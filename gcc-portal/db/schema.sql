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
