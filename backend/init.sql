-- ============================================================
-- Tender Platform — Initial Schema
-- PostgreSQL 16+
-- Run: psql -U postgres -d tender_platform -f init.sql
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Trigram similarity for fuzzy search

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE source_type AS ENUM ('eis', 'rts', 'sber', 'corp', 'sub');
CREATE TYPE law_type AS ENUM ('44-fz', '223-fz', 'commercial', 'corporate', 'subcontract');
CREATE TYPE purchase_type AS ENUM ('auction', 'quotation', 'contest', 'single_source', 'direct_request', 'other');
CREATE TYPE tender_status AS ENUM ('active', 'completed', 'cancelled', 'draft');
CREATE TYPE company_type AS ENUM ('contractor', 'customer', 'supplier', 'mixed');
CREATE TYPE company_status AS ENUM ('active', 'liquidated', 'reorganizing');
CREATE TYPE request_status AS ENUM ('active', 'closed', 'expired');

-- ============================================================
-- SOURCES
-- ============================================================

CREATE TABLE sources (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(50) NOT NULL,
    source_type source_type NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    color VARCHAR(7) DEFAULT '#3b82f6',
    is_active BOOLEAN DEFAULT TRUE,
    parse_method VARCHAR(100),
    parse_frequency VARCHAR(100),
    last_parsed_at TIMESTAMPTZ,
    tender_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed sources
INSERT INTO sources (id, name, short_name, source_type, base_url, color, parse_method, parse_frequency) VALUES
    ('eis', 'ЕИС (zakupki.gov.ru)', 'ЕИС', 'eis', 'https://zakupki.gov.ru', '#3b82f6', 'ftp_xml', 'every_2h'),
    ('rts', 'РТС-тендер', 'РТС', 'rts', 'https://rts-tender.ru', '#22c55e', 'scrapy_json', 'twice_daily'),
    ('sber', 'Сбербанк-АСТ', 'Сбер-АСТ', 'sber', 'https://sberbank-ast.ru', '#f59e0b', 'scrapy_html', 'twice_daily'),
    ('rosneft', 'Роснефть', 'Роснефть', 'corp', 'https://tenders.rosneft.ru', '#a855f7', 'scrapy_html', 'daily'),
    ('gazprom', 'Газпром', 'Газпром', 'corp', 'https://zakupki.gazprom.ru', '#8b5cf6', 'scrapy_html', 'daily'),
    ('lukoil', 'ЛУКОЙЛ', 'ЛУКОЙЛ', 'corp', 'https://lukoil.ru', '#7c3aed', 'scrapy_html', 'daily'),
    ('vsem_podryad', 'Всем Подряд', 'Субподряды', 'sub', 'https://vsem-podryad.ru', '#ec4899', 'scrapy_html', 'daily');

-- ============================================================
-- TENDERS
-- ============================================================

CREATE TABLE tenders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id VARCHAR(20) NOT NULL REFERENCES sources(id),
    source_number VARCHAR(100) NOT NULL,
    source_url VARCHAR(1000),
    
    title TEXT NOT NULL,
    description TEXT,
    
    law_type law_type NOT NULL,
    purchase_type purchase_type,
    okved_codes VARCHAR(20)[] DEFAULT '{}',
    okpd_codes VARCHAR(20)[] DEFAULT '{}',
    tags VARCHAR(100)[] DEFAULT '{}',
    
    nmck NUMERIC(18,2),
    currency VARCHAR(3) DEFAULT 'RUB',
    contract_price NUMERIC(18,2),
    
    customer_name VARCHAR(500),
    customer_inn VARCHAR(12),
    winner_name VARCHAR(500),
    winner_inn VARCHAR(12),
    
    region VARCHAR(200),
    region_code INTEGER,
    
    publish_date TIMESTAMPTZ,
    deadline TIMESTAMPTZ,
    
    status tender_status DEFAULT 'active',
    raw_data JSONB,
    search_vector TSVECTOR,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_tender_source UNIQUE (source_id, source_number)
);

