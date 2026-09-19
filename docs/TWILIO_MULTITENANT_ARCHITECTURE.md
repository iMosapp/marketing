# IMOS Twilio Multi-Tenant Architecture

Companion to `TWILIO_MULTITENANT_AUDIT.md` (what existed). This is what was built, how it maps to the outline, and what is left.

## Hierarchy

IMOS Platform (parent Twilio account) -> Organization (one Twilio **subaccount**, one Messaging Service, brand + campaign)
-> Locations = `stores` (compliance form lives here) -> Users (assigned numbers) -> Phone numbers (`phone_numbers` registry).

Twilio's ISV rule: the Secondary Customer Profile, A2P brand, campaign and Messaging Service are created **inside the customer's
subaccount with the subaccount's credentials**. `services/twilio_compliance.py` now runs each store's registration through
`twilio_tenant.client_for_store()` and stamps `compliance.account_sid` at submit, so a registration always stays in the account
it started in (legacy in-flight registrations keep using the parent).

## Data model

### `organizations.twilio` (services/twilio_tenant.py `defaults()`)

| field | meaning |
|---|---|
| enabled | subaccount exists |
| subaccount_sid, subaccount_friendly_name, subaccount_status | `IMOS {org name} ({org id})`; status active / suspended / closed |
| subaccount_auth_token_enc | Fernet-encrypted (key derived from `TWILIO_TOKEN_KEY` or `JWT_SECRET`), never returned by any API |
| messaging_service_sid | mirrored from the backing store's compliance record |
| compliance_profile_sid / _status, a2p_brand_sid / _status, a2p_campaign_sid / _status | mirrored; statuses use the 7-value vocabulary |
| compliance_store_id | which store's `compliance` record backs the org (pinned, else furthest along) |
| provisioning_status | NOT_STARTED, IN_PROGRESS, INFORMATION_REQUIRED, WAITING_APPROVAL, READY, ERROR |
| provisioning_step, provisioning_error | actionable text ("Complete and submit the compliance form for X: 3 fields still needed.") |
| provisioning_history[] | {at, step, status, note} capped at 80 |
| messaging_ready | campaign APPROVED + Messaging Service + every active number attached + subaccount not suspended |
| last_synced_at | |

Status vocabulary (`STATUS_LABEL`): NOT_STARTED, INFORMATION_REQUIRED, SUBMITTED, PENDING, APPROVED, REJECTED, ACTION_REQUIRED,
computed for: subaccount, compliance_profile (profile + A2P trust product), a2p_brand, a2p_campaign, messaging_service, phone_numbers.

### `phone_numbers` (services/phone_numbers.py)

`organization_id, location_id, assigned_user_id, twilio_phone_number_sid, twilio_account_sid, phone_number, friendly_name,
number_type (USER|STORE|SHARED|CAMPAIGN|VA), sms_enabled, mms_enabled, voice_enabled, messaging_service_sid,
incoming_sms_webhook, incoming_voice_webhook, status (AVAILABLE|ASSIGNED|SUSPENDED|RELEASED), monthly_cost_usd,
created_at, updated_at, assigned_at, suspended_at, released_at, previous_user_id, history[]`.

Every write mirrors the legacy fields so nothing else had to change: `users.twilio_number / mvpline_number / twilio_number_sid`
(ASSIGNED only) and a `phone_number_pool` row keyed by `twilio_sid` (status assigned / pool / suspended / released, `registry_id`).

### `audit_logs` (`twilio_tenant.audit`)

`{action, actor_id, actor_name, actor_role, organization_id, target{}, details{}, ok, error, at}`. Actions: subaccount_created /
adopted / dry_run / suspended / active, provisioning_started, provision_step, provisioning_error, compliance_submitted,
number_purchased / assigned / reassigned / unassigned / suspended / reactivated / released / imported, number_purchase_failed,
number_release_failed, inbound_unrouted, flags_changed. Org admins get a sanitized copy (no SIDs).

### `usage_daily` (`phone_numbers.record_usage`)

`{organization_id, location_id, user_id, phone_number, day}` with `$inc` sms_out, sms_in, mms_out, mms_in, segments_out,
segments_in, messages, cost_usd. Written by `twilio_service.send_sms` (outbound, `num_segments` from Twilio) and the inbound webhook.
`usage_summary(org, month)` rolls up totals, per number, per user, active numbers and rental estimate.

## Flows

**Provision Twilio** (`POST /api/admin/organizations/{org}/twilio/provision`, super admin): `twilio_tenant.provision` ->
`_recompute(create=True)`: subaccount (adopt by friendly name, else create; dry-run makes `ACdry…`), compliance mirror, attach
registry numbers to the Messaging Service, numbers status, readiness. Pauses at INFORMATION_REQUIRED (form not submitted / no
number) or WAITING_APPROVAL and resumes on every compliance change (`twilio_compliance.advance` -> `mirror_compliance`), every
Sync, and the 30-minute `twilio_tenant_sync` scheduler job. Never duplicates a resource: each step checks what is on file.
`auto_provision` flag runs it at `POST /api/setup-wizard/new-account`.

