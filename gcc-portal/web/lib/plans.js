// Single source of truth for what each plan can do.
export const PLANS = {
  free: { label: "Free", price: "₹0", maxRows: 25, jobs: 3, signals: 3, export: false, saved: 10, alerts: 0 },
  pro:  { label: "Pro",  price: "₹2,999/mo", maxRows: 1000, jobs: 100, signals: 100, export: true, saved: 500, alerts: 10 },
  team: { label: "Team", price: "₹9,999/mo", maxRows: 100000, jobs: 500, signals: 500, export: true, saved: 5000, alerts: 100 },
};
export const planOf = (u) => PLANS[(u && effectivePlan(u)) || "free"];
export function effectivePlan(u) {
  if (u.plan !== "free" && u.plan_expires_at && new Date(u.plan_expires_at) < new Date()) return "free";
  return u.plan;
}
