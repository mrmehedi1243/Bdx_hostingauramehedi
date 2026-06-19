import { Router } from "express";

const router = Router();

const ADMIN_KEY = "mehedixaura";
const ADMIN_TOKEN = "akta_admin_session_token";

router.post("/admin/login", (req, res) => {
  const { accessKey } = req.body as { accessKey?: string };
  if (!accessKey || accessKey !== ADMIN_KEY) {
    res.status(401).json({ error: "Invalid access key" });
    return;
  }
  res.json({ authenticated: true, token: ADMIN_TOKEN });
});

router.get("/admin/verify", (req, res) => {
  const auth = req.headers.authorization;
  if (!auth || auth !== `Bearer ${ADMIN_TOKEN}`) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  res.json({ authenticated: true, token: ADMIN_TOKEN });
});

export default router;
