# Next steps (in priority order)

## A. Get it out of the cloud session and into a real host (first)
1. Merge pull request #1, or move `gcc-portal/` (plus `render.yaml` and `.github/workflows/gcc-portal-*.yml`) into its own repo. See `WORKFLOW.md`.
2. Deploy for testing. Free: Render (`HOSTING-FREE.md`). Better: AWS Lightsail with `deploy/aws-setup.sh` (about $12/month). **These have never been run for real; expect to fix a first-build snag.**
3. Set real values: `JWT_SECRET`, `ADMIN_EMAILS`, `SITE_URL`. Sign up with the admin email.
4. Turn on database backups and (for AWS) Lightsail snapshots. User accounts, comments and subscribers exist only in that database.

## B. Needed before taking anyone's money
5. **Payments.** Razorpay (India) and Stripe: create checkout, map their webhook payloads to the existing `/api/billing/webhook` shape, then set `BILLING_MODE=live` and remove the plan switcher. Decide real prices.
6. **Legal pages:** privacy policy, terms, refund policy, cookie notice. Company-level data only; keep it that way unless counsel signs off.
7. **Email:** configure SMTP (any provider with an SMTP login), then test subscribe confirm, the Monday digest and add password reset and email verification (not built).
8. **Domain + HTTPS + Cloudflare in front.**

## C. Data quality (what a paying customer judges)
9. Collapse duplicate expansion rows (same company + city + week) and let the admin verify entries; show "Verified" prominently.
10. Fill the deals and people-moves trackers properly (3 and 33 rows today).
11. Widen job coverage beyond 24 companies (more ATS types, company careers pages that publish JSON-LD `JobPosting`); never fake the rest.
12. Re-run the pipelines weekly (scheduler in `workers/`, or GitHub Actions with a `DATABASE_URL` secret) and watch `ingestion_runs`.
13. Replace "public knowledge" company data over time with sourced fields (HQ, India sites, headcount where public). Keep blank when unknown.
14. Write original articles (analysis, Q recaps, "top GCC cities") from the data. Today most of the site is linked headlines; original writing is what makes it a publication.

## D. Growth
15. Google Search Console + sitemap submission (`/sitemap.xml`, `/rss.xml`). SEO pages exist for companies, cities, stories and reports.
16. Google Ads on "GCC database / GCC list India" once payments and legal pages are live.
17. Social cards (Open Graph images) per story and report.
18. Referral and LinkedIn sharing; a lead-capture sample of the paid data.

## E. Engineering hygiene
19. Add automated tests (the browser flow scripts used during the build were throwaway; turn them into a Playwright suite in `web/tests/` and run in CI).
20. Consider TypeScript and a migrations tool when the schema starts changing weekly.
21. Admin tools to delete or hide a comment, ban a user, edit an article.
22. Accessibility pass (labels were fixed once; re-audit after changes).

## Do not do
Do not buy paid data credits to fill the database (owner's rule). Do not store personal contact data. Do not copy article text. Do not ship `BILLING_MODE=test` to the public after launch.