**Add number** (`GET .../numbers/suggest`, `GET .../numbers/search`, `POST .../numbers`): area-code suggestions from the rep's
cell, the store's line, the org phone, sibling locations and the org's existing numbers; search by area code / digits / city with
SMS-MMS-voice filters; purchase under the org's account with `sms_url=/api/webhooks/twilio/sms`, `voice_url=/api/webhooks/twilio/voice`,
attach to the Messaging Service, register, mirror, audit. Dry run when the compliance mode is `dry_run` (`PNdry…` SIDs).

**Assign / reassign / unassign / suspend / reactivate / release** (`POST .../numbers/{id}/…`, `DELETE …?confirm=true`):
organization owns the number; users are assigned. Release is super admin only and needs `confirm=true` (UI asks twice).
User deactivation (`DELETE /api/admin/users/{id}`) returns their registry numbers to AVAILABLE. Historical messages keep the
original sender.

**Inbound** (`POST /api/webhooks/twilio/sms` = alias of `/incoming`): signature check (`services/twilio_signature.py`, mode
`TWILIO_WEBHOOK_VALIDATION=off|log|enforce`, default `log`; token = subaccount's when `AccountSid` is a subaccount) ->
MessageSid dedupe -> interceptors (lead shops, text shops, photo request) -> shared inbox -> **registry** (number -> org ->
location -> user; STORE/SHARED/SUSPENDED numbers go to the location's manager, else the org admin) -> legacy
`users.twilio_number` -> pool -> platform super admin only (audited as `inbound_unrouted`). Messages carry `direction: inbound`,
`organization_id`, `location_id`, `phone_number_id`. STOP sets `opted_out` + `sms_opt_out` (both paths); START clears both;
HELP / INFO answers with the store's registered HELP message or a compliant default. Up to 10 MMS attachments.

**Outbound** (`twilio_service.send_sms`): unchanged signature plus optional `org_id / user_id / contact_id`; sends from a
subaccount number with that subaccount's credentials; records usage; when the `enforce_ready` flag is on, a registry number whose
organization is not MESSAGING READY is refused with an actionable reason (legacy numbers are never blocked).

## Admin UI

- Super admin: Admin -> Organizations -> [Organization] -> **Communications** tile -> `/admin/org-twilio/{orgId}`: MESSAGING READY
  banner + 6 resource statuses, Provisioning card (Provision / Sync / suspend subaccount / history), Phone numbers (add, assign,
  reassign, unassign, suspend, release with double confirm), Compliance by location, Usage, Audit log, Webhooks.
- Org admin: Tools -> Set Up -> **Communications** (same screen, no SIDs / parent account / history / release / suspend).
- Super admin: Tools -> **Twilio Migration** (`/admin/twilio-migration`): read-only mapping of every number (Twilio inventory +
  users + shared inboxes + pool + shop clients + registry) with issues, one-tap import into the registry (no Twilio writes), and
  the global flags (`enforce_ready`, `auto_provision`, validation mode). Also reachable from Phone Numbers -> Migration.

## Outline phases

| Phase | Status |
|---|---|
| 1 Audit + data model | done (`docs/TWILIO_MULTITENANT_AUDIT.md`, this file, registry + org record + audit + usage collections) |
| 2 Subaccount per org | done (dry-run tested; first live subaccount happens when the mode is `live`) |
| 3 Number provisioning / assignment | done |
| 4 Inbound / outbound routing | done: registry-first resolver, signature validation (log mode), HELP, opt-out unification, subaccount send credentials. Still legacy: ~12 callers write `messages` themselves (schema drift) |
| 5 Messaging Service | mirrored from compliance, numbers attached on purchase / provision |
| 6 A2P compliance workflow | existing per-store flow now runs in the org's subaccount and feeds the org statuses; requirements are still hard-coded in `compliance_preflight.py` |
| 7 Usage tracking | counts + segments per org / location / user / number; Twilio price not yet pulled |
| 8 Automated onboarding | `auto_provision` flag at signup (off by default) |
| 9 Migration tools | report + import; nothing is moved or released |
| 10 Rollout | preview tested in dry run; production: import the report, provision one pilot org, flip validation to `enforce` after the logs are clean, then `enforce_ready` once pilots are READY |

## Not done / next

- Twilio message price pull for `usage_daily.cost_usd` (needs a fetch after delivery or the Usage Records API).
- One writer for `messages` (`direction`, `organization_id`, `campaign_id` on every row) and `contact_events` for campaign sends.
- Table-driven compliance requirements (`compliance_preflight.py` rules as data).
- Voice / dialer / lead-call webhooks still skip signature validation (only SMS + status use `twilio_signature`).
- Org-level compliance form when a group has one EIN across rooftops (today one store's record backs the org).
