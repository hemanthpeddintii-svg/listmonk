import { q } from "./db";
export const quarterOf = (d) => `Q${Math.floor(new Date(d).getUTCMonth() / 3) + 1}`;
export const bounds = (year, qn) => [new Date(Date.UTC(year, (qn - 1) * 3, 1)), new Date(Date.UTC(year, qn * 3, 1))];
export const ago = (d) => { const s = (Date.now() - new Date(d)) / 1000; if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m ago`; if (s < 86400) return `${Math.floor(s / 3600)}h ago`; if (s < 86400 * 30) return `${Math.floor(s / 86400)}d ago`; return new Date(d).toISOString().slice(0, 10); };
export const clean = (t = "") => t.replace(/\s+-\s+[^-]+$/, "");           // strip " - Publisher" suffix from RSS titles
export const href = (a) => `/story/${a.id}`;
export const external = (a) => !a.body;
export const latestNews = (n = 12, where = "", args = []) =>
  q(`SELECT * FROM articles ${where} ORDER BY published_at DESC NULLS LAST LIMIT ${Number(n)}`, args);
export const CITY_LIST = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi NCR", "Gurugram", "Noida", "Kolkata", "Ahmedabad", "Coimbatore", "Kochi"];
