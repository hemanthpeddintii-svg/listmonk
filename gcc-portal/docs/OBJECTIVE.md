# Objective

## One line
Build and monetise **GCC Intel**: the daily record of India's Global Capability Center (GCC) boom. An Inc42-style news and intelligence portal for GCCs and MNC captive centres in India.

## Why it exists
Every week a multinational opens, expands or closes a centre in India. The announcements are scattered across hundreds of outlets, LinkedIn posts and state press notes. Nobody keeps one clean, searchable, dated record. Sales teams, recruiters, analysts and investors who need it either pay a lot for opaque data (GCC-intel vendors such as Ocean Frogs, AIM Research) or piece it together by hand.

## Who it is for (the three "doors" on the home page)
1. **I sell to GCCs.** Who just opened, who is hiring, who got a new leader.
2. **I hire from GCCs.** Which centres are hiring right now, by city.
3. **I invest or advise.** Quarter-by-quarter record, policy by state, deals.

## What success looks like
- People come back weekly (news daily, The GCC Weekly digest every Monday, comments and follows).
- Free users get real value from news and trackers; Pro users pay because the full database, exports, alerts and history save them a week of work. A paying customer should never feel they bought something thin: every record shows its source and date, and the limits are stated openly (see `/methodology`).
- Traffic from search: people searching "GCC database", "GCC India list", "GCC news" land here. (The word GCC also means the Gulf Cooperation Council; `/learn` explains both and we filter Gulf stories out.)
- The data stays fresh on its own: news daily, jobs and company profiles weekly, digest weekly.

## Business model
Freemium subscription. Free: read news and trackers, comment, follow, limited database view. Pro and Team: full database, longer history, CSV export, alerts, bigger saved lists. Prices in code (Pro Rs 2,999/month, Team Rs 9,999/month) are **placeholders**, not decisions. Razorpay for India, Stripe for international: **not built yet**.

## Hard constraints set by the owner
- **No paid data tools.** Do not spend credits on Apollo, Lusha, Prospeo, Apify, HubSpot or similar to build the data. Free public internet sources only.
- **No personal contact data.** Company-level data only for v1 (privacy law risk: India DPDP, GDPR). No scraped emails or phone numbers.
- **Headline + link only for news.** Never copy publisher article text.
- **Never fabricate data.** Blank is better than guessed. Auto-detected items are labelled "Detected" until a human verifies them.
- **The look must not feel AI-generated or template-like.** Editorial, hand-crafted, with real motion graphics.

## The meta-objective (how we work)
The project must live in **git**, not in any cloud session or on any one computer. Anyone (or any Claude session) can clone the repo, continue, push back, and then throw the working machine away. See `WORKFLOW.md`.
