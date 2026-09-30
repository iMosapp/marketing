# IMOS frontend (Expo / React Native)

The iOS, Android and web client of i'M On Social. One TypeScript codebase, Expo SDK 54, React Native 0.81,
React 19, Expo Router (file-based navigation), react-native-web for the browser build.

## Layout

```
app/                 screens = routes. app/(tabs)/ is the main tab bar; app/admin/ the admin console;
                     app/thread/[id].tsx the SMS thread; app/guide/, app/shop-score/ etc. are public pages.
components/          shared UI. components/ui = shadcn-style primitives; feature folders (mystery-shops/,
                     thread/, widget/, contact/, common/ ...)
services/api.ts      axios instance. Web: same-origin "/api". Native: EXPO_PUBLIC_BACKEND_URL + "/api".
hooks/               data + platform hooks (useWebSocket, useContactSearch, liveRtc.native/web ...)
store/               zustand stores (e.g. draftStore.ts)
contexts/            React contexts (auth, theme, toast, Live Jessi provider)
utils/ constants/ config/ types/
assets/              icons, splash, sounds
babel-plugin-*.js    compile-time transforms applied to app/ and components/ only:
                     max-font (maxFontSizeMultiplier=1), keyboard (dismiss on drag + Done bar),
                     modal-kav (KeyboardAvoidingView inside every <Modal>), testid (data-testid -> testID/dataSet)
plugins/             Emergent preview tooling (health-check, visual-edits); not used by Metro builds
public/              static files copied into the web export (ad pages, audio)
```

## Run

```bash
yarn install
yarn start        # Expo web on :3000  (the platform proxies /api to the backend on :8001)
yarn ios          # iOS simulator
yarn android      # Android emulator
yarn build:web    # static export -> dist/
npx tsc --noEmit  # type check
yarn lint
```

Environment: copy `.env.example` to `.env`. Only `EXPO_PUBLIC_*` variables reach the bundle. Point
`EXPO_PUBLIC_BACKEND_URL` / `EXPO_PUBLIC_APP_URL` at `https://app.imonsocial.com` before any `eas update`; the
values are baked into the OTA bundle.

## Conventions

- Every interactive or informative element carries a `data-testid` / `testID` (kebab-case, function not style).
  Use the `tid('name')` helper where a component exports it.
- Named exports for components, default exports for screens. Keep components small.
- Bottom sheets use `components/common/SheetGrabber.tsx` (swipe to close). Do not hand-add
  `KeyboardAvoidingView` to modals or `maxFontSizeMultiplier` to text; the Babel plugins do it.
- After changing `babel.config.js` or a Babel plugin: `rm -rf node_modules/.cache .metro-cache` and restart Metro.
- AI-written copy must never contain em/en dashes (product rule; see `docs/PRODUCT_RULES.md`).

## Shipping

- JS-only changes: `eas update --branch production --message "..."` (from a machine logged into the Expo account
  that owns project `imos`). Native changes (new permission, native module, app.json): bump `expo.version`, then
  `eas build --platform ios --profile production --auto-submit`.
- Android is configured (`com.imonsocial.app`) but not published; `google-services.json` (push) and
  `google-service-account.json` (Play submit) are intentionally not in the repo.

See the root `README.md` and `docs/DEPLOYMENT.md` for the full release procedure.
