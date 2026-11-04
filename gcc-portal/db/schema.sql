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

-- v4: community, enrichment, weekly digest, trackers
ALTER TABLE articles ADD COLUMN IF NOT EXISTS category TEXT;      -- funding|leadership|expansion|hiring|policy|ai|other
ALTER TABLE articles ADD COLUMN IF NOT EXISTS score INT NOT NULL DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS comment_count INT NOT NULL DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS wikipedia_url TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS wikidata_id TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS global_employees BIGINT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS founded_year INT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS website TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS ticker TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS aliases TEXT[] DEFAULT '{}';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS logo_url TEXT;
CREATE TABLE IF NOT EXISTS comments (
  id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id) ON DELETE CASCADE,
  target_type TEXT NOT NULL,            -- article | company | expansion
  target_id INT NOT NULL, parent_id INT REFERENCES comments(id) ON DELETE CASCADE,
  body TEXT NOT NULL, deleted BOOLEAN DEFAULT false, reports INT DEFAULT 0, created_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target_type, target_id, created_at);
CREATE TABLE IF NOT EXISTS votes (user_id INT REFERENCES users(id) ON DELETE CASCADE, article_id INT REFERENCES articles(id) ON DELETE CASCADE, PRIMARY KEY(user_id, article_id));
CREATE TABLE IF NOT EXISTS follows (user_id INT REFERENCES users(id) ON DELETE CASCADE, kind TEXT NOT NULL, value TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(user_id, kind, value));  -- kind: company(value=id)|city|topic
CREATE TABLE IF NOT EXISTS subscribers (
  id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, topics TEXT[] DEFAULT '{}', cities TEXT[] DEFAULT '{}',
  token TEXT NOT NULL DEFAULT md5(random()::text || clock_timestamp()::text), confirmed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(), unsubscribed_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS digests (
  id SERIAL PRIMARY KEY, week_start DATE UNIQUE NOT NULL, title TEXT, html TEXT, text TEXT, stats JSONB, sent_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS policies (
  id SERIAL PRIMARY KEY, state TEXT NOT NULL, name TEXT NOT NULL, year INT, summary TEXT, incentives TEXT[] DEFAULT '{}',
  source_url TEXT, fetched_at TIMESTAMPTZ DEFAULT now(), UNIQUE(state, name));
CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY, name TEXT NOT NULL, city TEXT, starts_on DATE, url TEXT, description TEXT, source_url TEXT, UNIQUE(name, starts_on));
CREATE TABLE IF NOT EXISTS people_moves (
  id SERIAL PRIMARY KEY, person TEXT, role TEXT, company_name TEXT, company_id INT REFERENCES companies(id) ON DELETE SET NULL,
  city TEXT, kind TEXT DEFAULT 'appointed', source_url TEXT UNIQUE, published_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS fundings (
  id SERIAL PRIMARY KEY, company_name TEXT NOT NULL, kind TEXT DEFAULT 'funding', amount_text TEXT, round TEXT, investors TEXT,
  summary TEXT, source_url TEXT UNIQUE, published_at TIMESTAMPTZ);
CREATE INDEX IF NOT EXISTS idx_articles_cat ON articles(category, published_at DESC);

-- v4 community: report de-dupe, DB-enforced comment rate limit, synced counters
CREATE TABLE IF NOT EXISTS comment_reports (comment_id INT REFERENCES comments(id) ON DELETE CASCADE, user_id INT REFERENCES users(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(comment_id, user_id));
CREATE INDEX IF NOT EXISTS idx_comments_user_time ON comments(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_follows_kind_value ON follows(kind, value);
CREATE INDEX IF NOT EXISTS idx_articles_company ON articles(company_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(score DESC, published_at DESC);

CREATE OR REPLACE FUNCTION gcc_comment_rate() RETURNS trigger AS $f$
BEGIN
  PERFORM pg_advisory_xact_lock(7001, NEW.user_id);   -- serialise one user's inserts so the checks below can't race
  IF EXISTS (SELECT 1 FROM comments WHERE user_id = NEW.user_id AND created_at > clock_timestamp() - interval '15 seconds') THEN
    RAISE EXCEPTION 'rate_limit_15s' USING ERRCODE = 'P0001';
  END IF;
  IF (SELECT count(*) FROM comments WHERE user_id = NEW.user_id AND created_at > clock_timestamp() - interval '1 hour') >= 20 THEN
    RAISE EXCEPTION 'rate_limit_hour' USING ERRCODE = 'P0001';
  END IF;
  RETURN NEW;
END $f$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_comment_rate ON comments;
CREATE TRIGGER trg_comment_rate BEFORE INSERT ON comments FOR EACH ROW EXECUTE FUNCTION gcc_comment_rate();

CREATE OR REPLACE FUNCTION gcc_sync_comment_count() RETURNS trigger AS $f$
DECLARE ty TEXT; tid INT;
BEGIN
  IF TG_OP = 'DELETE' THEN ty := OLD.target_type; tid := OLD.target_id; ELSE ty := NEW.target_type; tid := NEW.target_id; END IF;
  IF ty = 'article' THEN
    UPDATE articles SET comment_count = (SELECT count(*) FROM comments WHERE target_type='article' AND target_id=tid AND NOT deleted AND reports < 3) WHERE id = tid;
  END IF;
  RETURN NULL;
END $f$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_comment_count ON comments;
CREATE TRIGGER trg_comment_count AFTER INSERT OR UPDATE OF deleted, reports OR DELETE ON comments FOR EACH ROW EXECUTE FUNCTION gcc_sync_comment_count();

CREATE OR REPLACE FUNCTION gcc_sync_score() RETURNS trigger AS $f$
DECLARE aid INT;
BEGIN
  IF TG_OP = 'DELETE' THEN aid := OLD.article_id; ELSE aid := NEW.article_id; END IF;
  UPDATE articles SET score = (SELECT count(*) FROM votes WHERE article_id = aid) WHERE id = aid;
  RETURN NULL;
END $f$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_vote_score ON votes;
CREATE TRIGGER trg_vote_score AFTER INSERT OR DELETE ON votes FOR EACH ROW EXECUTE FUNCTION gcc_sync_score();

-- v5: deploy-readiness (rate limits, subscriber bookkeeping, digest stats)
CREATE TABLE IF NOT EXISTS rate_limits (
  key TEXT PRIMARY KEY, count INT NOT NULL DEFAULT 0, window_start TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start);
ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS last_digest DATE;      -- week_start of the last digest mailed to this person
ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE digests ADD COLUMN IF NOT EXISTS sent_count INT NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(confirmed) WHERE unsubscribed_at IS NULL;
