# Automotive CRM & DMS Partner Programs

**Purpose:** a working checklist for getting I'm On Social certified with the automotive CRM and DMS vendors our dealers use, so customer records, notes, texts and sold data can sync directly instead of through ADF email and CSV. Program details below were researched in September 2026 from vendor sites and agreements; fees and timelines change, so confirm each one on the first call.

> **Bottom line:** none of the big automotive CRMs have a self-serve API. Every one is a gated partner program with an application, a contract (usually under NDA), a security review, a certification test and, for most, fees plus per-rooftop dealer authorization. Plan on 2 to 6 months per vendor. Start with the fastest ones (Tekion, Fortellis) while the slow ones (Cox, Reynolds) are in the queue.

---

## At a glance

| Vendor / CRM | Program | Access model | Cost signal | Realistic timeline | Works today without certification |
|---|---|---|---|---|---|
| **CDK Global** (Elead CRM, CDK CRM/Drive DMS) | Fortellis Automotive Commerce Exchange | Self-register, then mandatory app certification per app | Certification fee (quoted in welcome email); recert up to $2,500; $129/month per Marketplace listing; API usage per publisher plan | 6 to 12 weeks after the app is built | ADF email into Elead; ADF/lead forwarding out of Elead |
| **Cox Automotive** (VinSolutions Connect CRM; also Dealer.com, vAuto, HomeNet, Xtime) | Cox Automotive Partner Program / Developer Network | Application, Participation Form, VinSolutions Integration Terms; per-rooftop dealer enablement | Negotiated per vendor; pass-through to dealers capped at actual cost | 3 to 6 months | ADF email into VinSolutions; lead forwarding out |
| **Reynolds and Reynolds** (FOCUS CRM, ERA-IGNITE / POWER DMS) | Reynolds Certified Interface (RCI) | Inquiry, technical + security review, contract under NDA; recertification every 2 years | Not public. Historically the most expensive program (one-time participation + per-dealer fees) | 6+ months, enterprise-style engagement | ADF email into FOCUS; CSV |
| **DealerSocket** (Solera) | Certified Partners program | Sales-gated contract; credentials issued per rooftop | Not public | 3 to 6 months | ADF/XML lead forwarding out; ADF email in; inbound activity sync only for partners |
| **DriveCentric** | Partner Program | Inquiry form -> overview call -> data agreement -> docs | Not public | 2 to 4 months (they note high demand / slow replies) | ADF email in |
| **Tekion** (Automotive Retail Cloud, CRM + DMS) | Automotive Partner Cloud (APC) 2.0 | Automated onboarding: pick use case + APIs in the APC dashboard, review, then docs + test tools | Tiered (Standard / Enterprise / Strategic) with different rate limits and support | 4 to 8 weeks | ADF email in |

---

## What we already have (use this in every application)

Vendors ask the same questions. We can answer these today:

- **Public, documented REST API** with API-key auth, tenant scoping, rate limiting, OpenAPI schema and an interactive console: `https://app.imonsocial.com/api/public/reference`.
- **Signed webhooks** (HMAC-SHA256) for every data change, with a delivery log per subscription.
- **ADF/XML 1.0 lead intake** (`POST /api/leads/adf`) and **ADF lead push** by email to any CRM intake address.
- **Full request logging** on the API and webhook side (delivery logs kept; Fortellis requires 60 days of request/response logs for the certified app, so plan to extend retention to 60+ days for the Fortellis connector).
- **Data isolation per store and organization**, hashed key storage, instant key revocation, HTTPS only.
- **Consent handling:** STOP / opt-out honored automatically on every send path; SMS terms published at `/imos/sms-terms`.
- **Privacy Policy and Terms** at `/imos/privacy` and `/imos/terms`.
- **Dealer authorization flow:** the store's admin creates and revokes keys themselves, which maps cleanly onto the "dealer must enable the vendor per rooftop" model every program uses.

---

## Universal prep checklist (do once, reuse for every vendor)

Company and legal
- [ ] Legal entity details, EIN, D-U-N-S number, business address, officer to sign agreements
- [ ] Certificate of insurance (general liability; several programs ask for cyber/E&O, typically $1M+)
- [ ] W-9 and ACH details (Fortellis bills through the platform)
- [ ] NDA on file (Reynolds, DealerSocket and Cox will send theirs)

