# i'M On Social — Product Requirements Document

**Version:** August 2026 · **Status:** Live in production (iOS App Store + Android internal track + Web PWA)
**Production:** app.imonsocial.com · **Marketing site:** imonsocial.com

---

## 1. Vision

i'M On Social (iMOS) is a **Relationship Operating System** for automotive sales professionals and dealerships. It replaces the patchwork of personal texting, sticky notes, spreadsheet follow-up lists, and generic CRMs with one mobile-first platform where a rep can: capture every customer, text/call from a dedicated business number, let AI ("Jessi") draft and send personalized replies, run years-long follow-up automatically, intake internet leads with inventory matching, and prove ROI on every lead source.

**North star:** no customer relationship ever goes cold, and every touchpoint feels personal — even when it's automated.

## 2. Users & Personas

| Persona | Role in app | What they need |
|---|---|---|
| **Sales Rep** | `user` | Dialer, inbox, contacts, AI replies, cards, touchpoints, leads, personal reports |
| **Store Manager** | `store_manager` | Everything reps have + store-level admin: team, inventory, lead sources, intent tuning, lockout settings |
| **Org Admin** | `org_admin` | Multi-store oversight, org reports, user management |
| **Super Admin (owner)** | `super_admin` | Full platform: billing, partners, white-label, Twilio numbers, system logs, internal docs |
| **Partner / Reseller** | partner portal | Agreements, invoices, W-9, onboarding |
| **Customer (end consumer)** | no login | Receives texts/calls/cards; public pages (digital card, review, showcase, opt-in, congrats/birthday cards) |

## 3. Core Feature Requirements (Current Scope)

### 3.1 Contacts & CRM
- Full contact records: names, phones (E.164 normalized, dedup on import), vehicle, dates (birthday, anniversary, **date sold**), tags, notes, photo.
- CSV bulk import with duplicate detection; contact merge tool; duplicate finder.
- Activity timeline per contact (calls, texts, cards, campaign events, AI events).
- Photo gallery per contact: profile history, MMS photos texted in/out, card photos; camera or library upload; set-any-photo-as-profile; delete photos.
- SOLD wizard: backdatable purchase date, delivery photo, triggers congrats flow.
- Voice memos per contact: record (native m4a / web webm→auto-converted to m4a), Whisper transcription, playback (HTTP range streaming), delete.

### 3.2 Messaging (Twilio SMS/MMS)
- Every rep gets a **dedicated Twilio number**; inbound texts route to the owning rep (strict number→rep lookup, shared-inbox fallback).
- Threaded inbox with media, vCard contact-card tiles, read state, quiet hours (sends deferred to 9 AM local).
- Broadcast messaging with scheduling; opt-in/opt-out compliance (STOP handling); A2P messaging service.
- MMS media proxied and stored durably in Emergent Object Storage.

### 3.3 AI — "Jessi"
- Per-rep AI persona (tone, brevity, emoji, humor) trained via onboarding + voice training.
- AI auto-reply queue with escalation to rep when unsure; drafts held for approval in manual mode.
- **Intent detection engine** with per-store sensitivity slider (`intent_hot_threshold`) + preview of which past conversations would flag.
- **Live inventory context**: Jessi quotes actual in-stock vehicles (year/make/model/price) in replies.
- AI message suggestions on contact page (no em-dashes rule enforced).

### 3.4 Dialer & Voice
- Full-screen keypad, height-adaptive layout, server-side search of the entire contact book by **name or phone digits**, Recents tab.
- Tapping a contact **stages** the number; the green button places the call (no accidental dials).
- **Click-to-call with press-1 gate**: Twilio calls the rep's cell first → rep must **press 1** to dial the customer. Hang-up/voicemail = customer is never dialed.
- Live in-call UI: status line + **red hang-up button** that kills the call server-side.
- Call recording (record-from-answer), recording playback, call logging to contact timeline + thread; inbound calls ring rep's cell with whisper, voicemail fallback.

### 3.5 Campaigns & Automations
- Campaign builder: multi-step sequences (SMS/email), delays (minutes→months), AI-personalized or template, auto or manual delivery.
- Triggers: **tag-based** (instant on tag application — except date tags), **date-based** (birthday / anniversary / sold-date — fire ONLY day-of), lifecycle (sold → long-term nurture), congrats-card follow-up.
- **Date sends are strictly opt-in**: a contact gets birthday/anniversary messages ONLY if they carry the manual `Birthday` / `Anniversary` tag. Tags are never auto-applied. Same-day guard makes double-sends impossible.
- **Date Recipients manager** (Settings → Date Triggers → Manage Recipients): search everyone with a date on file, filter ON/OFF, bulk opt-in/out. Per-contact toggles also live on the contact profile (Details → Important Dates).
- **Morning preview digest**: at 8 AM local, rep gets an SMS + notification listing exactly who receives date sends that day (sends go at 9 AM).
- Anniversary = **sold-date anniversary**: message resolves `{years}` and auto-attaches the anniversary card featuring the car photo.
- Sold workflow: delivery congrats card, scheduled delivery texts, VCF auto-queue.

