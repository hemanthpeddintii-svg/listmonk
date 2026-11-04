import pg from "pg";
export const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });
// TODO: replace with real auth (NextAuth email magic link) + Stripe/Razorpay webhooks setting users.plan.
export function currentPlan() { return process.env.DEMO_PLAN || "free"; }