Security and data handling
- [ ] One-page data flow diagram: what we read, what we write, where it is stored (MongoDB, region), who can see it
- [ ] Written Information Security Policy (access control, encryption in transit/at rest, key rotation, incident response, employee access)
- [ ] Data retention and deletion policy, including "dealer leaves: what happens to their data"
- [ ] Subprocessor list (Twilio, OpenAI, Resend, Stripe, hosting provider)
- [ ] Security questionnaire answers ready (SIG Lite / CAIQ style). SOC 2 Type I is not mandatory for most CRM programs but shortens every review; start it if we plan to do Reynolds or Cox
- [ ] Penetration test summary or vulnerability scan report from the last 12 months
- [ ] Breach notification commitment (most agreements require notice within 24 to 72 hours)

Product and technical
- [ ] Integration Workflow document: every API call we make, why, how often, expected volume per rooftop per day (Fortellis requires this before certification starts)
- [ ] 60-day request/response log retention for certified connectors
- [ ] Sandbox / test store with fake customers (+1 500 555 01xx numbers) and a demo login for the vendor's reviewer
- [ ] Field map for the vendor's objects (customer, deal, note, activity, user) to ours, including how we handle dealer-side merges and deletes
- [ ] Loop prevention and dedupe description (see the CRM Integration Guide)
- [ ] Marketplace listing kit: 100-word description, 3 to 5 screenshots, logo (SVG + PNG), pricing text, support contact, privacy URL
- [ ] Support SLA statement (hours, response time, escalation email)

Commercial
- [ ] Decide pricing pass-through: Cox forbids marking up their integration fee to mutual dealers; Fortellis charges us per listing and per API plan. Set our per-rooftop integration price accordingly
- [ ] Reference dealers willing to take a vendor call (most programs ask for at least one mutual client)

---

## Vendor by vendor

### 1. Tekion (Automotive Partner Cloud 2.0)  - start here

**Why first:** the only program with automated onboarding. Dealer count is growing fast and their dealers skew toward technology-forward stores.

Steps
1. Create an account at `apc.tekioncloud.com`, choose the use case (CRM customer + activity sync) and the specific APIs.
2. Submit for review; on approval you get API docs, sandbox credentials and test tools inside APC.
3. Build the connector against the sandbox; request the tier (Standard is enough to start; Enterprise raises rate limits).
4. Dealer enablement is done by the dealer inside Tekion; document the steps for our store admins.

Gotchas: tiers gate which APIs you can call; check that customer write, notes/activities and deal read are in the tier before building.

### 2. CDK Global / Fortellis (Elead CRM, CDK Drive)

**Why second:** self-registration, public docs, clear (if not cheap) fee schedule, and Elead is one of the most installed CRMs.

Steps
1. Register a developer account on Fortellis, create the app, request the CRM APIs (customer, sales opportunity, activities, direct post).
2. Get test-environment access and build against it.
3. Submit the **Integration Workflow** document through the Developer Care Portal before certification; implement full request/response logging with 60-day retention.
4. Pay the certification fee when the welcome email arrives (due about 31 days later; it auto-charges).
5. Certification with a Fortellis Business Process Consultant: functional tests and possibly an end-to-end demo.
6. Submit the Marketplace listing ($129/month per listing). Dealers subscribe to the app in the Marketplace, which is how per-rooftop authorization works.
7. Any change to the app or the APIs it uses can trigger recertification (up to $2,500 USD).

Gotchas: API usage may be billed per the API publisher's plan (transactional or subscription); read the plan on each API before designing polling frequency. Elead-specific CRM APIs are separate from CDK Drive DMS APIs; we want the CRM set.

### 3. Cox Automotive (VinSolutions Connect CRM)

**Why third:** the largest CRM footprint, but a longer, negotiated process.

Steps
1. Apply through the Cox Automotive Developer Network / VinSolutions gateway registration.
2. Sign the Participation Form and accept the VinSolutions Integration Terms (confidential specs; per-rooftop dealer authorization; no marking up their fee).
3. Request the right plans: **Contact Management** (create/update contacts, consent), **Lead Management** (lead + vehicle sync), and **Connect Eventing** (near-real-time change notifications, which replaces polling).
4. OAuth2 client-credentials + API key are issued after signature; build and test.
5. Each dealer enables us in their VinSolutions settings; write the one-page dealer guide.

