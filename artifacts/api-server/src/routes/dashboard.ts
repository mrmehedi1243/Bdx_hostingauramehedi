import { Router } from "express";
import { db, usersTable, apiKeysTable } from "@workspace/db";
import { eq, desc } from "drizzle-orm";

const router = Router();

router.get("/dashboard/stats", async (req, res) => {
  try {
    const allKeys = await db.select().from(apiKeysTable);
    const allUsers = await db
      .select({ user: usersTable, key: apiKeysTable.key })
      .from(usersTable)
      .leftJoin(apiKeysTable, eq(usersTable.apiKeyId, apiKeysTable.id));

    const now = new Date();

    const totalApiKeys = allKeys.length;
    const activeApiKeys = allKeys.filter((k) => k.status === "active").length;
    const totalUsers = allUsers.length;
    const activeUsers = allUsers.filter((r) => r.user.status === "active" && r.user.expiresAt > now).length;
    const expiredUsers = allUsers.filter((r) => r.user.status === "expired" || r.user.expiresAt <= now).length;

    const recentRows = await db
      .select({ user: usersTable, key: apiKeysTable.key })
      .from(usersTable)
      .leftJoin(apiKeysTable, eq(usersTable.apiKeyId, apiKeysTable.id))
      .orderBy(desc(usersTable.createdAt))
      .limit(10);

    const recentUsers = recentRows.map((r) => ({
      id: r.user.id,
      username: r.user.username,
      password: r.user.password,
      apiKeyId: r.user.apiKeyId,
      apiKey: r.key ?? "",
      status: r.user.status,
      expiresAt: r.user.expiresAt.toISOString(),
      createdAt: r.user.createdAt.toISOString(),
    }));

    res.json({ totalApiKeys, activeApiKeys, totalUsers, activeUsers, expiredUsers, recentUsers });
  } catch (err) {
    req.log.error({ err }, "getDashboardStats error");
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
