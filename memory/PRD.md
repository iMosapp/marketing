# i'M On Social — Relationship OS (PRD)

## Original Problem Statement
Phase 2 "Relationship OS" UX enhancements: robust backend security, intent-based detection engine, live inventory tracking, ADF/XML lead intake. Native iOS/Android UX (Expo), Twilio voice/SMS routing, long-term campaign tracking, AI personalization, strict RBAC, and "no brain power" UI layouts for sales reps.

## Environments
- Preview: REACT_APP_BACKEND_URL in /app/frontend/.env (backend under test)
- Production: https://app.imonsocial.com — user pushes frontend via `eas update --branch production --message "msg"` (give ONLY the one-liner). Backend goes live when user hits Deploy.
- IMPORTANT: EXPO_PUBLIC_BACKEND_URL in frontend/.env must point to https://app.imonsocial.com before any `eas update` (it gets baked into the OTA bundle). Temporarily point it at the preview URL only for screenshot testing, then revert + restart frontend.

## Implemented (key items)
- AI auto-replies (per-chat + global AI ON/OFF master switch), Twilio routing, voice memos → AI profile extraction (newest memo wins)
- Live inventory webhooks, keyword auto-tagging, call playback, ADF/XML lead intake
- Contact profile refactored into /app/frontend/components/contact/*
- Touchpoints swipe actions (right=Done, left=Snooze) + Undo snackbar (backend undo in tasks.py)
- Send Photo to many (quick-send/photo.tsx), industry-neutral naming
- QR everywhere: login screen "My Card QR", Home header 1-tap QR, Card tile long-press
- Wallet pass pipeline (backend/routers/wallet_pass.py): Apple .pkpass signing + Google save-link — returns 503 until certs are in .env (APPLE_TEAM_ID, APPLE_PASS_TYPE_ID, APPLE_PASS_P12_B64, APPLE_PASS_P12_PASSWORD, APPLE_WWDR_PEM_B64)
- **QR Scan Counter (June 2026, this session)**: `card_scans` collection — unique visitor/day dedupe (sha256 of IP+UA), owner self-views excluded via Bearer token check. `GET /api/card/scan-stats/{user_id}` → {week, total}. Displayed as "X scans this week · Y all-time" pill in UniversalShareModal QR view (home header QR / Card QR). Tested: dedupe, self-view exclusion, UI render all verified on preview.

## Pending / Backlog
- P0 Wallet Activation: user gathering Apple certs — step-by-step instructions provided (Pass Type ID + Team ID + .p12 + WWDR G4 PEM). When received: base64 into backend .env, test /api/wallet/{id}/download-token flow.
- P1 Google Play .aab: user to upload build from expo.dev to Play Console (user action).
- P1 HomeNet/vAuto live inventory feed (awaiting dealer API credentials).
- P2 Rotate production secrets (Twilio, Stripe, Resend, Mongo, VAPID, OpenAI) before contractor handoff.
- P2 Zapier integration for generic lead payloads.
- P3 WhatsApp, Stripe partner invoices, enterprise DMS (CDK, Reynolds, Dealertrack).

## Notes for agents
- User language: English. Keep replies short; for production pushes give ONLY `eas update` one-liner.
- Metro bundler can serve stale bundles — restart frontend supervisor if changes don't appear.
- RN-web may not expose data-testid on TouchableOpacity in header; click by coordinates in screenshot tests.
- Admin login: forest@imosapp.com / Admin123! (see /app/memory/test_credentials.md)
