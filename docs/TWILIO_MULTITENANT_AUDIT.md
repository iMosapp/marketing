# IMOS Twilio Audit (Phase 1 of the Multi-Tenant Provisioning outline)

Snapshot taken Jun 2026 on the preview build. Read-only audit; nothing was changed except the
one security hotfix noted at the bottom.

## 1. Credentials and Twilio client

| Item | Today | Outline wants |
|---|---|---|
| Account | ONE parent account. `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` from backend/.env, read in ~20 files (`services/twilio_service.py:16-30`, `services/twilio_compliance.py:201,503`, `routers/twilio_admin.py:24-30`, `routers/calls.py`, `routers/auth.py`, `services/live_host.py`, ...). | One subaccount per ORGANIZATION, parent account authenticates against it. |
| Subaccounts | None. `grep -i subaccount` = 0 hits. | `client.api.accounts.create(friendly_name)` per org. |
| Per-org fields | `models.Organization.twilio_account_sid`, `twilio_auth_token`, `ten_dlc_brand_id`, `ten_dlc_campaign_id`, `ten_dlc_status` are declared (`models.py:39-43`) but never read or written anywhere. Dead schema. | The 14-field org Twilio record. |
| Secrets to frontend | Never sent. Compliance `public()` masks the EIN. | Keep. |
| Encryption at rest | Fernet helper exists only for inventory feeds (`services/inventory_feed.py:26,89-97`). | Reuse for subaccount auth tokens (if stored at all). |
| Mock mode | `TWILIO_MOCK_MODE` is in .env but nothing reads it. Real switches: `TWILIO_ENABLED` (creds present) and the compliance `mode` setting `dry_run|mock|live`. | Keep `dry_run` adapter pattern for provisioning. |

## 2. Hierarchy and RBAC

