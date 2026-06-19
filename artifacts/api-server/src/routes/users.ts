import { Router } from "express";
import { db, usersTable, apiKeysTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { CreateUserBody } from "@workspace/api-zod";

const router = Router();

const VALIDITY_DAYS = 15;

function expiresAt(): Date {
  const d = new Date();
  d.setDate(d.getDate() + VALIDITY_DAYS);
  return d;
}

function formatUser(u: typeof usersTable.$inferSelect, apiKey: string) {
  return {
    id: u.id,
    username: u.username,
    password: u.password,
    apiKeyId: u.apiKeyId,
    apiKey,
    status: u.status,
    expiresAt: u.expiresAt.toISOString(),
    createdAt: u.createdAt.toISOString(),
  };
}

router.get("/users", async (req, res) => {
  try {
    const rows = await db
      .select({
        user: usersTable,
        key: apiKeysTable.key,
      })
      .from(usersTable)
      .leftJoin(apiKeysTable, eq(usersTable.apiKeyId, apiKeysTable.id))
      .orderBy(usersTable.createdAt);

    const result = rows.map((r) => formatUser(r.user, r.key ?? ""));
    res.json(result);
  } catch (err) {
    req.log.error({ err }, "listUsers error");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/users", async (req, res) => {
  try {
    const parsed = CreateUserBody.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: "Invalid input" });
      return;
    }
    const { username, password, apiKey } = parsed.data;

    const [key] = await db
      .select()
      .from(apiKeysTable)
      .where(eq(apiKeysTable.key, apiKey));

    if (!key || key.status !== "active") {
      res.status(400).json({ error: "Invalid or expired API key" });
      return;
    }

    if (key.maxUsers !== null && key.usageCount >= key.maxUsers) {
      res.status(400).json({ error: "API key usage limit reached" });
      return;
    }

    const now = new Date();
    if (key.expiresAt && key.expiresAt < now) {
      await db
        .update(apiKeysTable)
        .set({ status: "expired" })
        .where(eq(apiKeysTable.id, key.id));
      res.status(400).json({ error: "API key has expired" });
      return;
    }

    const [created] = await db
      .insert(usersTable)
      .values({
        username,
        password,
        apiKeyId: key.id,
        status: "active",
        expiresAt: expiresAt(),
      })
      .returning();

    await db
      .update(apiKeysTable)
      .set({ usageCount: key.usageCount + 1 })
      .where(eq(apiKeysTable.id, key.id));

    res.status(201).json(formatUser(created, apiKey));
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "";
    if (msg.includes("unique")) {
      res.status(400).json({ error: "Username already exists" });
      return;
    }
    req.log.error({ err }, "createUser error");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/users/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const [row] = await db
      .select({ user: usersTable, key: apiKeysTable.key })
      .from(usersTable)
      .leftJoin(apiKeysTable, eq(usersTable.apiKeyId, apiKeysTable.id))
      .where(eq(usersTable.id, id));

    if (!row) {
      res.status(404).json({ error: "Not found" });
      return;
    }
    res.json(formatUser(row.user, row.key ?? ""));
  } catch (err) {
    req.log.error({ err }, "getUser error");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.delete("/users/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    await db.delete(usersTable).where(eq(usersTable.id, id));
    res.json({ success: true, message: "Deleted" });
  } catch (err) {
    req.log.error({ err }, "deleteUser error");
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
