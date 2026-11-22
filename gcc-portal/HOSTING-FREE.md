# Free hosting until you buy a domain (Render, about 10 minutes)

You get a public address like `https://gcc-intel.onrender.com`, with the starter data already loaded.

1. Go to https://render.com and sign up with your GitHub account (allow access to the `listmonk` repo).
2. Dashboard -> **New** -> **Blueprint** -> pick `hemanthpeddintii-svg/listmonk` and branch `claude/gcc-companies-portal-arqoke`.
3. Render reads `render.yaml` and shows two things to create: a web service and a database. When asked for **ADMIN_EMAILS**, type your own email.
4. Click **Apply**. The first build takes about 5 to 10 minutes. When it says *Live*, open the address shown on the service page.
5. Click **Start free**, sign up using the email you put in ADMIN_EMAILS. That account is the admin; you will see an **Admin** link in the top bar.
6. If the address Render gave you is not `gcc-intel.onrender.com`, edit the `SITE_URL` variable on the service (Environment tab) to match, so the sitemap and RSS point to the right place.

## What to expect on the free plan
- The site **sleeps after 15 minutes of no visits** and takes about a minute to wake up. Fine for testing, not for launch.
- The free database **expires after 30 days** on Render. Before then, upgrade it or move the data (`pg_dump`).
- **News will not refresh by itself** here (no background worker on the free plan). Use the GitHub Actions workflows in `.github/workflows/gcc-portal-*.yml`: add a repository secret `DATABASE_URL` (the *External* connection string from the Render database page) and they run news daily, the weekly refresh and the Monday digest.
- Email sending is off until you add SMTP variables (see `.env.example`). Subscribers still sign up; the confirm link is shown on screen in test mode.
- **Test mode is on**: any logged-in user can switch their own plan from the Dashboard. Before real launch set `BILLING_MODE=live` (payments are not built yet) or remove the switcher.
- There are no demo logins on this deployment; only your own signup exists.

## Custom domain later
Render service -> Settings -> Custom Domains -> add your domain and set the DNS records it shows. Then update `SITE_URL`.
