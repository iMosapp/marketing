# iMOS — MANDATORY CHANGE RULES

**READ THIS BEFORE MAKING ANY CODE CHANGE.**

These rules exist because production features were broken by changes that didn't account for mobile browser behavior. Every rule below was written after a real production incident.

---

## Rule 1: No Change Without Understanding the Full Flow

Before modifying ANY function, you MUST:
1. Read the function's documentation in `/app/memory/PRD.md` under "CRITICAL TECHNICAL FLOWS"
2. Trace the COMPLETE user journey from tap to result (not just the function in isolation)
3. Test on a mobile viewport (390x844) — not just desktop
4. Verify that the change does NOT break any of the flows documented in the PRD

If you don't understand why the code is written a specific way, DO NOT CHANGE IT. Ask first.

---

## Rule 2: The `keepalive` Pattern is Sacred

Any function that opens a native app protocol (`sms:`, `tel:`, `mailto:`) MUST use `fetch` with `keepalive: true` for API logging — NEVER `await`.

**Why:** Opening `sms:` or `tel:` navigates the browser away. Any pending `await` will never resolve. The API call gets killed. Data is silently lost.

**Correct pattern:**
```javascript
// 1. Fire API call with keepalive (completes even when browser navigates away)
fetch(apiUrl, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
  keepalive: true,
}).catch(() => {});

// 2. THEN open native app (this navigates away)
const a = document.createElement('a');
a.href = protocolUrl;  // sms:, tel:, mailto:
a.target = '_self';
document.body.appendChild(a);
a.click();
document.body.removeChild(a);
```

**WRONG pattern (will silently lose data):**
```javascript
// DON'T DO THIS — await will never resolve after navigation
const a = document.createElement('a');
a.href = 'sms:1234567890';
a.click();  // browser navigates away HERE
await api.post('/log', data);  // NEVER EXECUTES
```

**Files using this pattern:**
- `/app/frontend/app/thread/[id].tsx` — `handleSend()` personal SMS path
- `/app/frontend/app/(tabs)/dialer.tsx` — `handleCall()`

---

## Rule 3: The Anchor-Click Technique is Required for Protocol Links

On mobile Safari, `window.location.href`, `window.open()`, and `Linking.openURL()` are blocked by popup blockers for `sms:` and `tel:` protocols. The ONLY reliable method is creating an `<a>` element and clicking it programmatically.

**Correct (works on all mobile browsers):**
```javascript
if (Platform.OS === 'web') {
  const a = document.createElement('a');
  a.href = 'sms:1234567890&body=Hello';
  a.target = '_self';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
} else {
  Linking.openURL('sms:1234567890');
}
```

**WRONG (blocked on mobile Safari):**
```javascript
window.location.href = 'sms:1234567890';  // BLOCKED
window.open('sms:1234567890');  // BLOCKED
Linking.openURL('sms:1234567890');  // UNRELIABLE on web
```

---

## Rule 4: Action Tiles Must Pre-fill, Never Auto-send

Every action tile in a conversation thread (Share Review, Share Business Card, Share Landing Page, Templates, Congrats Card) MUST use `setMessage(msg)` to pre-fill the composer.

NEVER call `handleSend(msg)` from an action tile handler. The Send button tap is the user gesture that opens the native SMS app. Without it, mobile browsers block the `sms:` protocol.

---

## Rule 5: iOS vs Android SMS URL Format

iOS iMessage: `sms:{phone}&body={message}` (ampersand separator)
Android: `sms:{phone}?body={message}` (question mark separator)

Detection: `/iPad|iPhone|iPod|Macintosh/.test(navigator.userAgent)`

Using the wrong separator = SMS app opens but message body is empty.

---

## Rule 6: The Viewport Meta Tag Must Not Change

File: `/app/frontend/app/+html.tsx`

The viewport MUST include `maximum-scale=1, user-scalable=no`. Removing these allows iOS Safari to expand the viewport when content overflows or when focusing inputs with font-size < 16px. Once expanded, the viewport stays wide permanently until the user pinch-zooms.

---

## Rule 7: Input Fields Must Be 16px on Mobile

Global CSS in `+html.tsx`: `input, textarea, select { font-size: 16px !important; }`

iOS Safari auto-zooms when focusing an input with font-size less than 16px. This combined with a permissive viewport causes permanent zoom issues.

---

## Rule 8: Both Email Fields Must Be Checked

Contacts can have `email` (personal) and `email_work` (work). Every email-sending code path MUST check both:
```python
contact_email = contact.get('email') or contact.get('email_work')
```

Backend file: `/app/backend/routers/messages.py` — has TWO email paths that both need this.


Also: ALL navigation paths to the thread page MUST include `contact_email` in params. The conversations API returns `email` in the contact object. If `contact_email` is missing from URL params, the "Switch to Email" button will do a fallback API check — but passing it upfront is always preferred.

Frontend files that navigate to threads:
- `/app/frontend/app/(tabs)/inbox.tsx` — 3 navigation paths (all now include email)
- `/app/frontend/app/contact/[id].tsx` — includes email in threadParams

---

## Rule 9: Preview and Production Are Separate

- Preview database: `localhost:27017 / imos-admin-test_database`
- Production database: MongoDB Atlas (set via Emergent platform env vars)

Changes in preview do NOT deploy to production automatically. User must click Deploy in Emergent.

`load_dotenv(override=False)` in `server.py` is CRITICAL. `override=True` causes production to use the .env localhost URL, locking the user out. This caused a 3-day outage.

---

## Rule 10: Test the Exact User Journey

Before declaring any fix complete:
1. Login as `forest@imosapp.com`
2. Navigate to a contact with a phone number AND email
3. From the contact, tap SMS → verify thread opens with phone pre-filled
4. Type a message → tap Send → verify native SMS app opens WITH message body
5. Go back → check Inbox → verify message appears in conversation
6. Check contact → verify Activity Feed shows the event
7. Repeat for Email mode → verify Resend dashboard shows the email
8. Test the dialer → verify phone app opens AND call is logged
9. Test Share Review, Share Card, Share Congrats from More page

If ANY step fails, the change is not ready for production.

---

## Incident Log

### Feb 27, 2026 — Personal SMS Logging Failure
**What happened:** Agent moved `sms:` link opening to before `await messagesAPI.send()` to fix a "user gesture" issue. This caused the browser to navigate away before the API call completed. Messages appeared sent in the UI but were never logged to the backend.
**Impact:** All inbox messages, activity feed entries, and conversation history lost for the session.
**Root cause:** Not understanding that opening `sms:` navigates the browser away, killing pending `await` calls.
**Fix:** Replaced `await` with `fetch` + `keepalive: true` for the personal SMS path.
**Lesson:** Any code that opens a native protocol (`sms:`, `tel:`, `mailto:`) MUST use `keepalive` for background API calls. NEVER `await`.
