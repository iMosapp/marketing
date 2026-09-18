# CRM Integration Guide

**Who this is for:** the programmer at a CRM vendor, a dealer group's IT team, or an automation consultant who has been asked "make I'm On Social and our CRM talk to each other." It explains the *how* in plain English and points at the exact endpoints. The full field-by-field reference is in the [API Reference](https://www.imonsocial.com/developers?doc=api-reference).

**Time to first sync:** about an afternoon for a one-way feed, two to three days for a solid two-way sync with a test store.

---

## The one-paragraph version

I'm On Social is where the salesperson lives all day: texting customers from their own number, logging calls, voice notes, sold records, follow-ups, birthday and anniversary cards, and their AI assistant Jessi. Your CRM is where the dealership lives: deals, desking, F&I, inventory, reporting. A good integration lets each system keep doing what it is good at and copies the *relationship* data across so nobody types anything twice. Concretely: **customers and deal status flow from the CRM into I'm On Social; texts, calls, notes, tags and sold records flow from I'm On Social back into the CRM.**

---

## What moves, and which way

| Data | CRM -> I'm On Social | I'm On Social -> CRM |
|---|---|---|
| Customer record (name, phone, email, address) | `POST /api/v1/contacts` (upsert) | `contact.created` / `contact.updated` webhooks, `GET /api/v1/contacts?updated_since=` |
| Assigned salesperson | `owner_email` on the upsert | `owner_user_id` on every contact payload (map through `GET /api/v1/users`) |
| Deal / sold | `POST /api/v1/contacts/{id}/purchases` | `deal.closed` webhook |
| Notes | `POST /api/v1/contacts/{id}/notes` (appends) | `note.added` webhook, or `GET .../notes` |
| Texts and emails with the customer | `POST /api/v1/contacts/{id}/messages` (sends for real, from the rep's number) | `message.sent` / `message.received` webhooks, `GET .../messages` |
| Calls | not applicable | `call.logged` webhook (duration, outcome, transcript, AI summary) |
| Follow-up tasks | `POST /api/v1/tasks` (shows on the rep's Today list) | `task.created` / `task.completed` webhooks |
| Tags / segments | `tags` on upsert (additive), `POST .../tags` | `contact.updated` carries the full tag list |
| Internet leads | `POST /api/leads/adf` (ADF/XML) or `POST /api/leads/webhook/{source_id}` (JSON) | `contact.created` with `source` = the provider name |
| Anything else that happened in your system | `POST /api/v1/contacts/{id}/events` (shows on the customer's timeline in the app) | `activity.logged` webhook |

Everything above is live today. Nothing in this guide requires a partnership agreement with us; a dealership admin creates an API key in the app and hands it to you.

---

## Architecture in one picture

```
   YOUR CRM                                  I'M ON SOCIAL
 ┌───────────────┐   POST /api/v1/contacts    ┌────────────────────┐
 │ Customer saved│ ─────────────────────────> │ Contact (upsert,   │
 │ Deal closed   │   POST .../purchases       │ no duplicates)     │
 │ Task assigned │   POST /api/v1/tasks       │                    │
 └───────────────┘                            │  Rep texts, calls, │
                                              │  notes, tags, sells│
 ┌───────────────┐   webhook POST (signed)    │                    │
 │ Your endpoint │ <───────────────────────── │  Change feed (60 s)│
 │ /imos-webhook │   contact.updated,         └────────────────────┘
 └───────────────┘   message.received, ...
        │
        └── nightly: GET /api/v1/contacts?updated_since=<24h ago>  (reconcile)
```

Three moving parts:

1. **Push** (CRM -> us): call our REST API with an `X-API-Key` header whenever something changes on your side.
2. **Webhooks** (us -> CRM): we POST every change in the store to your URL within about a minute, signed with a shared secret.
3. **Reconcile**: once a day, pull `updated_since` and fix anything a webhook missed.

---

## Step by step

### 1. Get a key from the dealership

The store's admin opens **Tools -> Integrations -> API Keys -> New key**, names it after your product, gives it `read` + `write`, and sends you the key. It starts with `imos_live_`. One key sees one store. For a dealer group ask them (or us) for an **organization** key.

Sanity check:

```bash
curl https://app.imonsocial.com/api/v1/me -H "X-API-Key: $KEY"
```

You should see the store name and `users_visible` > 0.

### 2. Map the salespeople

Pull `GET /api/v1/users` once and store our `id` next to each rep in your system, matched by email. You will need it to assign ownership and to read `owner_user_id` on incoming payloads. New hires appear as `user.created` webhooks.

### 3. Initial load

- **Us -> you:** `GET /api/v1/export/contacts?format=json` (up to 20,000 in one call). Save our `id` on your record.
- **You -> us:** loop over your customers and `POST /api/v1/contacts` with `external_ids: {"<yoursystem>": "<your id>"}` and `source: "<yoursystem>"`. Rate limit is 120 requests per minute per key, so 5,000 customers take about 45 minutes; run it in the background and respect `429` + `Retry-After`.

Both directions are idempotent. Running the load twice changes nothing.

### 4. Turn on real time

```bash
curl -X POST https://app.imonsocial.com/api/v1/webhooks -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"url": "https://yourcrm.com/imos-webhook", "events": ["*"], "secret": "<32+ random chars>", "description": "<Your product> sync"}'
```

Then `POST /api/v1/webhooks/{id}/test` and confirm your endpoint verifies the `X-IMOS-Signature` header (HMAC-SHA256 over the raw body, see the API Reference for copy-paste code in Python and Node).

### 5. Wire your side's events to our API

Whenever a customer, deal, note or task changes in your CRM, make the matching call from the table above. Include `external_ids` every time so matching is exact.

### 6. Reconcile nightly

`GET /api/v1/contacts?updated_since=<yesterday>&limit=200` and page with `offset`. Treat each row as truth for the fields we own (see ownership below).

---

## Matching and duplicates (read this twice)

When you `POST /api/v1/contacts` we look for an existing customer in this order and update it instead of creating a new one:

1. `external_id` / any value in `external_ids` (your id, exact match)
2. Phone number, last 10 digits (formatting ignored)
3. Email, case-insensitive
4. Exact first + last name, only if there is no conflicting phone on file

The response tells you what happened: `{"id": "...", "created": true|false}`. Store the `id`.

On a match we **set** the scalar fields you sent, **add** tags (never remove), **merge** `external_ids`, and **append** notes. We never blank a field because you left it out of the body. Send only what you own.

Phone is the primary identity in this product (it is what the rep texts). If a customer has several numbers put the mobile in `phone` and the rest in `phones: [{"label": "work", "number": "..."}]`.

---

## Who owns which field

Two systems writing the same field is where syncs go wrong. Our recommendation, which is how the app itself behaves:

| Field group | Owner | Why |
|---|---|---|
| Identity: name, phone, email, address | **CRM** | Desking and F&I need the legal record |
| Deal data: sold date, vehicle, price, stock #, VIN | **CRM** (push to us via `/purchases`) | The deal is closed in the CRM |
| Assigned rep | **CRM** | Managers reassign in the CRM |
| `tags`, `vehicle_interest`, `personal_details`, `notes` | **I'm On Social** | The rep captures these on the lot and by voice |
| Texts, calls, voice notes, timeline | **I'm On Social** | They happen here |
| Follow-up tasks | Either, with `idempotency_key` | Both sides create them |

Last write wins per field. If you must let both sides edit names or emails, compare `updated_at` on the webhook payload against your own timestamp and keep the newer one.

---

## Avoiding echo loops

You push a customer -> a minute later `contact.created` arrives at your webhook -> naive code creates a duplicate on your side -> which pushes again. Two rules stop it:

- **Ignore your own writes:** every contact payload carries `source` and `external_ids`. If `data.external_ids["<yoursystem>"]` is set and `data.updated_at` is within a few seconds of your last push for that id, drop the event.
- **Idempotency:** `X-IMOS-Delivery` is unique per event. Keep the last 24 hours of ids and skip repeats. For tasks always send `idempotency_key`.

---

## Field maps for the big four

These are starting points; every CRM has custom fields, so expect to add rows.

### HubSpot

| I'm On Social | HubSpot object.property |
|---|---|
| `first_name`, `last_name` | Contact `firstname`, `lastname` |
| `phone` | Contact `mobilephone` (fallback `phone`) |
| `email` | Contact `email` |
| `external_ids.hubspot` | Contact `hs_object_id` |
| `owner_user_id` | Contact `hubspot_owner_id` (map by email through Owners API) |
| `tags` | A multi-checkbox property `imos_tags`, or Lists |
| `vehicle_interest`, `vehicle` | Custom properties `vehicle_interest`, `vehicle_owned` |
| `source` | `hs_lead_status` / `hs_analytics_source` (read-only in HubSpot; store in a custom property) |
| `note.added` webhook | `POST /crm/v3/objects/notes` + association to the contact |
| `message.sent/received` | Notes with a `[SMS in/out]` prefix, or the Communications object (`crm/v3/objects/communications`, `hs_communication_channel_type = SMS`) |
| `call.logged` | `POST /crm/v3/objects/calls` (`hs_call_body` = AI summary, `hs_call_duration` in ms, `hs_call_recording_url`) |
| `deal.closed` | Update the Deal to `closedwon`, or create one with `dealname` = the vehicle |
| `task.created` | `POST /crm/v3/objects/tasks` |

HubSpot -> us: subscribe to `contact.creation` / `contact.propertyChange` in a HubSpot app, or use a Workflow "Send webhook" action to `POST /api/v1/contacts` with the fields above.

### Salesforce

| I'm On Social | Salesforce |
|---|---|
| Customer | `Contact` (or `Lead` until converted; treat `Lead.ConvertedContactId` as the same person) |
| `first_name`, `last_name`, `email` | `FirstName`, `LastName`, `Email` |
| `phone` | `MobilePhone` (fallback `Phone`) |
| `external_ids.salesforce` | 18-character `Id`. Put our id in a custom External ID field `IMOS_Id__c` so you can upsert by it |
| `owner_user_id` | `OwnerId` (map `User.Email`) |
| `tags` | Multi-select picklist `IMOS_Tags__c` or Topics |
| `note.added`, messages, calls | `Task` records (`Subject` = "SMS in: ...", `TaskSubtype` = `Call`/`Email`, `CallDurationInSeconds`, `Description` = body or transcript) |
| `deal.closed` | `Opportunity` `StageName = Closed Won`, `CloseDate` = sold date |
| `task.created` | `Task` with `Status = Not Started`, `ActivityDate` = due date |

Salesforce -> us: Platform Events or an Apex trigger on `Contact` calling a Named Credential that POSTs to `/api/v1/contacts`; or Flow's HTTP Callout action.

### Zoho CRM

| I'm On Social | Zoho |
|---|---|
| Customer | `Contacts` module (or `Leads` before conversion) |
| `first_name`, `last_name`, `email` | `First_Name`, `Last_Name`, `Email` |
| `phone` | `Mobile` (fallback `Phone`) |
| `external_ids.zoho` | record `id` |
| `owner_user_id` | `Owner.id` (map `Owner.email`) |
| `tags` | Zoho Tags (`/Contacts/{id}/actions/add_tags`) |
| `note.added`, messages | `Notes` module attached to the contact (`Note_Title` = "SMS in", `Note_Content`) |
| `call.logged` | `Calls` module (`Call_Duration`, `Description`) |
| `deal.closed` | `Deals` with `Stage = Closed Won` |
| `task.created` | `Tasks` module |

Zoho -> us: Notifications API (`/actions/watch` on `Contacts`) or a Workflow Rule webhook.

### Pipedrive

| I'm On Social | Pipedrive |
|---|---|
| Customer | `persons` |
| `first_name` + `last_name` | `name` (we split on the last space if you only have `name`) |
| `phone`, `email` | `phone[]` (label `mobile`), `email[]` |
| `external_ids.pipedrive` | person `id` |
| `owner_user_id` | `owner_id` (map `users.email`) |
| `tags` | Custom field (multiple options) or Labels |
| `note.added`, messages | `notes` (`content`, `person_id`) |
| `call.logged` | `activities` with `type = call`, `duration`, `done = 1`, `note` = summary |
| `deal.closed` | `deals` `status = won`, `title` = vehicle |
| `task.created` | `activities` with `type = task`, `due_date` |

Pipedrive -> us: Webhooks (`event_action = added|updated`, `event_object = person`) pointing at your middleware, which upserts to `/api/v1/contacts`.

---

## Sending texts through the API (compliance)

`POST /api/v1/contacts/{id}/messages` sends a real SMS from the salesperson's number and it lands in their inbox thread like any other text. Rules that apply automatically: customers who texted STOP are skipped, quiet hours configured by the store are honored, and every message is logged on the timeline. Your responsibility: only send to customers who consented to texts from the dealership (TCPA / CTIA). Do not use the API for bulk marketing; that is what the app's campaign tools with opt-in tracking are for.

---

## Rate limits, retries, errors

- 120 requests per minute per key. Bulk loads: batch at 100 per minute and honor `Retry-After`.
- Webhooks are delivered once per event; a non-2xx from you is logged (`GET /api/v1/webhooks/{id}/deliveries`) and **not retried**. Your nightly `updated_since` pull is the safety net.
- Errors are JSON: `{"detail": "..."}`. `404` also means "exists but not in your store"; never treat it as "create it again".

---

## Go-live checklist

1. `GET /api/v1/me` shows the right store and `users_visible` matches the roster.
2. Reps mapped by email; unmatched reps listed for the store manager.
3. Initial load both ways done; spot-check 10 customers in both UIs.
4. Webhook registered, `/test` ping verified with the signature code (not just a 200).
5. Edit a customer in the app -> `contact.updated` arrives -> your record changes, no duplicate created.
6. Save a customer in your CRM -> it appears in the app under the right rep, once.
7. Mark a customer sold in the app -> `deal.closed` -> your deal/opportunity updates.
8. Text from the app -> `message.sent` logged on your side; reply from the customer -> `message.received`.
9. Echo test: push a record, wait 2 minutes, confirm your webhook handler ignored its own write.
10. Nightly reconcile scheduled; alert if it changes more than 5% of records (usually a mapping bug).
11. Test data cleaned up (`?tag=api-test`) and the test key revoked.
12. Store manager has a one-page "what syncs where" sheet (copy the table at the top of this guide).

---

## Automotive CRMs (VinSolutions, Elead, DealerSocket, DriveCentric, Reynolds, Tekion)

These CRMs do not offer public APIs; each has a partner program. What works **today** without certification:

- **Leads into the CRM:** the app can push any contact as a standards-compliant **ADF/XML lead** to the CRM's lead intake email address (contact page -> "Push to CRM", or bulk from the Contacts tab). Every automotive CRM accepts ADF by email.
- **Leads into I'm On Social:** point any lead provider or the CRM's lead forwarding at `POST /api/leads/adf?source_id=...` or the per-source intake email.
- **Reports and exports:** CSV in both directions.
- **Automation tools:** Zapier / Make connectors many dealers already run against their CRM, wired to our webhooks and API.

The certification path per vendor, with costs and timelines, is in [Automotive CRM Programs](https://www.imonsocial.com/developers?doc=automotive-crm-programs).

---

## Getting help

- Interactive console: `https://app.imonsocial.com/api/public/reference`
- OpenAPI schema: `https://app.imonsocial.com/api/public/openapi-v1.json`
- Sandbox store, organization keys, or a call with our engineers: **support@imonsocial.com** with your company, the CRM, and the dealership you are integrating for.
