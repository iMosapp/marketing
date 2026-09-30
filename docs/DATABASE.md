# IMOS Database

MongoDB, accessed asynchronously with Motor. One database per environment (`DB_NAME`); production data lives in
an Emergent-managed cluster today (see `docs/PORTABILITY.md`). Status: Sep 30 2026 audit snapshot; ~194 distinct
collections are referenced from code, 74 `create_index` calls exist, no schema registry.

## Access layer
- `routers/database.py` - lazy singleton `get_db()` (`AsyncIOMotorClient(MONGO_URL)`, database from the URL path
  or `DB_NAME`). Also the RBAC scoping helpers (`get_accessible_user_ids`, `get_data_filter`, `verify_user_access`).
- Documents use Mongo `ObjectId` primary keys; APIs return `str(_id)` as `id`/`_id`. Timestamps are stored as
  datetimes (some legacy fields as ISO strings). Mongo returns naive datetimes: make them tz-aware before
  arithmetic (a real bug source, see `memory/PRD.md`).
- There is no ORM. Each router/service builds dicts directly; `serialize_*` functions shape API output.

## Tenancy model
```
organizations (org_admin)  1 ─┐
                              ├─ stores (store_manager)  1 ─┬─ users (reps, role "user")
white_label_partners / partners ┘                          └─ everything a rep owns carries user_id
shop_clients (mystery-shop customers, standalone tenants owned by iMOS admins)
```
- Scoping fields: `user_id` (owner rep) on almost everything (contacts, conversations, messages, tasks,
  campaigns, cards ...), `store_id` on users/stores/shared inboxes/scorecards/widgets/compliance,
  `organization_id` (legacy alias `org_id`) on stores/users/org-level Twilio, `partner_id` for the partner program,
  `shop_client_id` for mystery-shop data.
- Rule: every query that returns customer data must be filtered by the caller's scope via the helpers above or
  the `rbac.py` dependencies. Managers see their store's reps' data; org admins their org; super admins everything.

