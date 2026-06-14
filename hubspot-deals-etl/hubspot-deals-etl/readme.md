# HubSpot Deals ETL

HubSpot Deals ETL is a Flask-RESTX service that extracts HubSpot deal data, writes it through DLT into PostgreSQL, and exposes scan management endpoints for monitoring and retrieval.

## What it does

- Pulls deal records from the HubSpot CRM API v3
- Normalizes HubSpot properties into a PostgreSQL-friendly schema
- Stores ETL metadata such as `_scan_id`, `_tenant_id`, and `_extracted_at`
- Supports cursor-based pagination and retry handling
- Exposes REST endpoints for scan start, status, results, cleanup, and health

## Project Layout

```text
hubspot-deals-etl/
├── api/
├── docs/
├── models/
├── services/
├── test-results/
├── app.py
├── config.py
├── docker-compose.yml
├── Dockerfile.dev
├── Dockerfile.prod
├── Dockerfile.stage
├── Dockerfile.test
├── .env.example
├── readme.md
├── requirements.txt
└── wsgi.py
```

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- A HubSpot private app access token with `crm.objects.deals.read`
- PostgreSQL 15+

## Environment Setup

Start from the example file:

```bash
cp .env.example .env
```

Important variables:

| Variable | Purpose |
|---|---|
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app token |
| `HUBSPOT_BASE_URL` | HubSpot API base URL |
| `PIPELINE_NAME` | DLT pipeline name |
| `DB_SCHEMA` | PostgreSQL schema name |
| `DATABASE_URL` | PostgreSQL connection string |
| `SERVICE_API_KEY` | Service-level API key for protected endpoints |
| `DEV_PORT` | Local development port |
| `STAGE_PORT` | Staging port |
| `PROD_PORT` | Production port |

## Quick Start

### With Docker

```bash
docker-compose up -d --build
```

Then check:

```bash
curl http://localhost:5200/api/health
```

Open the Swagger UI:

```bash
http://localhost:5200/docs
```

### Local Development

```bash
pip install -r requirements.txt
python app.py
```

## API Overview

The service is mounted under the `/api` prefix.

### Health

```http
GET /api/health
```

### Scan Management

```http
POST   /api/scan/start
GET    /api/scan/{scan_id}/status
POST   /api/scan/{scan_id}/cancel
DELETE /api/scan/{scan_id}/remove
POST   /api/scan/{scan_id}/pause
GET    /api/scan/list
GET    /api/scan/statistics
```

### Results and Pipeline

```http
GET /api/results/{scan_id}/tables
GET /api/results/{scan_id}/result
GET /api/pipeline/info
POST /api/maintenance/cleanup
POST /api/maintenance/detect-crashed
GET /api/stats
```

## HubSpot Integration

The HubSpot integration is centered on:

- `GET /crm/v3/objects/deals`
- Cursor pagination via `paging.next.after`
- Properties such as `dealname`, `amount`, `dealstage`, `pipeline`, `closedate`, and `hs_lastmodifieddate`

The integration and schema docs are here:

- [Integration Docs](docs/INTEGRATION-DOCS.md)
- [Database Design Docs](docs/DATABASE-DESIGN-DOCS.md)
- [Service API Docs](docs/APi-DOCS.md)

## Data Model

The extracted deals are normalized into the `hubspot_deals.deals` table with:

- `id` as the HubSpot deal ID
- core deal fields like `deal_name`, `amount`, `deal_stage`, and `close_date`
- ETL metadata like `_extracted_at`, `_scan_id`, and `_tenant_id`

## Testing

Run the available checks:

```bash
python -m py_compile app.py config.py api/*.py services/*.py models/*.py
```

If Docker is available:

```bash
docker-compose up -d --build
curl http://localhost:5200/api/health
```

## Test Results

The latest extraction verification is documented in:

- [test-results/deal-ids.md](test-results/deal-ids.md)

That file records the five test deals used for validation.

## Notes

- Keep `.env` out of git
- Use `.env.example` as the canonical template for new setups
- The repo currently contains both the scan orchestration layer and the HubSpot extraction implementation