- `organizations` (34 in preview) -> `stores` (30, `organization_id`) -> `users` (148, `organization_id`, `store_id`, `store_ids[]`, `role`).
- Roles: `super_admin`, `org_admin`, `store_manager`, `user` (`models.py:197,212`, `permissions.py ROLE_HIERARCHY`).
- Helpers: `routers/rbac.py require_role(min_role)`, `routers/compliance.py _admin(request, store, org_ok)` (super always, org_admin only for own org's stores).
- Preview data: 1 user with a Twilio number, 2 pool rows (lead-shop), 7 shared inboxes, 1 store with a compliance record. Production has more; the migration report must be run there.

## 3. Where phone numbers live today (fragmented, 6 places)

| Place | Fields | Written by | Notes |
|---|---|---|---|
| `users.twilio_number`, `twilio_number_sid`, `mvpline_number` | rep's own number | `routers/twilio_admin.py:304-462` (purchase/assign), `routers/admin_users.py:766-793` (deactivate -> pool) | the assignment source of truth for reps |
| `phone_number_pool` | `phone_number, twilio_sid, status pool/assigned/available/released, purpose, assigned_user_id, previous_store_id, monthly_cost_usd` | `twilio_admin.py:355`, `admin_users.py:665,771,975`, `services/shop_numbers.py:87`, `services/lead_shops.py`, `routers/mystery_shops.py:558` | two schemas; `status` vocabulary differs per writer |
| `shared_inboxes.phone_number` | store / team inbox number | `routers/shared_inboxes.py`, `services/inboxes.py` | not linked to the pool |
| mystery shop `shop_clients.from_number` | shopper caller ID | `services/shop_numbers.py` | separate lifecycle |
| lead shop pool `phone_number_pool purpose=lead_shop` | covert shopper numbers | `services/lead_shops.py:88-130` | only place with area-code auto-buy |
| `stores.compliance.numbers_plan` | release / port status per SID | `services/compliance_onboarding.py` | third tracker |
| `stores.twilio_phone_number` | declared `models.py:117`, never used | | no real store main number exists |

Webhooks: every purchase sets the same global `sms_url = {APP_URL}/api/webhooks/twilio/incoming` (`twilio_admin.py:304-355`, `shop_numbers.py:66-95`). Tenant resolution therefore happens inside the webhook by looking up the `To` number.

## 4. Inbound SMS (`routers/twilio_webhooks.py POST /incoming`, lines 104-1046)

Matches the outline: idempotent on `MessageSid` (`inbound_message_dedup` upsert + `messages.twilio_sid` fallback, 138-163); MMS stored (`media_urls, media_ids, media_types, has_media`, 166-172 + 431-452); STOP/START handled (728-771: `contacts.opted_out`, pauses enrollments, cancels AI queue, `add_dnc`, TwiML reply); notifications (rep SMS + push 592-662); VA gate (`ai_mode` per conversation / campaign `ai_assist_mode`, 663-874); contact scoped to `user_id`, conversation keyed `(rep_phone, contact_phone)`.

Resolution order today: lead-shop / text-shop / photo-request interceptors -> `shared_inboxes.phone_number` -> `users.twilio_number|mvpline_number` (no org filter, 240-243) -> `phone_number_pool status=pool` -> previous store's manager (250-266) -> **first super_admin/org_admin in the whole database (267-269)**.

Gaps: no Twilio signature validation on `/incoming`, `/status`, every voice/call webhook, `routers/dialer_webhooks.py`, `routers/lead_call_webhooks.py` (only `compliance.py:382 trusthub-status` validates); no Org/Location layer; global admin fallback; HELP keyword not handled; opt-out field split (`opted_out` main path vs `sms_opt_out` shared-inbox path `services/inboxes.py:506,542`); only `MediaUrl0-2` read; inbound rows have no `direction` field.

## 5. Outbound SMS

One wrapper exists: `services/twilio_service.send_sms(to, message, media_urls, from_phone)` (84-152): from = `from_phone` else `TWILIO_MESSAGING_SERVICE_SID` else `TWILIO_PHONE_NUMBER`; always adds `status_callback` -> `/api/webhooks/twilio/status`. It does NOT write `messages`, does not know org/user/contact, does not check opt-out or compliance.

~12 callers each insert their own `messages` row: `routers/messages.py:661,758,965,2223`, `routers/ai_reply.py:1136-1162,1402-1427`, `services/inboxes.py:872-880`, `scheduler.py:822,926,1259` (campaigns), `services/lead_flows.py:412-434`, `routers/lead_intake.py:977-1015,2630`, `services/mystery_shops.py`, `services/text_shops.py`, `routers/team_invite.py:584`, `routers/auth.py:884`, `services/compliance_onboarding.py:164`.

Raw bypasses of the wrapper (no status callback): `routers/lead_intake.py:2844`, `routers/twilio_webhooks.py:640,980`, `routers/auth.py:1466`.

Pre-send checks: opt-out only in `ai_reply.py:1054`, `inboxes.py:872`, `scheduler.py:1112`; quiet hours only for automated campaign steps (`scheduler.py:1163-1189`, 8am-9pm rep tz); no A2P/compliance gate anywhere; no caps.

Status callback `/status` (1047-1171): queued/sent/delivered/undelivered/failed -> `messages.twilio_status/status`, `error_code`, `error_message`; campaign/broadcast counters; auto text-only resend on MMS errors; rep failure push. Matches the outline.

`messages` schema drift: `sender` vs `direction` (only `lead_flows.py` and shared-inbox system rows set `direction`), `campaign_id/broadcast_id/has_media` only on campaign rows. `contact_events` (`utils/activity_log.py`) is written by messages/ai_reply/lead_flows/lead_intake but NOT by campaign sends or shared-inbox sends.

## 6. Compliance (already built, store-keyed)

`services/twilio_compliance.py`: `stores.compliance` = business (legal_name, ein, business_type, website, address, company_type), rep (name, email, phone, title), campaign (use_case, description, message_flow, 3 samples, privacy/terms URLs, opt-in/out/help keywords + messages, links/phone flags), cnam; `mode dry_run|mock|live`; stages `draft -> profile -> a2p -> brand -> campaign -> complete`; `sids{}`, `statuses{}`, `history[]`, `events[]` (60 cap); LiveTwilio covers Trust Hub secondary profile, end users, address, supporting docs, evaluations, A2P trust product, brand, Messaging Service, `us_app_to_person` campaign, CNAM. `services/compliance_onboarding.py`: public token form, Day 2/5/9 reminders, digest, `numbers_view`, release / port status, port-out packet. `services/compliance_preflight.py`: EIN, entity suffix, address, website reachability, rep email domain, privacy/terms wording, description/flow, samples, CNAM (rules are inline Python, not table-driven). Router `routers/compliance.py` under `/admin/compliance` with `_admin()` gates; public `/public/a2p-onboarding/{token}`, `/public/port-out/{token}`; signed webhook `/webhooks/twilio/trusthub-status`. Scheduler polls every 10 min.

Numbers attached to the store's Messaging Service come from `users.twilio_number_sid` of reps in that store (`store_numbers()` 346-354, `_assign_new_numbers()` 518-532).

Gap vs outline: keyed per STORE not ORG; no subaccount step; no Messaging Service / phone numbers status in the status card; statuses are internal stage names, not the 7-value vocabulary; requirement rules are hard-coded.

## 7. Usage, audit, failure handling

- Usage: none. `msg.price`, `num_segments` never stored. `monthly_cost_usd` only for number rental in pool rows; `cost_usd` only for GPT-Live minutes. `routers/reports.py` counts `messages` rows only.
- Audit: no `audit_logs`. Only `stores.compliance.events`, `permission_audit_log` (permissions), `system_logs`, `contact_events`.
- Errors: compliance stores `error` + history; number ops raise 400/500 with Twilio text.

## 8. Admin UI

- `/admin/twilio-numbers` (list, search, purchase, assign, fix-webhook, release; Hub "Phone Numbers" tile), `/admin/compliance` + `/admin/compliance/{storeId}` (Hub "Texting Compliance" tile), `/inboxes` editor, `/admin/phone-assignments.tsx` (6-line stub).
- `/admin/organizations/[id].tsx` and `/admin/stores/[id].tsx` have zero Twilio / compliance wiring. No Organization -> Communications -> Twilio area. No customer-admin Communications area (org_admin only sees the compliance screen).

## 9. SECURITY FINDING (fixed in this session)

`routers/twilio_admin.py` (`/api/admin/twilio/*`: list numbers, search, PURCHASE, assign, fix-webhook, RELEASE) had **no authentication at all**; `curl` without a token returned 200 on preview. Locked to `super_admin` via `require_role`.

## 10. Outline coverage matrix

| Outline section | Exists | Missing |
|---|---|---|
| Org Twilio record | dead fields on model | subaccount SIDs, provisioning status/error, last synced, messaging ready |
| Phone number resource | pool + user fields (fragmented) | single `phone_numbers` collection with numberType/status/org/location/user |
| User phone assignment | assign/unassign/deactivate | org-owned lifecycle, reassignment history, service function |
| Inbound webhook | idempotent, MMS, STOP/START, notify, VA | signature check, org/location resolver, HELP, no global fallback |
| Outbound service | `send_sms` phone-only | `send_sms({org,user,contact,...})` writing messages + events + usage, opt-out/quiet/compliance gates |
| Status callbacks | done | usage from `NumSegments`/price |
| A2P compliance | full per-store flow, preflight, onboarding, port-out | org-level, subaccount, 7-value statuses, Messaging Ready, table-driven rules |
| Automated provisioning | compliance state machine | subaccount + number + webhook steps, Provision Twilio button, pause/resume |
| Admin UI | flat screens | Org -> Communications -> Twilio, customer admin area |
| Number search / area code | search by area code (super admin) | area-code suggestion from org/store/user location |
| Usage tracking | none | per org/location/user/number counters + cost |
| Audit log | compliance events only | `audit_logs` for every Twilio action |
| Migration | none | mapping report of existing numbers |
