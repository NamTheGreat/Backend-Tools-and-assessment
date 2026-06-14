# Service API Documentation - HubSpot Deals ETL

## Base URL
- Dev:   http://localhost:5200
- Stage: http://localhost:5201
- Prod:  http://localhost:5202

## Authentication
All endpoints (except /health) require:
```http
Authorization: Bearer <SERVICE_API_KEY>
```
The service API key is configured via `SERVICE_API_KEY` in `.env`.

---

## Endpoints

### Health Check
`GET /health`

No auth required.

**Response 200:**
```json
{ "status": "ok", "version": "1.0.0" }
```

---

### Start Extraction Scan
`POST /api/v1/scan/start`

**Request Body:**
```json
{
  "hubspot_access_token": "pat-na2-XXXX",
  "tenant_id": "tenant_abc",
  "pipeline_name": "hubspot_deals",
  "properties": ["dealname", "amount", "dealstage", "pipeline", "closedate"],
  "limit_per_page": 100,
  "checkpoint_every_n_pages": 5
}
```

**Response 202:**
```json
{
  "job_id": "job_a1b2c3d4",
  "status": "pending",
  "message": "Extraction job queued successfully",
  "created_at": "2026-06-14T10:00:00Z"
}
```

**Error Responses:**
| Code | Reason |
|---|---|
| 400 | Missing required fields or invalid token format |
| 401 | Invalid service API key |
| 422 | Validation error on request body |

---

### Get Scan Status
`GET /api/v1/scan/status/{job_id}`

**Response 200:**
```json
{
  "job_id": "job_a1b2c3d4",
  "status": "in_progress",
  "pages_processed": 3,
  "records_extracted": 287,
  "started_at": "2026-06-14T10:00:05Z",
  "last_checkpoint": "2026-06-14T10:01:30Z",
  "error": null
}
```

**Status values:** `pending` -> `in_progress` -> `completed` | `failed` | `cancelled`

**Error Responses:**
| Code | Reason |
|---|---|
| 404 | job_id not found |
| 401 | Invalid service API key |

---

### Get Scan Results
`GET /api/v1/scan/result/{job_id}?page=1&page_size=50`

Only available when job status is `completed`.

**Response 200:**
```json
{
  "job_id": "job_a1b2c3d4",
  "total_records": 5,
  "page": 1,
  "page_size": 50,
  "data": [
    {
      "id": "12345",
      "deal_name": "Won Enterprise Contract",
      "amount": 75000.00,
      "deal_stage": "closedwon",
      "pipeline": "default",
      "close_date": "2026-06-30T00:00:00Z",
      "_extracted_at": "2026-06-14T10:02:00Z",
      "_scan_id": "job_a1b2c3d4",
      "_tenant_id": "tenant_abc"
    }
  ]
}
```

**Error Responses:**
| Code | Reason |
|---|---|
| 404 | job_id not found |
| 409 | Job not yet completed |
| 401 | Invalid service API key |

---

### Cancel Scan
`POST /api/v1/scan/cancel/{job_id}`

Only cancels jobs in `pending` or `in_progress` state.

**Response 200:**
```json
{ "job_id": "job_a1b2c3d4", "status": "cancelled" }
```

**Error Responses:**
| Code | Reason |
|---|---|
| 400 | Job already completed or failed |
| 404 | job_id not found |

---

### Remove Scan
`DELETE /api/v1/scan/remove/{job_id}`

Deletes job record and all extracted data for that job.

**Response 200:**
```json
{ "job_id": "job_a1b2c3d4", "deleted": true }
```

---

### List All Jobs
`GET /api/v1/jobs/jobs?page=1&page_size=20&status=completed`

**Response 200:**
```json
{
  "total": 3,
  "page": 1,
  "page_size": 20,
  "jobs": [
    {
      "job_id": "job_a1b2c3d4",
      "status": "completed",
      "records_extracted": 5,
      "started_at": "2026-06-14T10:00:05Z",
      "completed_at": "2026-06-14T10:02:00Z"
    }
  ]
}
```

---

### Job Statistics
`GET /api/v1/jobs/statistics`

**Response 200:**
```json
{
  "total_jobs": 3,
  "completed": 2,
  "failed": 0,
  "cancelled": 1,
  "in_progress": 0,
  "pending": 0,
  "total_records_extracted": 10,
  "avg_extraction_time_seconds": 12.4
}
```

---

## Common Error Response Format
All errors follow this structure:
```json
{
  "error": "ERROR_CODE",
  "message": "Human readable description",
  "detail": {}
}
```

## Swagger / OpenAPI Docs
Available at: `http://localhost:5200/docs`
ReDoc available at: `http://localhost:5200/redoc`
