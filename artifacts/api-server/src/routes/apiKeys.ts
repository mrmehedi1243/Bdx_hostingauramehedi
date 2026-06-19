import { Router } from "express";
import { db, apiKeysTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { randomBytes } from "crypto";
import { CreateApiKeyBody } from "@workspace/api-zod";

const router = Router();

function generateKey(): string {
  return randomBytes(24).toString("hex");
}

router.get("/apikeys", async (req, res) => {
  try {
    const { status } = req.query as { status?: string };
    let keys = await db.select().from(apiKeysTable).orderBy(apiKeysTable.createdAt);
    if (status) {
      keys = keys.filter((k) => k.status === status);
    }
    const result = keys.map((k) => ({
      id: k.id,
      key: k.key,
      label: k.label,
      status: k.status,
      usageCount: k.usageCount,
      maxUsers: k.maxUsers ?? null,
      expiresAt: k.expiresAt ? k.expiresAt.toISOString() : null,
      createdAt: k.createdAt.toISOString(),
    }));
    res.json(result);
  } catch (err) {
    req.log.error({ err }, "listApiKeys error");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/apikeys", async (req, res) => {
  try {
    const parsed = CreateApiKeyBody.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: "Invalid input" });
      return;
    }
    const { label, maxUsers } = parsed.data;
    const [created] = await db
      .insert(apiKeysTable)
      .values({ key: generateKey(), label, maxUsers: maxUsers ?? null })
      .returning();
    res.status(201).json({
      id: created.id,
      key: created.key,
      label: created.label,
      status: created.status,
      usageCount: created.usageCount,
      maxUsers: created.maxUsers ?? null,
      expiresAt: created.expiresAt ? created.expiresAt.toISOString() : null,
      createdAt: created.createdAt.toISOString(),
    });
  } catch (err) {
    req.log.error({ err }, "createApiKey error");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/apikeys/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const [key] = await db.select().from(apiKeysTable).where(eq(apiKeysTable.id, id));
    if (!key) {
      res.status(404).json({ error: "Not found" });
      return;
    }
    res.json({
      id: key.id,
      key: key.key,
      label: key.label,
      status: key.status,
      usageCount: key.usageCount,
      maxUsers: key.maxUsers ?? null,
      expiresAt: key.expiresAt ? key.expiresAt.toISOString() : null,
      createdAt: key.createdAt.toISOString(),
    });
  } catch (err) {
    req.log.error({ err }, "getApiKey error");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.delete("/apikeys/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    await db.delete(apiKeysTable).where(eq(apiKeysTable.id, id));
    res.json({ success: true, message: "Deleted" });
  } catch (err) {
    req.log.error({ err }, "deleteApiKey error");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/apikeys/:id/revoke", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const [updated] = await db
      .update(apiKeysTable)
      .set({ status: "revoked" })
      .where(eq(apiKeysTable.id, id))
      .returning();
    if (!updated) {
      res.status(404).json({ error: "Not found" });
      return;
    }
    res.json({
      id: updated.id,
      key: updated.key,
      label: updated.label,
      status: updated.status,
      usageCount: updated.usageCount,
      maxUsers: updated.maxUsers ?? null,
      expiresAt: updated.expiresAt ? updated.expiresAt.toISOString() : null,
      createdAt: updated.createdAt.toISOString(),
    });
  } catch (err) {
    req.log.error({ err }, "revokeApiKey error");
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
