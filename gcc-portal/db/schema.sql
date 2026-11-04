CREATE TABLE IF NOT EXISTS companies (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  domain TEXT UNIQUE,
  parent_company TEXT,
  hq_country TEXT,
  india_cities TEXT[] DEFAULT '{}',
  india_headcount_range TEXT,
  industry TEXT,
  gcc_function TEXT,           -- e.g. engineering, analytics, shared services
  year_established INT,
  tech_stack TEXT[] DEFAULT '{}',
  careers_url TEXT,
  source TEXT,                 -- where this row first came from
  last_refreshed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS job_postings (
  id SERIAL PRIMARY KEY,
  company_id INT REFERENCES companies(id) ON DELETE CASCADE,
  title TEXT, location TEXT, url TEXT UNIQUE, department TEXT,
  first_seen TIMESTAMPTZ DEFAULT now(), last_seen TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS signals (   -- news, expansions, leadership changes
  id SERIAL PRIMARY KEY,
  company_id INT REFERENCES companies(id) ON DELETE CASCADE,
  kind TEXT, headline TEXT, url TEXT UNIQUE, published_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  plan TEXT NOT NULL DEFAULT 'free',   -- free | pro | team
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON job_postings(company_id);

-- v2: auth, plans, saved items, billing, ingestion tracking
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';  -- user | admin
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_customer_id TEXT;
CREATE TABLE IF NOT EXISTS saved_companies (
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  company_id INT REFERENCES companies(id) ON DELETE CASCADE,
  note TEXT, created_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, company_id));
CREATE TABLE IF NOT EXISTS saved_searches (   -- powers email alerts
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  name TEXT, query JSONB NOT NULL, alert BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS payments (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE SET NULL,
  provider TEXT, provider_ref TEXT UNIQUE, plan TEXT, amount_minor INT, currency TEXT,
  status TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS ingestion_runs (
  id SERIAL PRIMARY KEY, kind TEXT, started_at TIMESTAMPTZ DEFAULT now(),
  finished_at TIMESTAMPTZ, rows_in INT DEFAULT 0, rows_ok INT DEFAULT 0, note TEXT);
CREATE TABLE IF NOT EXISTS leads (            -- landing-page email capture
  id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, source TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies (lower(name));
CREATE INDEX IF NOT EXISTS idx_companies_refreshed ON companies (last_refreshed_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_signals_company_date ON signals (company_id, published_at DESC);

-- v3: media hub (news, expansions tracker, quarterly reports)
CREATE TABLE IF NOT EXISTS articles (
  id SERIAL PRIMARY KEY,
  kind TEXT NOT NULL DEFAULT 'news',        -- news | analysis | explainer
  slug TEXT UNIQUE, title TEXT NOT NULL, summary TEXT, body TEXT,
  source_name TEXT, source_url TEXT UNIQUE,  -- external news: we store headline+link only, never full text
  city TEXT, tags TEXT[] DEFAULT '{}', company_id INT REFERENCES companies(id) ON DELETE SET NULL,
  published_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS expansions (      -- GCC launches / expansions / closures
  id SERIAL PRIMARY KEY,
  company_id INT REFERENCES companies(id) ON DELETE SET NULL, company_name TEXT NOT NULL,
  city TEXT, event TEXT NOT NULL DEFAULT 'opened',   -- opened | expanded | closed | announced
  headcount INT, summary TEXT, source_url TEXT UNIQUE,
  verified BOOLEAN DEFAULT false,            -- auto-detected rows start unverified
  announced_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_articles_pub ON articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_exp_date ON expansions (announced_at DESC);
