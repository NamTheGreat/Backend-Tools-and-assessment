# HubSpot CRM API v3 - Deals Integration

## Authentication
- Method: Private App Access Tokens
- Header: `Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>`
- Token is generated from HubSpot Settings -> Integrations -> Private Apps
- Required scope: `crm.objects.deals.read`
- Token must be stored in `.env` as `HUBSPOT_ACCESS_TOKEN` - never committed to git

## Base URL
https://api.hubapi.com

## Deals Endpoint
GET /crm/v3/objects/deals

## Query Parameters
| Parameter | Type | Description | Default |
|---|---|---|---|
| limit | integer | Number of records per page (max 100) | 10 |
| after | string | Cursor for next page (from paging.next.after) | None |
| properties | string (comma-separated) | Deal properties to return | Basic fields only |
| archived | boolean | Include archived deals | false |

### Properties Used in This Service
dealname, amount, dealstage, pipeline, closedate, createdate,
hs_lastmodifieddate, hubspot_owner_id, description, hs_deal_stage_probability

## Sample Request
```bash
curl --request GET \
  --url 'https://api.hubapi.com/crm/v3/objects/deals?limit=100&properties=dealname,amount,dealstage,pipeline,closedate,createdate,hs_lastmodifieddate,hubspot_owner_id,description' \
  --header 'Authorization: Bearer pat-na2-XXXXXXXXXXXXXXXXXXXXXXXXXXXX'
```

## Sample Response
```json
{
  "results": [
    {
      "id": "12345",
      "properties": {
        "dealname": "Won Enterprise Contract",
        "amount": "75000",
        "dealstage": "closedwon",
        "pipeline": "default",
        "closedate": "2026-06-30T00:00:00.000Z",
        "createdate": "2026-06-14T10:00:00.000Z",
        "hs_lastmodifieddate": "2026-06-14T10:05:00.000Z",
        "hubspot_owner_id": "123456789",
        "description": null
      },
      "createdAt": "2026-06-14T10:00:00.000Z",
      "updatedAt": "2026-06-14T10:05:00.000Z",
      "archived": false
    }
  ],
  "paging": {
    "next": {
      "after": "NTI1Cg%3D%3D",
      "link": "https://api.hubapi.com/crm/v3/objects/deals?after=NTI1Cg%3D%3D"
    }
  }
}
```

## Pagination
- HubSpot uses cursor-based pagination
- If `paging.next.after` exists in response, use its value as the `after` param in the next request
- If `paging` key is absent or `paging.next` is absent, you have reached the last page
- Maximum `limit` per request is 100

## Rate Limits
- 150 requests per 10 seconds per token
- On HTTP 429: parse `Retry-After` header, sleep that many seconds, then retry
- Implement exponential backoff: wait 1s, 2s, 4s, 8s on repeated failures
- Log every rate limit hit

## Error Codes
| Code | Meaning | Action |
|---|---|---|
| 200 | Success | Process results |
| 400 | Bad request (invalid params) | Log and raise |
| 401 | Unauthorized (bad token) | Raise AuthenticationError |
| 403 | Forbidden (missing scope) | Raise with scope message |
| 429 | Rate limit exceeded | Sleep + retry |
| 500/503 | HubSpot server error | Retry with backoff (max 3 times) |

## All Available Deal Properties
dealname, amount, dealstage, pipeline, closedate, createdate,
hs_lastmodifieddate, hubspot_owner_id, description, hs_deal_stage_probability,
hs_is_closed, hs_is_closed_won, hs_num_associated_companies,
hs_num_associated_contacts, hs_object_id, hs_priority, hs_projected_amount,
hs_projected_amount_in_home_currency, num_notes, num_contacted_notes,
engagements_last_meeting_booked, hs_analytics_source, hs_campaign