### 3.6 Cards & Public Pages
- Congrats / birthday / anniversary / thank-you / holiday / welcome cards with store branding, customer photo, short URLs, view tracking.
- Digital business card per rep (`/card/{userId}`), store cards, link page (`/l/{username}`), showcase pages, review funnel (`/review/{storeSlug}`) with template replies and approvals.

### 3.7 Internet Leads
- **ADF/XML intake** (`POST /api/leads/inbound`), **email intake** (`/api/leads/inbound/email`), Zapier-style webhook payloads; per-source webhook URLs generated in Admin → Lead Sources.
- Auto-match lead vehicle to live inventory (year/make/model/trim) and attach the stock unit.
- Instant push notification to reps on new lead; **auto-photo texting** — the matched vehicle's photo rides along on the first reply.
- Leads dashboard: status funnel (new → replied → sold), per-lead **speed-to-lead badge** ("Replied in 4m", color-coded <5m green).
- **Speed tab**: team avg response time + per-rep leaderboard (avg/fastest/count). First *human* reply only — AI/auto sends don't count.
- **Source ROI**: monthly cost entry per source; funnel + $/lead + $/sale; **monthly ROI email** on the 1st (per-store recipient configurable, defaults to owner).

### 3.8 Live Inventory
- Vehicle records: stock #, year/make/model/trim, price, status (available/sold), photos (object storage), visibility.
- Webhook ingestion endpoints ready for HomeNet/vAuto feeds.
- **Missing-photo reminders**: banner in Inventory + daily 9 AM push to store admins while in-stock units lack photos.
- Inventory context injected into Jessi AI replies and lead auto-match.

### 3.9 Teams, Stores, Orgs, Partners
- Hierarchy: Org → Stores → Users; RBAC everywhere (BOLA middleware + role checks).
- Store settings: intent threshold, login lockout (attempts + minutes), **ROI report email**.
- Team invites, pending-user approval, availability/shifts (leads route to on-shift reps), team chat, leaderboards (v2 power rankings), engagement scoring.
- Partner program: agreements (e-sign), NDA flow, W-9 collection, partner invoices (Stripe), white-label config.

### 3.10 Reporting & Intelligence
- Personal / team / campaign / messaging reports; daily report delivery; monthly account-health reports; card analytics; click tracking (deduplicated); training completion reports & certificates.
- Home intelligence feed: touchpoints due today, hot leads, birthday nudges.

### 3.11 Platform & Security
- JWT auth (PyJWT), bcrypt passwords, brute-force lockout (configurable per store), password-reset throttles, strict CORS via env, BOLA object-level authorization middleware.
- Bug reporting: in-app "Report a Bug" → instant push to admins + Monday digest email.
- Push notifications (web VAPID + native), notification center.
- Object storage for all media (photos, audio, cards) served through `/api/images/{path}` proxy with HTTP Range support.
- Startup self-heals: voice-note relink, webm→m4a conversion, date-optin reset migration, doc sync, Twilio webhook verification.

## 4. Non-Functional Requirements
- Mobile-first (Expo/React Native); OTA updates via `eas update`; web PWA from the same codebase.
- All sends respect quiet hours (9 AM local deferral) and opt-out state.
- Every automated send must be idempotent/guarded (same-day guards, idempotency keys, TTL dedup).
- No customer-facing action fires without either an explicit rep action or an explicit opt-in.

## 5. Prioritized Backlog
- **P1** Google Play production `.aab` upload (built, awaiting console upload).
- **P1** HomeNet/vAuto live inventory feed (webhooks ready, needs dealer credentials).
- **P2** Rotate production secrets before contractor onboarding (Twilio, Stripe, Resend, Mongo, VAPID, OpenAI).
- **P2** Zapier generic lead payload connector.
- **P2** Slow-reply alert: ping manager when a lead sits unanswered >15 min.
- **P3** Digest quick actions (reply "SKIP Jane" to pull someone from today's date sends).
- **P3** Refactor `contact/[id].tsx` and `thread/[id].tsx` monoliths.
- **P3** WhatsApp channel; CDK/Reynolds/Dealertrack DMS integrations; Stripe partner-invoice autopay.

---
*Source of truth: `/app/docs/PRODUCT_REQUIREMENTS.md` — synced to Admin → Docs automatically on every deploy.*
