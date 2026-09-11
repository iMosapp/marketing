# i'M On Social — Tech Stack (the one-pager)

**Read this before talking to a programmer.** It is the plain-English version of "what is this thing written in?" Every item below is exactly what runs in production today.

---

## The 10-second answer

> "It's a **React Native / Expo** app written in **TypeScript**, so one codebase ships the iPhone app, the Android app and the web app. The back end is **Python (FastAPI)** with a **MongoDB** database. Texting and calls run on **Twilio**, the AI is **OpenAI (GPT-5.2 + Whisper)**, email is **Resend**, payments are **Stripe**, and it's hosted on **Emergent**."

If they only want languages: **TypeScript on the front end, Python on the back end, MongoDB for data.**

---

## Front end (what people tap on)

| Piece | What it is | Why it matters |
|---|---|---|
| **React Native + Expo** (Expo SDK 54, React Native 0.81, React 19) | The app framework. One codebase for iOS, Android and web/PWA. | We never build the same screen three times. |
| **TypeScript** | The language the app is written in (JavaScript with types). | Any React/React Native developer can work on it. |
| **Expo Router** | File-based navigation: every file in `frontend/app/` is a screen. | Screens like `/scorecards/team` map 1:1 to files. |
| **EAS Update** | Over-the-air updates. `eas update --branch production` pushes UI changes to phones without an App Store review. | Most UI fixes ship in minutes. Only native changes need a store build. |
| **Zustand** | Tiny state store (logged-in user, theme). | Simple, no Redux. |
| **Axios** | Talks to the back end over HTTPS at `/api/...`. | |
| **react-native-svg, expo-image, expo-av, expo-contacts, expo-notifications** | Charts/gauges, images, audio playback, phone contacts import, push. | |

## Back end (the brain)

| Piece | What it is | Why it matters |
|---|---|---|
| **Python 3.11 + FastAPI** | The API server. Every route lives under `/api`, async end to end. | Fast, typed, auto-documented. ~100 routers grouped by domain (contacts, messages, leads, inboxes, scorecards...). |
| **Pydantic** | Request/response validation. | Bad input is rejected before it touches data. |
| **Motor (async MongoDB driver)** | How Python talks to the database. | |
| **APScheduler** | Background jobs (campaign steps, AI reply queue, lead ladders, date triggers, digests, invoices, cleanup). | The "it just happens" automation. `GET /api/health/deep` shows the live job count. |
| **JWT auth + role-based access** | Bearer tokens; roles `user` (rep), `store_manager`, `org_admin`, `super_admin`, partners. | Reps only see their own data; managers see their store; org admins their org. |
| **fpdf2, Pillow, qrcode** | PDF generation (invoices, docs, 4x6 print cards), server-side images and QR codes. | No browser needed on the server. |

## Data

| Piece | What it is |
|---|---|
| **MongoDB (Atlas)** | The database. Document store, one database per environment (preview vs production, separate data). Key collections: `users`, `stores`, `organizations`, `contacts`, `conversations`, `messages`, `contact_events` (every touchpoint), `tasks`, `campaigns`, `inbound_leads`, `lead_sources`, `shared_inboxes`, `call_logs`, `scorecards`, `call_evaluations`, `notifications`. |
| **Emergent Object Storage** | Photos, voice notes, audio, cards. Served through `/api/images/{path}`. |

## Third-party services (the plumbing)

| Service | Used for |
|---|---|
| **Twilio** | SMS/MMS (A2P 10DLC messaging service), voice calls, call recording, shared department numbers, lead call ladders. Inbound webhooks hit `/api/webhooks/twilio/*`. |
| **OpenAI via Emergent LLM key** | GPT-5.2 for Jessi (AI replies, drafts, summaries, Relationship Intel, call scorecards); Whisper for call and voice-note transcription. Accessed through the `emergentintegrations` library. |
| **Resend** | All email (invites, reports, ADF lead pushes, PDF exports). Domain: imonsocial.com. |
| **Stripe** | Subscriptions, partner billing and invoices. |
| **Expo Push + Web Push (VAPID)** | Native push to iPhone/Android and browser push for the PWA. |
| **Apple Wallet / Google Wallet** | Digital card passes (Apple certs pending). |
| **Nominatim / OpenStreetMap** | Address lookup during onboarding (free). |

## Where it runs

| | Preview (dev) | Production (live) |
|---|---|---|
| Web + API | Emergent preview pod | **app.imonsocial.com** on the Emergent platform |
| Phones | n/a | iOS App Store, Google Play (internal track), web PWA |
| Marketing site | n/a | imonsocial.com (static, Vercel) |
| Code | GitHub (Save to GitHub button) | Deploy button ships back end + web; `eas update` ships the app UI |

## Repo at a glance

```
/app
├── backend/      FastAPI (Python)  -> server.py, routers/, services/, scheduler.py
├── frontend/     Expo / React Native (TypeScript) -> app/ (screens), components/, services/api.ts
├── docs/         these internal docs (synced into Admin > Company Docs on every deploy)
└── marketing/    static marketing site
```

## Cheat sheet: things a developer will ask

- **"Monolith or microservices?"** One FastAPI monolith with domain routers. One database. Simple to run, simple to hand off.
- **"REST or GraphQL?"** REST/JSON. Everything under `/api`. OpenAPI docs are auto-generated by FastAPI.
- **"Auth?"** JWT bearer tokens, bcrypt password hashing, Face ID / biometric unlock on device. Strict role-based access on every route.
- **"Real-time?"** WebSockets for live inbox updates plus push notifications.
- **"How do you deploy?"** Save to GitHub, hit Deploy for the back end/web, `eas update` for the app. Native rebuilds (`eas build`) only for new permissions or native packages.
- **"Tests?"** Backend pytest suites live in `backend/tests/` (routing matrices, lead flows, inboxes, scorecards).
- **"Compliance?"** TCPA-aware texting (STOP/HELP handled, quiet hours), A2P 10DLC registered, encrypted in transit (TLS) and at rest (Atlas).

_Last updated: September 2026. Versions: Expo 54 / RN 0.81 / React 19 / TS 5.9 / Python 3.11 / FastAPI 0.110 / Motor 3.3 / Twilio 9 / Stripe 14 / Resend 2._