## Collection map (most referenced first; counts = code references)
| Area | Collections |
|---|---|
| Identity & tenancy | `users`(676) `stores`(226) `organizations`(72) `team_members` `teams` `team_invites` `permission_templates` `permission_audit_log` `impersonation_sessions` `login_attempts` `password_reset_tokens` `api_keys` `white_label_partners` `partners` `partner_agreements` `partner_invoices` `partner_billing_records` `partner_templates` `nda_agreements` |
| Customers & activity | `contacts`(496) `contact_events`(158) `contact_photos` `contact_intel` `archived_contacts` `notes` `tags` `keyword_rules` `keyword_tag_events` `engagement_signals` `customer_feedback` `referrals` `sold_event_logs` `inventory_interest` |
| Messaging | `conversations`(270) `messages`(173) `message_drafts` `ai_reply_queue` `ai_messages` `inbound_message_dedup` (unique `message_sid` + 1 h TTL) `sms_queue` `shared_inboxes` `inboxes` `threads` `templates` `email_templates` `email_logs` `broadcasts` `broadcast_recipients` `lifecycle_messages` `date_trigger_configs` `date_trigger_log` `date_send_guard` `birthday_cards` |
| Leads | `inbound_leads` `lead_sources` `lead_deferred_actions` `lead_call_jobs` `lead_email_failures` `inbound_email_unmatched` `demo_requests` `webhook_subscriptions` `webhook_events` `webhook_logs` `integrations` `sync_logs` `crm_pin_sessions` |
| Tasks & home | `tasks`(135) `task_nudges` `home_action_state` `home_daily_picks` `user_schedules` `notifications`(106) `notification_reads` `held_pushes` `push_subscriptions` `expo_push_tokens` `push_log` `push_errors` `weekly_kpis` `user_milestones` `user_lifecycle_events` |
| Campaigns | `campaigns` `campaign_enrollments` `campaign_pending_sends` `campaign_templates` `campaign_configs` `campaign_settings` `campaign_costs` `ai_outreach` `email_campaigns` |
| Cards, links, QR | `congrats_cards` `congrats_cards_sent` `congrats_templates` `congrats_card_templates` `card_scans` `card_shares` `card_events` `short_urls` `short_url_clicks` `go_links` `go_scans` `link_pages` `app_links` `app_link_taps` `app_installs` `wallet_pass_tokens` `brand_assets` `social_templates` `review_response_templates` `review_link_clicks` `user_gallery` `showcase_consents` `tracked_media` `media` |
| Calls & voice | `call_logs` `calls` `pending_calls` `voicemails` `voice_notes` `voice_upload_chunks` `photo_upload_chunks` `photo_requests` `jessie_sessions` `live_sessions` `interview_sessions` `ai_va_profiles` `ai_clone_prompts` |
| Mystery shops & training | `roleplay_sessions`(171, every practice/shop call) `scripts`(60, challenges live here with `pool: "mystery_shop"`) `shop_clients` `shop_targets` `shop_proposals` `shop_report_sends` `mystery_shops` `call_evaluations` `scorecards` `call_guides` `voice_samples` `phone_number_pool` `courses` `course_enrollments` `training_tracks` `training_lessons` `training_progress` `training_certificates` `training_video_views` `sops` `sop_progress` `sop_feedback` `coaching_digest_sends` |
| Inventory | `inventory` `inventory_feeds` `inventory_feed_runs` |
| Billing | `subscriptions` `subscription_quotes` `subscription_cancellations` `payment_transactions` `invoices` `discount_codes` `billing_waivers` |
| Widget | `widgets` `widget_chats` `widget_call_requests` `widget_events` `widget_site_pages` |
| Platform | `settings` (key/value: `jessi_voice`, `twilio_compliance`, `locale_voices`, lab flags) `system_logs` `system_cursors` `migrations` `migration_jobs` `error_reports` `bug_reports` `company_docs` (synced docs) `onboarding_settings` `onboarding_clients` `setup_wizard_progress` `report_preferences` `health_report_schedules` `account_health_snapshots` `account_health_alert_log` `source_health_alert_log` `seo_stats` `seo_page_visits` `transfer_logs` `bulk_transfers` `member_activities` `activity` `waiting_clear_log` `weekly_wins_push_log` `weekly_proof_push_log` `template_sends` `invite_shares` |

## Indexes
- Created lazily from code (`create_index` in `server.py` startup and inside routers/services), never dropped.
  Known: `inbound_message_dedup` (unique `message_sid`, TTL 1 h), `login_attempts`, `messages`, `conversations`,
  `contacts`, `contact_events`, `notifications`, `short_urls`, `short_url_clicks`, `tags`, `campaign_*`,
  `push_log`, `photo_upload_chunks`, `date_trigger_configs`, `link_pages`, `customer_feedback`, `ai_reply_queue`.
- TODO (portability step): consolidate into one `ensure_indexes()` module so a fresh database gets every index.

## Migrations & seeds
- `backend/migrations/hash_passwords.py` - one-off bcrypt migration (auth still accepts legacy plaintext until a
  user logs in and is upgraded).
- Startup self-heals in `server.py` seed reference data idempotently: Kubota demo shop client (`seed_key`),
  call guides (`call_guides.SEEDS`, `seed_version`), sample shop, docs sync, persona gender backfill.
- QA seed scripts live in `backend/tests/seed_*.py` and `backend/seed_demo_data.py`; they are for preview only.
- Rule (see `CLAUDE.md`): destructive migrations need a written plan + rollback; never run them against
  production data ad hoc.

## Environment separation
- Preview: local `mongod` in the container (`mongodb://localhost:27017`). Production: managed cluster with a
  different `DB_NAME`. `services/runtime_env.is_preview_runtime()` keys off `localhost` in `MONGO_URL`.
- Binary data is NOT in Mongo: photos, voice notes, card images, PDFs and audio live in object storage and Mongo
  stores the path (`/api/images/{path}` serves them). Exception: `voice_samples.wav` (small WAV blobs) and
  `voice_id` profiles are stored as `Binary`.

## Backups
- No application-level backup/export exists yet. Production backups are whatever the managed cluster provides.
  Portability step 4 adds `mongodump`/`mongorestore` procedures.
