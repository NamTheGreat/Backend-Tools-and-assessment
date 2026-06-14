# Database Schema Design - HubSpot Deals ETL

## Database: PostgreSQL
## Schema: hubspot_deals

## Table: deals

### CREATE TABLE Statement
```sql
CREATE SCHEMA IF NOT EXISTS hubspot_deals;

CREATE TABLE IF NOT EXISTS hubspot_deals.deals (
    -- Primary Key (HubSpot deal ID)
    id                          VARCHAR(50)     PRIMARY KEY,

    -- Core Deal Properties
    deal_name                   VARCHAR(500)    NOT NULL,
    amount                      NUMERIC(15, 2)  NULL,
    deal_stage                  VARCHAR(100)    NULL,
    pipeline                    VARCHAR(100)    NULL,
    close_date                  TIMESTAMP       NULL,
    created_date                TIMESTAMP       NULL,
    last_modified_date          TIMESTAMP       NULL,
    hubspot_owner_id            VARCHAR(50)     NULL,
    description                 TEXT            NULL,
    deal_stage_probability      NUMERIC(5, 4)   NULL,
    is_closed                   BOOLEAN         DEFAULT FALSE,
    is_closed_won               BOOLEAN         DEFAULT FALSE,
    priority                    VARCHAR(50)     NULL,

    -- ETL Metadata Fields
    _extracted_at               TIMESTAMP       NOT NULL DEFAULT NOW(),
    _scan_id                    VARCHAR(100)    NOT NULL,
    _tenant_id                  VARCHAR(100)    NOT NULL,

    -- Audit
    created_at                  TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMP       NOT NULL DEFAULT NOW()
);
```

### HubSpot Property -> PostgreSQL Type Mapping
| HubSpot Property | HubSpot Type | PostgreSQL Column | PostgreSQL Type |
|---|---|---|---|
| hs_object_id | string (numeric) | id | VARCHAR(50) |
| dealname | string | deal_name | VARCHAR(500) |
| amount | string (numeric) | amount | NUMERIC(15,2) |
| dealstage | enumeration | deal_stage | VARCHAR(100) |
| pipeline | enumeration | pipeline | VARCHAR(100) |
| closedate | datetime (ISO8601) | close_date | TIMESTAMP |
| createdate | datetime (ISO8601) | created_date | TIMESTAMP |
| hs_lastmodifieddate | datetime (ISO8601) | last_modified_date | TIMESTAMP |
| hubspot_owner_id | string | hubspot_owner_id | VARCHAR(50) |
| description | string | description | TEXT |
| hs_deal_stage_probability | number | deal_stage_probability | NUMERIC(5,4) |
| hs_is_closed | bool | is_closed | BOOLEAN |
| hs_is_closed_won | bool | is_closed_won | BOOLEAN |
| hs_priority | enumeration | priority | VARCHAR(50) |

### Data Type Conversion Rules
- HubSpot `amount` comes as a string -> cast to NUMERIC, set NULL if empty string
- HubSpot dates come as ISO8601 strings -> parse to Python datetime -> store as TIMESTAMP
- HubSpot booleans come as string `"true"`/`"false"` -> convert to Python bool
- Empty strings `""` -> store as NULL (do not store empty strings)
- `hs_deal_stage_probability` is a 0-100 float from HubSpot -> divide by 100 before storing

## Indexes
```sql
-- Tenant isolation (most queries filter by tenant)
CREATE INDEX idx_deals_tenant_id
    ON hubspot_deals.deals (_tenant_id);

-- Scan lookup
CREATE INDEX idx_deals_scan_id
    ON hubspot_deals.deals (_scan_id);

-- Stage filtering
CREATE INDEX idx_deals_stage
    ON hubspot_deals.deals (deal_stage);

-- Date range queries
CREATE INDEX idx_deals_close_date
    ON hubspot_deals.deals (close_date);

CREATE INDEX idx_deals_created_date
    ON hubspot_deals.deals (created_date);

-- Compound: tenant + stage (common query pattern)
CREATE INDEX idx_deals_tenant_stage
    ON hubspot_deals.deals (_tenant_id, deal_stage);

-- Compound: tenant + close date (common query pattern)
CREATE INDEX idx_deals_tenant_close_date
    ON hubspot_deals.deals (_tenant_id, close_date);
```

## Multi-Tenant Data Isolation Strategy
- Every row contains `_tenant_id` - all queries MUST filter by it
- Tenants never see each other's data
- `_tenant_id` is injected at extraction time from the scan request payload
- Recommended: add PostgreSQL Row Level Security (RLS) as an additional layer:
```sql
ALTER TABLE hubspot_deals.deals ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON hubspot_deals.deals
    USING (_tenant_id = current_setting('app.tenant_id'));
```

## ETL Metadata Fields
| Field | Purpose |
|---|---|
| `_extracted_at` | Timestamp when this record was pulled from HubSpot |
| `_scan_id` | Links every record to the extraction job that created it |
| `_tenant_id` | Identifies which customer's data this belongs to |

## Upsert Strategy
On conflict (duplicate `id`), update all mutable fields:
```sql
INSERT INTO hubspot_deals.deals (...) VALUES (...)
ON CONFLICT (id) DO UPDATE SET
    deal_name = EXCLUDED.deal_name,
    amount = EXCLUDED.amount,
    deal_stage = EXCLUDED.deal_stage,
    ...
    updated_at = NOW();
```