-- Indexes
CREATE INDEX ix_tender_search ON tenders USING GIN (search_vector);
CREATE INDEX ix_tender_source ON tenders (source_id);
CREATE INDEX ix_tender_status ON tenders (status);
CREATE INDEX ix_tender_law ON tenders (law_type);
CREATE INDEX ix_tender_region ON tenders (region_code);
CREATE INDEX ix_tender_customer ON tenders (customer_inn);
CREATE INDEX ix_tender_winner ON tenders (winner_inn);
CREATE INDEX ix_tender_publish ON tenders (publish_date DESC);
CREATE INDEX ix_tender_deadline ON tenders (deadline);
CREATE INDEX ix_tender_nmck ON tenders (nmck);
CREATE INDEX ix_tender_okved ON tenders USING GIN (okved_codes);
CREATE INDEX ix_tender_title_trgm ON tenders USING GIN (title gin_trgm_ops);

-- Auto-update search vector
CREATE OR REPLACE FUNCTION tenders_search_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('russian', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('russian', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('russian', COALESCE(NEW.customer_name, '')), 'C') ||
        setweight(to_tsvector('russian', COALESCE(NEW.region, '')), 'D');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tenders_search 
    BEFORE INSERT OR UPDATE OF title, description, customer_name, region 
    ON tenders FOR EACH ROW EXECUTE FUNCTION tenders_search_update();

-- ============================================================
-- OKVED CODES
-- ============================================================

CREATE TABLE okved_codes (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    section VARCHAR(5),
    section_name VARCHAR(300),
    parent_code VARCHAR(20),
    level INTEGER DEFAULT 0
);

CREATE INDEX ix_okved_section ON okved_codes (section);
CREATE INDEX ix_okved_parent ON okved_codes (parent_code);

-- ============================================================
-- COMPANIES
-- ============================================================

CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inn VARCHAR(12) UNIQUE NOT NULL,
    ogrn VARCHAR(15) UNIQUE,
    
    full_name VARCHAR(1000) NOT NULL,
    short_name VARCHAR(500),
    
    legal_address TEXT,
    region VARCHAR(200),
    region_code INTEGER,
    
    director_name VARCHAR(300),
    director_title VARCHAR(200),
    
    registration_date DATE,
    authorized_capital NUMERIC(18,2),
    
    primary_okved VARCHAR(20),
    company_type company_type,
    status company_status DEFAULT 'active',
    
    tender_wins_count INTEGER DEFAULT 0,
    tender_wins_sum NUMERIC(18,2),
    arbitration_count INTEGER DEFAULT 0,
    has_sro BOOLEAN DEFAULT FALSE,
    
    is_verified BOOLEAN DEFAULT FALSE,
    egrul_updated_at TIMESTAMPTZ,
    search_vector TSVECTOR,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_company_search ON companies USING GIN (search_vector);
CREATE INDEX ix_company_inn ON companies (inn);
CREATE INDEX ix_company_region ON companies (region_code);
CREATE INDEX ix_company_okved ON companies (primary_okved);
CREATE INDEX ix_company_status ON companies (status);
CREATE INDEX ix_company_wins ON companies (tender_wins_count DESC);
CREATE INDEX ix_company_name_trgm ON companies USING GIN (full_name gin_trgm_ops);

CREATE OR REPLACE FUNCTION companies_search_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('russian', COALESCE(NEW.full_name, '')), 'A') ||
        setweight(to_tsvector('russian', COALESCE(NEW.short_name, '')), 'A') ||
        setweight(to_tsvector('russian', COALESCE(NEW.legal_address, '')), 'C') ||
        setweight(to_tsvector('russian', COALESCE(NEW.director_name, '')), 'D');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_companies_search
    BEFORE INSERT OR UPDATE OF full_name, short_name, legal_address, director_name
    ON companies FOR EACH ROW EXECUTE FUNCTION companies_search_update();

-- ============================================================
-- COMPANY_OKVEDS
-- ============================================================

CREATE TABLE company_okveds (
    id SERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    okved_code VARCHAR(20) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    CONSTRAINT uq_company_okved UNIQUE (company_id, okved_code)
);

CREATE INDEX ix_co_okved ON company_okveds (okved_code);

-- ============================================================
-- CONTACTS
-- ============================================================

CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_type VARCHAR(20) NOT NULL,  -- 'email', 'phone', 'website'
    value VARCHAR(500) NOT NULL,
    source VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE
);

-- ============================================================
-- SRO_PERMITS
-- ============================================================

CREATE TABLE sro_permits (
    id SERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    sro_name VARCHAR(500) NOT NULL,
    permit_number VARCHAR(100),
    max_contract_sum NUMERIC(18,2),
    status VARCHAR(50) DEFAULT 'active',
    issue_date DATE
);

-- ============================================================
-- ARBITRATIONS
-- ============================================================

CREATE TABLE arbitrations (
    id SERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    case_number VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'plaintiff', 'defendant'
    amount NUMERIC(18,2),
    status VARCHAR(50),
    court VARCHAR(300),
    filing_date DATE,
    CONSTRAINT uq_company_case UNIQUE (company_id, case_number)
);

-- ============================================================
-- FINANCIALS
-- ============================================================

CREATE TABLE financials (
    id SERIAL PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    revenue NUMERIC(18,2),
    profit NUMERIC(18,2),
    assets NUMERIC(18,2),
    employees INTEGER,
    source VARCHAR(50) DEFAULT 'bo.nalog.ru',
    CONSTRAINT uq_company_year UNIQUE (company_id, year)
);

-- ============================================================
-- REQUESTS (Заявки на субподряд)
-- ============================================================

CREATE TABLE requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id VARCHAR(20) REFERENCES sources(id),
    source_url VARCHAR(1000),
    is_user_created BOOLEAN DEFAULT FALSE,
    
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(200),
    
    budget_min NUMERIC(18,2),
    budget_max NUMERIC(18,2),
    budget_text VARCHAR(200),
    
    region VARCHAR(200),
    address TEXT,
    
    company_name VARCHAR(500),
    contact_phone VARCHAR(50),
    contact_email VARCHAR(200),
    
    status request_status DEFAULT 'active',
    publish_date DATE,
    expire_date DATE,
    
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_request_search ON requests USING GIN (search_vector);
CREATE INDEX ix_request_status ON requests (status);
CREATE INDEX ix_request_region ON requests (region);

CREATE OR REPLACE FUNCTION requests_search_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('russian', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('russian', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('russian', COALESCE(NEW.region, '')), 'C');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_requests_search
    BEFORE INSERT OR UPDATE OF title, description, region
    ON requests FOR EACH ROW EXECUTE FUNCTION requests_search_update();

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(300) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    full_name VARCHAR(300),
    phone VARCHAR(50),
    company_inn VARCHAR(12),
    role VARCHAR(20) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- ============================================================
-- SUBSCRIPTIONS
-- ============================================================

CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filters JSONB NOT NULL,
    name VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    notify_email BOOLEAN DEFAULT TRUE,
    notify_push BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PARSE_LOGS
-- ============================================================

CREATE TABLE parse_logs (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(20) NOT NULL REFERENCES sources(id),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'running',
    records_found INTEGER DEFAULT 0,
    records_new INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX ix_parselog_source ON parse_logs (source_id, started_at DESC);

-- ============================================================
-- VIEWS (useful aggregations)
-- ============================================================

-- Stats per source
CREATE OR REPLACE VIEW v_source_stats AS
SELECT 
    s.id, s.name, s.short_name, s.color, s.is_active,
    s.last_parsed_at,
    COUNT(t.id) AS tender_count,
    COUNT(t.id) FILTER (WHERE t.status = 'active') AS active_count
FROM sources s
LEFT JOIN tenders t ON t.source_id = s.id
GROUP BY s.id;

-- Company with latest financials
CREATE OR REPLACE VIEW v_company_enriched AS
SELECT 
    c.*,
    f.revenue AS latest_revenue,
    f.profit AS latest_profit,
    f.employees AS latest_employees,
    f.year AS financial_year
FROM companies c
LEFT JOIN LATERAL (
    SELECT revenue, profit, employees, year
    FROM financials 
    WHERE company_id = c.id 
    ORDER BY year DESC LIMIT 1
) f ON TRUE;

-- ============================================================
-- DONE
-- ============================================================
SELECT 'Schema created successfully' AS status;
