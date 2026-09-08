# Android / Google Play launch checklist (June 2026)

## Code state (done in preview, ships with next `eas build`)
- package `com.imonsocial.app`, EAS project 178e2029-a577-4d78-9611-bd7ebec83c91, `appVersionSource: remote` (versionCode auto-increments on EAS).
- `android.blockedPermissions` strips READ_MEDIA_IMAGES/VIDEO/AUDIO/VISUAL_USER_SELECTED (Play "Photo & Video permissions" policy) + WRITE_CONTACTS (never used). Manifest keeps CAMERA, READ_CONTACTS, RECORD_AUDIO, READ/WRITE_CALENDAR (Calendar Sync screen), USE_BIOMETRIC, READ/WRITE_EXTERNAL_STORAGE (API <= 32 only).
- Photo saving (thread congrats photo, sold-quick) uses `MediaLibrary.requestPermissionsAsync(Platform.OS === 'android')` = write-only on Android (no prompt on 13+). iOS behaviour unchanged (needs no new plist key).
- expo-notifications plugin: Android status-bar icon `assets/images/notification-icon.png` (white silhouette) + accent `#C9A962`.
- `app.config.js` adds `android.googleServicesFile` automatically when `frontend/google-services.json` exists (app.json stays the source of truth).
- Backend: `PLAY_STORE_URL` env (routers/app_links.py) - once set, `imonsocial.com/get/<name>` sends Android to the store instead of the website.
- Verified: `expo prebuild --platform android` manifest shows blocked permissions with tools:node="remove", notification icon resources generated (android/ folder deleted afterwards; never commit it).

## User actions
1. Firebase (Android push): console.firebase.google.com -> new project -> Add Android app (package com.imonsocial.app) -> download `google-services.json` -> put it in `frontend/` (safe to commit). Then Project settings -> Service accounts -> Generate new private key -> `eas credentials -p android` -> FCM V1 -> upload that JSON.
2. Play Console: create app "i'M On Social"; Store listing (icon 512, feature graphic 1024x500, 2-8 phone screenshots, descriptions), Privacy policy https://www.imonsocial.com/privacy, Data safety (contacts, phone, email, photos, audio, approximate location none; not sold; encrypted in transit; deletable), Content rating, Target audience 18+, App access -> reviewer login (create in Admin > Users on production), Ads none, News/Financial/Health = no.
3. Build + upload: `eas build -p android --profile production` -> `eas submit -p android --profile production` (needs Play API service-account JSON at `frontend/google-service-account.json`, track internal) OR upload the .aab manually to Internal testing.
4. Personal developer accounts (created after Nov 2023): closed test with 12 testers x 14 days before production access. Organization accounts skip this.
5. After approval: set `PLAY_STORE_URL=https://play.google.com/store/apps/details?id=com.imonsocial.app` on the production backend + redeploy; add a Google Play badge next to the App Store badge on the marketing "Get the app" section.
