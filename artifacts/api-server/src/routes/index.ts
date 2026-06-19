import { Router, type IRouter } from "express";
import healthRouter from "./health";
import adminRouter from "./admin";
import apiKeysRouter from "./apiKeys";
import usersRouter from "./users";
import dashboardRouter from "./dashboard";

const router: IRouter = Router();

router.use(healthRouter);
router.use(adminRouter);
router.use(apiKeysRouter);
router.use(usersRouter);
router.use(dashboardRouter);

export default router;
