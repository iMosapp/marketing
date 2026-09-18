# I'm On Social Developer API

**Version:** v1 · **Base URL:** `https://app.imonsocial.com/api/v1` · **Auth:** `X-API-Key` header · **Format:** JSON

This is the complete reference for connecting a CRM, DMS, marketing platform or automation tool to I'm On Social. Everything on this page is live and testable today. If you are a CRM vendor's engineer, start with the [Quick start](#quick-start), then read [Webhooks](#webhooks-push-from-im-on-social-to-you) and [Sync patterns](#sync-patterns).

> **Try it in the browser:** an interactive console with every endpoint is at `https://app.imonsocial.com/api/public/reference`. Paste your key under **Authorize** and run real calls. The machine-readable schema is at `/api/public/openapi-v1.json` (import it into Postman or Insomnia, or generate a client).

---

## What you can do

| Direction | Capability | How |
|---|---|---|
| **Pull** | Contacts with tags, vehicle, notes, sold records, owner rep, your own CRM ids | `GET /api/v1/contacts`, `GET /api/v1/export/contacts` |
| **Pull** | Full text/email thread per customer, call logs with transcripts and AI summaries | `GET /api/v1/contacts/{id}/messages`, `/calls` |
| **Pull** | Activity timeline (cards, review requests, notes, sales, tasks) | `GET /api/v1/contacts/{id}/events` |
| **Push** | Create or update customers without creating duplicates | `POST /api/v1/contacts` (upsert) |
| **Push** | Notes, tags, timeline events, sold records, follow-up tasks | `POST .../notes`, `/tags`, `/events`, `/purchases`, `POST /api/v1/tasks` |
| **Push** | Send a real text from the rep's number | `POST /api/v1/contacts/{id}/messages` |
| **Real time** | Be told within a minute when anything changes (new contact, text in/out, call, sale, note, task) | [Webhooks](#webhooks-push-from-im-on-social-to-you) |
| **Leads** | Deliver internet leads into a rep's inbox (ADF/XML, JSON, email) | [Lead intake](#lead-intake-adfxml-json-email) |

---

## Quick start

**1. Get a key.** A dealership admin creates it in the app: **Tools → Integrations → API Keys → New key**. Pick a name (e.g. "HubSpot sync"), scopes (`read`, `write`), and an expiry. The key is shown once and stored hashed on our side. One key = one store. Ask for an **organization** key if you need every store in a dealer group.

**2. Confirm it works.**

```bash
curl https://app.imonsocial.com/api/v1/me \
  -H "X-API-Key: imos_live_xxxxxxxxxxxxxxxxxxxx"
```

```json
{
  "key_name": "HubSpot sync",
  "scopes": ["read", "write"],
  "store": {"id": "69a0b7095fddcede09591668", "name": "Riverton Chevrolet"},
  "organization": {"id": "org_001", "name": "Riverton Auto Group"},
  "stores_visible": 1,
  "users_visible": 14,
  "rate_limit_per_minute": 120,
  "docs": "https://www.imonsocial.com/developers"
}
```

**3. Pull contacts changed in the last day.**

```bash
curl "https://app.imonsocial.com/api/v1/contacts?updated_since=2026-09-17T00:00:00Z&limit=100" \
  -H "X-API-Key: $KEY"
```

**4. Push a customer from your CRM (idempotent).**

```bash
curl -X POST https://app.imonsocial.com/api/v1/contacts \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jordan", "last_name": "Lee",
    "phone": "(801) 555-0142", "email": "jordan@example.com",
    "source": "hubspot", "external_ids": {"hubspot": "1234567"},
    "tags": ["internet lead"], "vehicle_interest": "2024 Silverado LT"
  }'
```

```json
{"id": "6aad4836de3a277d2522915c", "created": true, "message": "Contact created"}
```

Send the same body again and you get `"created": false` with the same `id`: we matched it by `external_ids.hubspot`, then phone, then email. You can never create a duplicate through the API.

**5. Subscribe to changes.**

```bash
curl -X POST https://app.imonsocial.com/api/v1/webhooks \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"url": "https://crm.example.com/imos-webhook", "events": ["*"], "secret": "choose-a-long-random-string", "description": "CRM sync"}'
```

Then `POST /api/v1/webhooks/{id}/test` sends a signed `ping` immediately so you can verify your endpoint end to end.

---

## Authentication

Every request carries the key in a header:

```
X-API-Key: imos_live_xxxxxxxxxxxxxxxxxxxx
```

| | |
|---|---|
| **Where keys come from** | Created by a dealership admin in the app (Tools → Integrations → API Keys). We never email keys. |
| **Scope of data** | A key sees exactly one store's data (contacts owned by that store's reps, their conversations, calls, tasks). An organization key sees every store in the group. Nothing else is reachable, not even by id. |
| **Permissions** | `read` (all GETs) and `write` (all POST/PUT/DELETE). A read-only key gets `403` on writes. |
| **Expiry** | Optional, set at creation (default 365 days). Expired → `401 API key expired`. |
| **Revocation** | Instant, from the same screen. Revoked → `401 API key revoked`. |
| **Storage** | Only a SHA-256 hash is stored. If a key is lost, revoke it and create a new one. |
| **Transport** | HTTPS only. Keys sent over plain HTTP are rejected by the edge. |

## Rate limits, errors, conventions

- **Rate limit:** 120 requests per minute per key. Over the limit you get `429` with a `Retry-After: 60` header. Bulk pulls should use `limit=200` and `offset`, or `GET /export/contacts`.
- **Errors** are JSON: `{"detail": "human readable reason"}` with the standard status: `400` bad input, `401` bad/missing key, `403` read-only key, `404` not found *or not in your store* (we do not reveal that a record exists elsewhere), `429` rate limited, `500` our fault (logged, contact support with the timestamp).
- **Pagination:** `limit` (max 200; 500 on some sub-resources) and `offset`. Responses include `total`.
- **Timestamps:** ISO-8601 in UTC, e.g. `2026-09-18T14:03:22.104000+00:00`. Send filters like `updated_since` in the same format (`Z` suffix accepted).
- **IDs:** 24-character hex strings. Store them; they never change.
- **Phone numbers:** accepted in any format, stored as E.164 (`+18015550142`). Matching ignores formatting.
- **Soft deletes:** `DELETE` hides a contact from the rep and from lists; history is kept and the record can be restored by an admin.

---

## Data model

### Contact

| Field | Type | Notes |
|---|---|---|
| `id` | string | I'm On Social id |
| `first_name`, `last_name` | string | |
| `phone` | string | E.164. Primary mobile. |
| `phones` | array | Extra numbers `[{"label": "work", "number": "+1..."}]` |
| `email`, `email_work` | string | |
| `emails` | array | Extra addresses |
| `tags` | array of strings | Free-form. `sold` is special: it marks a customer as purchased and starts the sold follow-up cadence. |
| `source` | string | Where the record came from: `manual`, `csv`, `phone_contacts`, `lead_form`, `referral`, `api`, or the name you send (e.g. `hubspot`). |
| `external_id` | string | A single foreign id (legacy). Prefer `external_ids`. |
| `external_ids` | object | Your ids keyed by system: `{"hubspot": "1234567", "vinsolutions": "88-1002"}`. Used for matching on upsert and returned on every read. |
| `vehicle` | string | What they own / bought (derived from the newest purchase record) |
| `vehicle_interest` | string | What they said they want |
| `notes` | string | The rep's running notes. API notes are appended with a date and source prefix, never overwritten. |
| `purchase_history` | array | Sold records `[{"id", "title", "category", "date": "YYYY-MM-DD", "notes"}]` |
| `date_sold` | date | Most recent sale |
| `sold_count` | number | |
| `user_id` | string | Owning rep (see Users) |
| `store_id` | string | |
| `status` | string | `active`, `hidden` |
| `birthday`, `anniversary`, `custom_dates` | | Drive automated cards |
| `occupation`, `employer`, `organization_name`, `personal_details` | | Personal intelligence captured by the rep or Jessi |
| `address_street`, `address_city`, `address_state`, `address_zip` | string | |
| `photo_url` | string | |
| `created_at`, `updated_at` | datetime | `updated_at` changes on any edit, tag, note or sale, so it is the field to poll |

Writable through the API: `first_name`, `last_name`, `phone`, `phones`, `email`, `email_work`, `emails`, `organization_name`, `occupation`, `employer`, `vehicle`, `vehicle_interest`, `notes`, `tags`, `source`, `external_id`, `external_ids`, `birthday`, `anniversary`, `address_*`, `personal_details`, `photo_url`, `customer_number`, plus `owner_user_id` / `owner_email` to assign the rep.

### Message

`id`, `conversation_id`, `user_id` (rep), `direction` (`inbound` | `outbound`), `sender` (`user` | `contact` | `ai`), `channel` (`sms` | `email`), `content`, `media_url`, `ai_generated`, `status`, `timestamp`.

### Conversation

`id`, `user_id`, `contact_id`, `contact_phone`, `contact_name`, `status`, `ai_enabled`, `last_message_at`. One conversation per rep-customer pair.

### Call

`id`, `contact_id`, `user_id`, `direction`, `duration_s`, `outcome`, `connected`, `recording_url`, `transcript`, `ai_summary`, `created_at`.

### Timeline event

`id`, `contact_id`, `user_id`, `event_type` (e.g. `personal_sms`, `email_sent`, `call_made`, `digital_card_sent`, `review_request_sent`, `note_added`, `purchase_added`, `task_completed`, or your own via the API), `title`, `description`, `metadata`, `source`, `timestamp`.

### Task

`id`, `user_id`, `contact_id`, `type` (`follow_up`, `callback`, `appointment`, `manual`...), `title`, `description`, `due_date`, `priority`, `status` (`pending`, `completed`), `source`, `idempotency_key`, `created_at`, `completed_at`.

### User (rep)

`id`, `first_name`, `last_name`, `name`, `email`, `phone`, `role` (`user`, `store_manager`, `org_admin`), `title`, `status`, `store_id`, `organization_id`, `twilio_number` (the texting number customers see). Passwords and tokens are never returned.

---

## Endpoints

All paths below are relative to `https://app.imonsocial.com`.

### Identity

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/me` | Key name, scopes, the store/organization it can see, rate limit |

### Contacts

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/contacts` | List / search. Query: `search`, `phone`, `email`, `external_id`, `tag`, `source`, `owner_user_id`, `updated_since`, `limit`, `offset` |
| GET | `/api/v1/contacts/{contact_id}` | One contact with every field |
| POST | `/api/v1/contacts` | **Upsert.** Body: any writable field. Requires `phone`, `email` or `external_id`. Returns `{id, created}` |
| PUT | `/api/v1/contacts/{contact_id}` | Update fields. `external_ids` are merged, not replaced |
| DELETE | `/api/v1/contacts/{contact_id}` | Hide (soft delete) |
| POST | `/api/v1/contacts/{contact_id}/tags` | Body `{"tag": "VIP"}` → returns the tag list |
| DELETE | `/api/v1/contacts/{contact_id}/tags/{tag}` | Remove a tag |
| GET | `/api/v1/contacts/{contact_id}/notes` | The notes text |
| POST | `/api/v1/contacts/{contact_id}/notes` | Body `{"note": "...", "source": "HubSpot"}` → appends `[Sep 18, 2026 via HubSpot] ...` and logs a `note_added` event |
| GET | `/api/v1/contacts/{contact_id}/events` | Timeline, newest first |
| POST | `/api/v1/contacts/{contact_id}/events` | Body `{"event_type": "appraisal_completed", "title": "...", "description": "...", "metadata": {}}` |
| GET | `/api/v1/contacts/{contact_id}/messages` | Every text/email with this customer across the rep's conversations |
| POST | `/api/v1/contacts/{contact_id}/messages` | Body `{"content": "...", "user_id": "<rep, optional>", "channel": "sms"}` → sends for real from the rep's number |
| GET | `/api/v1/contacts/{contact_id}/calls` | Call logs with transcript + AI summary |
| GET | `/api/v1/contacts/{contact_id}/purchases` | Sold records |
| POST | `/api/v1/contacts/{contact_id}/purchases` | Body `{"title": "2024 Chevy Tahoe", "category": "vehicle", "date": "2026-09-01", "notes": "Traded a 2018 Silverado"}` → merges with a same-day record, tags `sold` |

**Upsert matching order** (`POST /api/v1/contacts`): `external_id` / `crm_id` → any value in `external_ids` → phone (last 10 digits) → email → exact first+last name with no conflicting phone. On a match we `$set` the fields you sent, add (never remove) tags, merge `external_ids`, append `notes`, and return `created: false`.

**Owner assignment:** send `owner_user_id` (from `GET /api/v1/users`) or `owner_email`. If omitted, new contacts go to the key creator, else the store manager.

### Tasks

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/tasks` | Query: `status`, `user_id`, `contact_id`, `due_after`, `due_before`, `limit`, `offset` |
| POST | `/api/v1/tasks` | Body `{"contact_id", "title", "due_date", "type": "follow_up", "priority": "medium", "user_id": "<rep, optional>", "idempotency_key": "<your id>"}` |

Tasks show on the rep's **Today** list in the app. Send `idempotency_key` (your task id) so retries never double up.

### People and places

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/users` | Reps and managers in scope. Query: `role`, `status`, `limit`, `offset` |
| GET | `/api/v1/users/{user_id}` | One user |
| GET | `/api/v1/stores` | Stores in scope |
| GET | `/api/v1/organizations` | The dealer group |

### Conversations

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/conversations` | Query: `user_id`, `contact_id`, `updated_since`, `limit`, `offset` |
| GET | `/api/v1/conversations/{conversation_id}/messages` | Messages oldest → newest |

### Export

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/export/contacts` | Initial load. `format=json` (default) or `format=csv`, `limit` up to 20,000 |

### Webhooks

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/webhooks/events` | Event catalog with descriptions (no key needed) |
| GET | `/api/v1/webhooks` | Your subscriptions |
| POST | `/api/v1/webhooks` | Body `{"url": "https://...", "events": ["contact.created", "message.received"] or ["*"], "secret": "...", "description": "..."}` |
| DELETE | `/api/v1/webhooks/{webhook_id}` | Remove |
| GET | `/api/v1/webhooks/{webhook_id}/deliveries` | Last 200 delivery attempts with status codes and errors |
| POST | `/api/v1/webhooks/{webhook_id}/test` | Sends a signed `ping` now and returns your server's response |

---

## Webhooks (push from I'm On Social to you)

Register an HTTPS URL and we POST events to it. Events are produced by a change feed that runs **every 60 seconds** over everything that happened in the store, regardless of how it happened (rep typed it, CSV import, lead source, Twilio, Jessi, or your own API call). Expect delivery within about a minute of the change.

### Event catalog

| Event | Fires when | `data` |
|---|---|---|
| `contact.created` | A contact was added by any path | Contact (see below) |
| `contact.updated` | Fields, tags, vehicle, notes, owner or sold data changed | Contact |
| `contact.deleted` | Contact hidden/removed | Contact |
| `message.sent` | A rep, campaign or Jessi sent a text/email | Message + `contact_id` |
| `message.received` | Customer replied | Message + `contact_id` |
| `call.logged` | A call ended (transcript/summary included when available) | Call |
| `note.added` | A note was added | Timeline event |
| `deal.closed` | A sale was recorded | Timeline event (`event_type: purchase_added`) |
| `task.created` / `task.completed` | Follow-up created / done | Task |
| `activity.logged` | Any other touchpoint: card sent, review request, congrats card, link click | Timeline event |
| `appointment.created`, `review.submitted`, `campaign.enrolled`, `campaign.completed`, `user.created`, `user.deactivated` | As named | Object |
| `ping` | You called `/test` | `{"message": "Hello from I'm On Social"}` |

Subscribe to `["*"]` for everything.

### Envelope

```json
{
  "id": "evt_3f9c1a7e2b8d4c5e6f70",
  "event": "message.received",
  "timestamp": "2026-09-18T14:03:22.104000+00:00",
  "store_id": "69a0b7095fddcede09591668",
  "organization_id": "org_001",
  "data": {
    "id": "6aad4836de3a277d2522915c",
    "contact_id": "69a496841603573df5a41723",
    "conversation_id": "69a4a1c0e2f3...",
    "user_id": "69a5303dbd4ef63b7ef776d4",
    "direction": "inbound",
    "sender": "contact",
    "channel": "sms",
    "content": "Yes, Saturday at 10 works",
    "media_url": null,
    "timestamp": "2026-09-18T14:02:58+00:00"
  }
}
```

Contact payloads carry: `id, first_name, last_name, phone, email, tags, source, external_id, external_ids, vehicle, vehicle_interest, notes, owner_user_id, store_id, status, date_sold, purchase_history, photo_url, created_at, updated_at`.

### Headers and signature

```
Content-Type: application/json
User-Agent: ImOnSocial-Webhooks/1.0
X-IMOS-Event: message.received
X-IMOS-Delivery: evt_3f9c1a7e2b8d4c5e6f70
X-IMOS-Signature: sha256=<hex HMAC-SHA256 of the raw request body using your secret>
```

Verify before trusting the payload:

```python
import hmac, hashlib
def verify(secret: str, raw_body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")
```

```javascript
const crypto = require("crypto");
function verify(secret, rawBody, header) {
  const expected = "sha256=" + crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(header || ""));
}
```

Compute the HMAC over the **raw bytes** you received (do not re-serialize the JSON).

### Delivery rules

- Respond with any `2xx` within 10 seconds. Do your processing after you respond.
- Each event is delivered **once per subscription**. A non-2xx or timeout is logged with the response (`GET /api/v1/webhooks/{id}/deliveries`) and increments `failure_count`; there is no automatic retry. Reconcile gaps with `GET /api/v1/contacts?updated_since=...`.
- Order is by change time within a batch but not guaranteed across batches. Use `data.updated_at` / `data.timestamp`.
- `X-IMOS-Delivery` (= `id`) is unique per event: use it as an idempotency key.
- **Avoid loops:** when you push a record through the API, the resulting `contact.created`/`contact.updated` event will come back to you a minute later. Ignore events whose `data.source` is your system name, or whose `data.external_ids` already contains your id with a matching `updated_at`.

---

## Lead intake (ADF/XML, JSON, email)

Internet leads enter through **Lead Sources**. A dealership admin creates one in **Tools → Leads → Lead Source Config** (or **Connect Zapier / Make**) and gets a `source_id` plus an optional per-source API key. Each source routes to the right store and rep, deduplicates against existing customers, and kicks off speed-to-lead.

| Format | Endpoint | Auth |
|---|---|---|
| **ADF/XML** (Cars.com, AutoTrader, OEM portals, most automotive providers) | `POST /api/leads/adf?source_id=<source_id>` — raw XML body or form field `XML=` | Optional `X-API-Key` header (the lead source's key) |
| **JSON / form webhook** (your CRM, website forms, Zapier, Make, n8n) | `POST /api/leads/webhook/<source_id>` | `X-API-Key: <source key>` header or `?api_key=` |
| **Email** (ADF delivered by email, the industry default) | `POST /api/leads/email-inbound?source_id=<source_id>` from any inbound-mail service (SendGrid Inbound Parse, Mailgun Routes, CloudMailin, Zapier Email Parser). Every text field and attachment is scanned for ADF | Per source |

The JSON webhook accepts any field names; these aliases are mapped automatically:

| Standard field | Accepted aliases |
|---|---|
| `phone` (required) | `phone`, `phone_number`, `mobile`, `cell` |
| `first_name` / `last_name` | `firstname`, `fname` / `lastname`, `lname` |
| `full_name` | `name`, `full_name`, `customer_name` (split for you) |
| `email` | `email`, `email_address` |
| `vehicle_year`, `vehicle_make`, `vehicle_model` | `year`, `make`, `model` |
| `vehicle_stock`, `vehicle_vin` | `stock`, `stock_number`, `vin` |
| `comments` | `comments`, `message`, `notes`, `inquiry` |
| `source_name` | `source`, `lead_source`, `provider` |
| `is_test` | `is_test`, `test` (true keeps the lead out of reporting) |

Sample:

```bash
curl -X POST "https://app.imonsocial.com/api/leads/webhook/<source_id>" \
  -H "X-API-Key: <source key>" -H "Content-Type: application/json" \
  -d '{"first_name":"Jordan","last_name":"Lee","phone":"5551234567","email":"jordan@example.com","year":"2024","make":"Ford","model":"F-150","stock_number":"F24-118","comments":"Is this truck still available?","is_test":true}'
```

ADF returns a plain-text acknowledgement (per the ADF spec); JSON returns `{"lead_id", "contact_id", "status"}`.

---

## Zapier, Make, n8n

- **Into I'm On Social:** use the JSON webhook above as the action ("Webhooks by Zapier → POST"). The **Connect Zapier / Make** screen in the app shows the exact URL, key and a sample payload for each source, and has a "Send test lead" button.
- **Out of I'm On Social:** create a "Catch Hook" trigger in Zapier (or a Webhook module in Make), then register that URL with `POST /api/v1/webhooks`, or from the app's **Tools → Integrations → Webhooks** tab. Use `/test` to fire a `ping` so the tool can learn the payload shape.

---

## Sync patterns

**Initial load (CRM ← I'm On Social):** `GET /api/v1/export/contacts?format=json` (or CSV) once, then store our `id` on your record. For threads and calls, iterate `GET /api/v1/contacts/{id}/messages` and `/calls` for the customers you care about.

**Incremental pull:** every N minutes call `GET /api/v1/contacts?updated_since=<last run>&limit=200` and page with `offset`. `updated_at` moves on any edit, tag, note or sale.

**Real-time (recommended):** subscribe to webhooks for `["*"]` and treat the payload as the new truth for that record; fall back to the incremental pull nightly to reconcile.

**Push (I'm On Social ← CRM):** upsert with `external_ids` = your id and `source` = your system name. Send only the fields you own. Tags are additive; to remove one use `DELETE .../tags/{tag}`. For notes use `POST .../notes` (append) rather than writing the `notes` field.

**Field ownership / conflicts:** last write wins per field. Keep the CRM authoritative for identity and deal data, and I'm On Social authoritative for `tags`, `notes`, `vehicle_interest`, `personal_details` and the timeline (the rep is typing these on the lot).

**Photos and files:** `photo_url` is a public URL you can store or mirror. Message `media_url` values are public for the life of the message.

---

## Testing checklist

1. `GET /api/v1/me` returns your store. If `users_visible` is 0, the store has no reps yet: add one in the app.
2. Create a contact with phone `+1 500 555 01xx` (Twilio test range, never a real person) and `"tags": ["api-test"]`, then delete it. Filter test data with `?tag=api-test`.
3. Register a webhook to a request bin, call `/test`, confirm the signature verifies.
4. Edit that contact in the app, wait a minute, confirm `contact.updated` arrives.
5. Send a lead with `"is_test": true` to your source URL and watch it appear in the rep's inbox.
6. Revoke the test key and confirm `401`.

Need a sandbox store or an organization-level key? Email **support@imonsocial.com** with your company, use case and the dealership you are integrating for.

---

## Changelog

- **2026-09 (v1):** Tenant-scoped keys (store / organization), hashed key storage, `GET /me`, upsert with `external_ids`, notes append, purchases, tasks, contact messages/calls, webhook management via API, change-feed webhooks for every event, signed deliveries, OpenAPI + interactive console, CSV export.