Gotchas: fees are negotiated; expect a per-rooftop monthly amount. The Call Tracking plan is restricted to authorized call providers; we do not need it (our calls run on Twilio and are logged on our side). Consent fields matter: pass SMS consent status both ways.

### 4. DealerSocket (Solera)

Steps
1. Contact the DealerSocket partner team through sales; there is no developer portal.
2. NDA + Certified Partner agreement.
3. Integration options historically offered: outbound lead forwarding (XML/email), inbound activity sync (calls, appointments, notes), entity sync for website data. Ask for customer read/write plus activity write.
4. Credentials are issued per rooftop after the dealer signs their authorization.

Gotchas: expect long lead times and manual onboarding per dealer. Until certified, ADF email into DealerSocket and lead forwarding out of it are the reliable paths.

### 5. DriveCentric

Steps
1. Fill in the partner inquiry form on `drivecentric.com/resources/partner-program`.
2. Overview call, then sign their data agreement.
3. API documentation is shared privately after signature. Their partner API is push-oriented (leads, consumer/household data, vehicle data); confirm whether outbound customer/activity events are available.

Gotchas: they publicly note high partner demand and slower responses; apply early and follow up every two weeks.

### 6. Reynolds and Reynolds (RCI; FOCUS CRM, ERA-IGNITE, POWER)

**Why last:** the most closed program, historically the most expensive, biannual recertification, active audits.

Steps
1. Submit an inquiry through Reynolds Data Management.
2. Technical and security review (this is where SOC 2 and the security policy pay off).
3. Contract under NDA; one-time participation fee plus per-dealer interface fees.
4. Certification, then recertification every 2 years or on significant releases.

Gotchas: budget for both the fee and the calendar. Only pursue when we have several Reynolds dealers asking.

---

## Recommended order and rough calendar

| Month | Action |
|---|---|
| 1 | Finish the universal prep checklist. Apply to Tekion APC and register on Fortellis. Send Cox and DriveCentric inquiries (they take longest to answer). |
| 2 | Build the Tekion connector in their sandbox. Write the Fortellis Integration Workflow doc. |
| 3 | Tekion review and first mutual dealer. Fortellis test environment build. |
| 4 to 5 | Fortellis certification + Marketplace listing. Cox Participation Form and plans. |
| 6+ | VinSolutions build and first dealer enablement. DealerSocket and DriveCentric as agreements land. Reynolds only on dealer demand. |

---

## Application blurb (copy and adapt)

> I'm On Social is a relationship platform for dealership salespeople: personal texting from a dedicated number, call logging with AI summaries, voice notes, automated birthday, anniversary and sold follow-up campaigns, digital business cards with review collection, and an AI assistant. We integrate with the CRM so the customer record, assigned salesperson and deal status flow into I'm On Social, and every text, call, note, tag and sold record the salesperson creates flows back into the CRM. We already operate a documented public REST API with tenant-scoped API keys, signed webhooks and ADF/XML lead intake (https://www.imonsocial.com/developers). We are requesting customer read/write, activity/note write and deal read for dealers who authorize us.

---

## Tracker

| Vendor | Status | Contact | Applied | Agreement | Sandbox | Certified | First dealer | Notes |
|---|---|---|---|---|---|---|---|---|
| Tekion APC | Not started | | | | | | | |
| CDK Fortellis (Elead) | Not started | | | | | | | |
| Cox / VinSolutions | Not started | | | | | | | |
| DealerSocket | Not started | | | | | | | |
| DriveCentric | Not started | | | | | | | |
| Reynolds RCI | Not started | | | | | | | |

Sources checked (Sep 2026): Fortellis App Launch Guide and API licensing terms (cdkglobal.com), Cox Automotive VinSolutions Integration Agreement (coxautoinc.com/terms), Reynolds Data Management and RCI pages (reyrey.com), DriveCentric Partner Program page, Tekion APC (apc.tekioncloud.com), public API report cards for DealerSocket/DriveCentric/VinSolutions.
