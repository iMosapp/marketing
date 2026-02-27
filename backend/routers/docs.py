"""
Company Documents Router
Admin-only document hub: Security Policy, Company Policy, ToS, Privacy, Training, Integrations
"""
from fastapi import APIRouter, HTTPException, Header
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/docs", tags=["Docs"])
logger = logging.getLogger(__name__)


async def verify_admin_access(user_id: str) -> dict:
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/")
async def list_docs(
    category: Optional[str] = None,
    search: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    await verify_admin_access(x_user_id)
    db = get_db()

    query: dict = {"is_published": True}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
        ]

    docs = await db.company_docs.find(query, {"slides": 0}).sort([
        ("sort_order", 1),
        ("title", 1),
    ]).to_list(100)

    for d in docs:
        d["_id"] = str(d["_id"])

    return docs


@router.get("/categories")
async def get_categories(x_user_id: str = Header(None, alias="X-User-ID")):
    await verify_admin_access(x_user_id)
    return [
        {"id": "operations", "name": "Operations Manual", "icon": "book", "color": "#00C7BE"},
        {"id": "security", "name": "Cyber Security", "icon": "shield-checkmark", "color": "#FF3B30"},
        {"id": "company_policy", "name": "Company Policy", "icon": "business", "color": "#5856D6"},
        {"id": "legal", "name": "Legal", "icon": "document-text", "color": "#007AFF"},
        {"id": "training", "name": "Training", "icon": "school", "color": "#34C759"},
        {"id": "integrations", "name": "Integrations", "icon": "git-network", "color": "#FF9500"},
    ]


@router.get("/{doc_id}")
async def get_doc(doc_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    await verify_admin_access(x_user_id)
    db = get_db()

    doc = await db.company_docs.find_one({"_id": ObjectId(doc_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/seed")
async def seed_docs(x_user_id: str = Header(None, alias="X-User-ID")):
    """Seed all company documents - super_admin only"""
    user = await verify_admin_access(x_user_id)
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    db = get_db()
    count = await db.company_docs.count_documents({})
    if count > 0:
        return {"message": f"Docs already seeded ({count} found). Delete to re-seed."}

    now = datetime.utcnow()

    docs = [
        # ====== CYBER SECURITY POLICY ======
        {
            "title": "Cyber Security Policy",
            "summary": "Comprehensive security standards for protecting company and customer data.",
            "category": "security",
            "icon": "shield-checkmark",
            "sort_order": 1,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Purpose & Scope",
                    "description": "This Cyber Security Policy establishes the security standards and practices that all i'M On Social (iMOs) employees, contractors, and partners must follow.\n\nThis policy applies to:\n\n- All employees and contractors\n- All company-owned devices and systems\n- All customer data handled by iMOs\n- All third-party integrations and services\n\nViolations of this policy may result in disciplinary action, up to and including termination.",
                    "tip": "Security is everyone's responsibility. If you see something, say something."
                },
                {
                    "order": 2,
                    "title": "Data Classification",
                    "description": "All data handled by iMOs is classified into the following categories:\n\n**Confidential**\n- Customer PII (names, emails, phone numbers)\n- Authentication credentials and API keys\n- Financial and billing information\n- Internal business strategies\n\n**Internal**\n- Employee contact information\n- Internal communications\n- Training materials and SOPs\n- System configurations\n\n**Public**\n- Marketing materials\n- Published review pages\n- Digital business cards (user-approved content only)",
                    "warning": "Never share Confidential data via unsecured channels (personal email, SMS, social media)."
                },
                {
                    "order": 3,
                    "title": "Access Control",
                    "description": "Access to systems and data follows the principle of least privilege:\n\n- Employees receive only the access necessary for their role\n- Admin access requires approval from a super admin\n- All access is logged and auditable\n- Access is revoked immediately upon termination or role change\n\n**Password Requirements:**\n- Minimum 12 characters\n- Mix of uppercase, lowercase, numbers, and symbols\n- No password reuse across systems\n- Passwords must be changed every 90 days\n- Multi-factor authentication (MFA) required for all admin accounts"
                },
                {
                    "order": 4,
                    "title": "Data Encryption",
                    "description": "All sensitive data must be encrypted:\n\n**In Transit:**\n- All API communications use TLS 1.2+ (HTTPS)\n- WebSocket connections are encrypted (WSS)\n- Email communications use TLS\n\n**At Rest:**\n- Database encryption enabled (MongoDB Atlas)\n- Backups are encrypted\n- API keys stored as environment variables, never in code\n\n**Key Management:**\n- API keys rotated quarterly\n- Compromised keys revoked immediately\n- Keys never committed to version control"
                },
                {
                    "order": 5,
                    "title": "Incident Response",
                    "description": "In the event of a security incident:\n\n**Step 1: Identify**\nRecognize and confirm the incident. Common indicators:\n- Unusual account activity\n- Unauthorized data access\n- System performance anomalies\n- Reports from users or third parties\n\n**Step 2: Contain**\n- Isolate affected systems immediately\n- Revoke compromised credentials\n- Preserve evidence (logs, screenshots)\n\n**Step 3: Report**\n- Notify your manager immediately\n- Contact: security@imosapp.com\n- Document timeline of events\n\n**Step 4: Recover**\n- Restore from clean backups\n- Patch vulnerabilities\n- Monitor for recurrence\n\n**Step 5: Review**\n- Post-incident analysis within 48 hours\n- Update policies as needed\n- Communicate lessons learned",
                    "warning": "Report all suspected incidents within 1 hour. Delayed reporting increases risk."
                },
                {
                    "order": 6,
                    "title": "Third-Party & Integration Security",
                    "description": "All third-party services must meet our security standards:\n\n**Approved Services:**\n- MongoDB Atlas (database)\n- Resend (email delivery)\n- Twilio (SMS/voice)\n- OpenAI (AI features)\n- Emergent (hosting & object storage)\n\n**Requirements for new integrations:**\n- SOC 2 compliance or equivalent\n- Data processing agreement (DPA)\n- API key authentication (no shared passwords)\n- Regular security audits\n- Data residency compliance\n\n**Webhook Security:**\n- All outgoing webhooks use HMAC signatures\n- Webhook secrets rotated quarterly\n- Delivery logs retained for 30 days"
                },
                {
                    "order": 7,
                    "title": "Employee Responsibilities",
                    "description": "Every team member must:\n\n- Complete security awareness training annually\n- Report suspicious activity immediately\n- Lock devices when unattended\n- Use company-approved tools only\n- Never share login credentials\n- Keep software and systems updated\n- Use VPN when on public networks\n- Verify identity before sharing sensitive information\n\n**Prohibited Actions:**\n- Storing customer data on personal devices\n- Using personal email for company business\n- Installing unauthorized software on company devices\n- Sharing API keys or credentials via chat/email\n- Bypassing security controls",
                    "tip": "When in doubt, ask before you act. It's always better to verify than to assume."
                },
            ],
            "created_at": now,
        },

        # ====== COMPANY POLICY ======
        {
            "title": "Company Policy & Code of Conduct",
            "summary": "Guidelines for professional conduct, workplace standards, and company expectations.",
            "category": "company_policy",
            "icon": "business",
            "sort_order": 2,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Our Mission",
                    "description": "i'M On Social (iMOs) empowers sales professionals with intelligent communication tools that build lasting customer relationships.\n\nOur core values:\n\n- **Innovation** - We push boundaries in sales technology\n- **Integrity** - We handle customer data with the highest ethical standards\n- **Impact** - Every feature we build drives real results for our users\n- **Inclusion** - We build for everyone and welcome diverse perspectives",
                },
                {
                    "order": 2,
                    "title": "Professional Conduct",
                    "description": "All team members are expected to:\n\n- Treat colleagues, customers, and partners with respect\n- Communicate professionally in all channels\n- Be punctual and reliable\n- Take ownership of your work and mistakes\n- Collaborate openly and share knowledge\n- Maintain confidentiality of company and customer information\n\n**Zero Tolerance:**\n- Harassment or discrimination of any kind\n- Retaliation against anyone who reports concerns\n- Misuse of customer data\n- Fraudulent activity",
                    "warning": "Violations of the code of conduct will be investigated and may result in immediate termination."
                },
                {
                    "order": 3,
                    "title": "Communication Standards",
                    "description": "**Internal Communication:**\n- Use designated channels (Slack, team chat)\n- Respond to messages within 4 business hours\n- Use clear, concise language\n- Mark urgent items appropriately\n\n**Customer Communication:**\n- Always professional and courteous\n- Response time: within 2 business hours\n- Use approved templates when available\n- Never promise features or timelines without approval\n- All customer communications are logged and auditable\n\n**External Communication:**\n- Social media posts about iMOs require approval\n- Press inquiries go to management\n- Represent the company positively at all times",
                },
                {
                    "order": 4,
                    "title": "Remote Work & Equipment",
                    "description": "**Remote Work:**\n- Maintain regular working hours and availability\n- Keep your work environment professional for video calls\n- Use secure, private networks for company work\n- VPN required on public Wi-Fi\n\n**Company Equipment:**\n- Keep devices updated and secured\n- Report lost or stolen devices immediately\n- Return all equipment upon departure\n- Personal use should not interfere with work functionality\n\n**Software:**\n- Only install approved applications\n- Keep all software updated\n- Use company accounts for work tools",
                },
                {
                    "order": 5,
                    "title": "Performance & Growth",
                    "description": "We invest in our team's growth:\n\n- Regular 1:1 meetings with your manager\n- Quarterly performance reviews\n- Training budget available for professional development\n- Clear career progression paths\n\n**Expectations:**\n- Meet deadlines and deliverables\n- Proactively communicate blockers\n- Seek feedback and act on it\n- Mentor others when possible\n- Stay current with industry trends",
                    "tip": "Your growth directly impacts our customers' success. Never stop learning."
                },
            ],
            "created_at": now,
        },

        # ====== TERMS OF SERVICE ======
        {
            "title": "Terms of Service",
            "summary": "Legal terms governing the use of the iMOs platform and services.",
            "category": "legal",
            "icon": "document-text",
            "sort_order": 3,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Agreement to Terms",
                    "description": "By accessing or using the i'M On Social (\"iMOs\") platform, you agree to be bound by these Terms of Service.\n\n**Effective Date:** February 2026\n**Company:** i'M On Social\n**Contact:** support@imosapp.com\n**Address:** 1741 Lunford Ln, Riverton, UT\n\nIf you do not agree to these terms, you may not use the platform. We reserve the right to modify these terms at any time, with notice provided to active users.",
                },
                {
                    "order": 2,
                    "title": "Account & Eligibility",
                    "description": "**Eligibility:**\n- You must be 18 years or older\n- You must provide accurate, complete registration information\n- You are responsible for maintaining the security of your account\n\n**Account Responsibilities:**\n- Keep your password confidential\n- Notify us immediately of unauthorized access\n- You are responsible for all activity under your account\n- One account per person; no shared accounts\n\n**Account Termination:**\n- We may suspend or terminate accounts that violate these terms\n- You may close your account at any time\n- Upon termination, your data will be handled per our Data Retention Policy",
                },
                {
                    "order": 3,
                    "title": "Acceptable Use",
                    "description": "You agree NOT to use iMOs to:\n\n- Send spam or unsolicited messages\n- Harass, threaten, or intimidate any person\n- Transmit malware, viruses, or harmful code\n- Impersonate another person or entity\n- Violate any applicable laws or regulations (including TCPA, CAN-SPAM, GDPR)\n- Scrape, mine, or collect data from the platform\n- Reverse engineer or decompile any part of the platform\n- Share your account credentials with others\n- Use the platform for illegal activities\n\n**Messaging Compliance:**\n- All SMS/email campaigns must comply with TCPA and CAN-SPAM\n- Recipients must have opted in to receive communications\n- Unsubscribe mechanisms must be honored within 10 business days",
                    "warning": "Violations of acceptable use may result in immediate account termination without refund."
                },
                {
                    "order": 4,
                    "title": "Intellectual Property",
                    "description": "**Our Property:**\n- The iMOs platform, including all code, design, and content, is owned by i'M On Social\n- Our trademarks, logos, and brand elements may not be used without permission\n\n**Your Content:**\n- You retain ownership of content you create (messages, contacts, templates)\n- You grant iMOs a license to process and store your content as needed to provide the service\n- You are responsible for ensuring your content does not violate any third-party rights\n\n**AI-Generated Content:**\n- Content generated by Jessi AI is provided as-is\n- You are responsible for reviewing and approving AI suggestions before sending",
                },
                {
                    "order": 5,
                    "title": "Limitation of Liability",
                    "description": "**Service Availability:**\n- We strive for 99.9% uptime but do not guarantee uninterrupted service\n- Scheduled maintenance will be communicated in advance\n\n**Liability Cap:**\n- Our total liability is limited to the amount paid by you in the 12 months preceding the claim\n- We are not liable for indirect, incidental, or consequential damages\n\n**Indemnification:**\n- You agree to indemnify iMOs against claims arising from your use of the platform\n- This includes claims related to your content, your customers, and your compliance with applicable laws\n\n**Governing Law:**\n- These terms are governed by the laws of the State of Utah\n- Disputes will be resolved through binding arbitration in Salt Lake County, UT",
                },
            ],
            "created_at": now,
        },

        # ====== PRIVACY POLICY ======
        {
            "title": "Privacy Policy",
            "summary": "How we collect, use, store, and protect personal information.",
            "category": "legal",
            "icon": "lock-closed",
            "sort_order": 4,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Information We Collect",
                    "description": "**Account Information:**\n- Name, email, phone number\n- Company/dealership details\n- Profile photos and bio\n\n**Usage Data:**\n- Feature usage and interaction patterns\n- Device information and browser type\n- IP address and approximate location\n- Login times and session duration\n\n**Customer Data (stored on your behalf):**\n- Contact names, emails, phone numbers\n- Communication history (messages, emails)\n- Tags, notes, and custom fields\n- Activity events and touchpoints\n\n**Third-Party Data:**\n- Information from connected services (Twilio, Resend)\n- Review submissions from public review pages",
                },
                {
                    "order": 2,
                    "title": "How We Use Information",
                    "description": "We use collected information to:\n\n- Provide and maintain the iMOs platform\n- Process and deliver messages (SMS, email)\n- Generate activity reports and analytics\n- Power AI features (Jessi assistant, message suggestions)\n- Send service notifications and updates\n- Detect and prevent fraud or abuse\n- Improve our products and services\n\n**We do NOT:**\n- Sell your personal information to third parties\n- Use customer contact data for our own marketing\n- Share data with advertisers\n- Train general AI models on your private data",
                    "tip": "Your data is your data. We process it only to provide you the service you signed up for."
                },
                {
                    "order": 3,
                    "title": "Data Storage & Security",
                    "description": "**Where Data is Stored:**\n- Primary database: MongoDB Atlas (cloud-hosted)\n- File storage: Encrypted object storage\n- Backups: Encrypted, stored in geographically separate locations\n\n**Security Measures:**\n- TLS encryption for all data in transit\n- Database encryption at rest\n- Regular security audits and penetration testing\n- Role-based access control (RBAC)\n- Automated threat detection\n\n**Data Retention:**\n- Active account data retained while account is active\n- Deleted contacts: 30-day recovery window, then permanent deletion\n- Deactivated users: 6-month grace period before data purge\n- Logs and audit trails: retained for 12 months",
                },
                {
                    "order": 4,
                    "title": "Your Rights",
                    "description": "You have the right to:\n\n**Access** - Request a copy of all data we hold about you\n**Correction** - Update or correct inaccurate information\n**Deletion** - Request deletion of your account and data\n**Portability** - Export your data in a standard format\n**Restriction** - Limit how we process your data\n**Objection** - Object to specific processing activities\n\n**To exercise your rights:**\nEmail: privacy@imosapp.com\nResponse time: within 30 days\n\n**California Residents (CCPA):**\n- Right to know what data is collected\n- Right to delete personal information\n- Right to opt-out of data sale (we do not sell data)\n- Right to non-discrimination for exercising rights",
                },
                {
                    "order": 5,
                    "title": "Cookies & Tracking",
                    "description": "**Essential Cookies:**\n- Authentication tokens\n- Session management\n- Security (CSRF protection)\n\n**Analytics:**\n- Usage patterns to improve the product\n- Feature adoption metrics\n- Performance monitoring\n\n**Third-Party:**\n- Payment processing (Stripe)\n- Error tracking (for bug fixes)\n\nYou can manage cookie preferences in your browser settings. Note that disabling essential cookies may affect platform functionality.\n\n**Do Not Track:**\nWe respect DNT browser signals and do not engage in cross-site tracking.",
                },
            ],
            "created_at": now,
        },

        # ====== DATA RETENTION POLICY ======
        {
            "title": "Data Retention Policy",
            "summary": "How data is handled when users leave or accounts are deactivated.",
            "category": "company_policy",
            "icon": "server",
            "sort_order": 5,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Overview",
                    "description": "This policy outlines how iMOs handles data when users are deactivated, leave an organization, or request account deletion.\n\nOur approach prioritizes:\n- Data integrity for the organization\n- Privacy for departing individuals\n- Compliance with data protection regulations\n- Business continuity",
                },
                {
                    "order": 2,
                    "title": "User Deactivation",
                    "description": "When a user is deactivated (e.g., leaves the company):\n\n**Soft Delete (Immediate):**\n- Account status set to \"deactivated\"\n- Login access revoked\n- User removed from active team lists\n\n**Contact Ownership:**\n- Organization-owned contacts remain accessible to the org\n- Personal contacts (manually added) are hidden from org view\n- Original user ID preserved for audit trail\n\n**6-Month Grace Period:**\n- All data retained for 6 months\n- Account can be reactivated by an admin\n- Personal contacts can be reassigned to another user\n\n**After 6 Months:**\n- Personal data permanently purged\n- Organization data fully transferred to org ownership\n- Audit logs retained per compliance requirements",
                    "tip": "Always reassign important contacts before deactivating a user."
                },
                {
                    "order": 3,
                    "title": "Account Deletion",
                    "description": "When a user requests full account deletion:\n\n**Individual Users:**\n- All personal data removed within 30 days\n- Communication history anonymized (content deleted, metadata retained)\n- Public pages (review links, digital cards) deactivated\n\n**Organization Accounts:**\n- Owner must confirm deletion\n- All user accounts under the org are deactivated\n- Organization-owned data (contacts, campaigns) deleted\n- 30-day recovery window before permanent deletion\n\n**What is NOT Deleted:**\n- Submitted reviews (anonymized, kept for store ratings)\n- Aggregate analytics (no PII)\n- Legal/compliance audit logs (retained per legal hold requirements)",
                },
                {
                    "order": 4,
                    "title": "Data Backup & Recovery",
                    "description": "**Backup Schedule:**\n- Automated daily backups\n- Point-in-time recovery available (last 7 days)\n- Monthly archive snapshots (retained for 12 months)\n\n**Recovery Process:**\n- Data restoration requests: contact support@imosapp.com\n- Recovery from backup: available within 24 hours\n- Accidental deletion: 30-day recovery window for contacts\n\n**Disaster Recovery:**\n- Multi-region database replication\n- RTO (Recovery Time Objective): 4 hours\n- RPO (Recovery Point Objective): 1 hour\n- Tested quarterly",
                },
            ],
            "created_at": now,
        },

        # ====== SECURITY AWARENESS TRAINING ======
        {
            "title": "Security Awareness Training",
            "summary": "Essential security training for all employees. Covers phishing, passwords, and data handling.",
            "category": "training",
            "icon": "shield",
            "sort_order": 6,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Why Security Matters",
                    "description": "As a CRM platform, iMOs handles thousands of customer records including:\n\n- Phone numbers and email addresses\n- Communication history\n- Sales data and customer preferences\n\nA single breach can:\n- Expose customer PII\n- Destroy trust with our clients\n- Result in legal penalties (TCPA fines up to $1,500 per violation)\n- Damage our brand permanently\n\nSecurity isn't just IT's job. Every team member is a line of defense.",
                    "warning": "The average cost of a data breach in 2025 was $4.88 million (IBM). Prevention is always cheaper."
                },
                {
                    "order": 2,
                    "title": "Recognizing Phishing",
                    "description": "Phishing is the #1 attack vector. Watch for:\n\n**Red Flags in Emails:**\n- Urgent language (\"Act now!\", \"Your account will be locked\")\n- Sender address doesn't match the company domain\n- Links that go to unexpected URLs (hover before clicking)\n- Requests for passwords, API keys, or financial info\n- Unexpected attachments\n\n**What to Do:**\n- Don't click suspicious links\n- Don't download unexpected attachments\n- Report to security@imosapp.com\n- When in doubt, verify via a different channel (call the sender)\n\n**We will NEVER ask you to:**\n- Share your password via email or chat\n- Transfer money urgently\n- Click a link to \"verify\" your account",
                    "tip": "If an email creates urgency or fear, that's the biggest red flag. Slow down and verify."
                },
                {
                    "order": 3,
                    "title": "Password & Authentication Security",
                    "description": "**Strong Password Rules:**\n- 12+ characters minimum\n- Mix: uppercase, lowercase, numbers, symbols\n- Never reuse passwords across services\n- Use a password manager (recommended: 1Password, Bitwarden)\n\n**Multi-Factor Authentication (MFA):**\n- Required for all admin accounts\n- Recommended for all accounts\n- Use authenticator apps over SMS when possible\n\n**What NOT to Do:**\n- Write passwords on sticky notes\n- Share credentials with coworkers\n- Store passwords in plain text files\n- Use personal information in passwords (birthdays, pet names)\n- Save passwords in browser on shared devices",
                },
                {
                    "order": 4,
                    "title": "Safe Data Handling",
                    "description": "**Sharing Customer Data:**\n- Only share on need-to-know basis\n- Use internal tools (not personal email)\n- Never screenshot customer data unnecessarily\n- Redact sensitive info in support tickets\n\n**Working Remotely:**\n- Use VPN on public Wi-Fi\n- Lock your screen when away (even at home)\n- Don't use public computers for work\n- Keep work data on work devices only\n\n**API Keys & Credentials:**\n- Never put keys in code or chat messages\n- Use environment variables only\n- Rotate keys if you suspect exposure\n- Report accidentally exposed keys immediately",
                    "tip": "Treat every piece of customer data like it's your own personal information."
                },
                {
                    "order": 5,
                    "title": "Incident Reporting",
                    "description": "**When to Report:**\n- You clicked a suspicious link\n- You see unauthorized activity on any account\n- A device is lost or stolen\n- You accidentally shared sensitive data\n- You notice unusual system behavior\n- A customer reports suspicious activity\n\n**How to Report:**\n1. Email: security@imosapp.com\n2. Notify your direct manager\n3. Do NOT try to \"fix\" it yourself\n4. Preserve evidence (don't delete emails/messages)\n\n**Timeline:**\n- Report within 1 hour of discovery\n- Security team acknowledges within 2 hours\n- Investigation begins immediately\n\nThere are NO penalties for reporting in good faith. We'd rather have 10 false alarms than 1 missed incident.",
                },
            ],
            "created_at": now,
        },

        # ====== PLATFORM ONBOARDING ======
        {
            "title": "Platform Onboarding Guide",
            "summary": "Step-by-step guide for new employees to get started with the iMOs platform.",
            "category": "training",
            "icon": "rocket",
            "sort_order": 7,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Welcome to iMOs",
                    "description": "Welcome to the team! This guide will walk you through everything you need to know to get started with the iMOs platform.\n\niMOs is an AI-powered Relationship Management System built for sales professionals at dealerships. Our platform helps salespeople:\n\n- Manage customer relationships\n- Send digital business cards\n- Automate follow-up communications\n- Track all customer interactions\n- Share review links and collect feedback\n- Collaborate with their team",
                },
                {
                    "order": 2,
                    "title": "Setting Up Your Account",
                    "description": "**Step 1: Log In**\nUse the credentials provided by your admin to log in at app.imosapp.com\n\n**Step 2: Complete Your Profile**\nGo to More > My Account and fill in:\n- Your name and title\n- Profile photo\n- Contact information\n- Bio for your digital card\n\n**Step 3: Set Up Your AI Persona**\nGo to More > AI Persona to customize how Jessi (your AI assistant) communicates on your behalf.\n\n**Step 4: Review Your Digital Card**\nGo to More > My Digital Card to preview how customers see your digital business card.",
                    "tip": "A complete profile with a professional photo dramatically increases customer engagement."
                },
                {
                    "order": 3,
                    "title": "The Inbox",
                    "description": "The Inbox is your communication hub:\n\n**SMS Mode** (default)\n- Send text messages to customers\n- If you don't have a Twilio number, messages will open your phone's native SMS app\n- All messages are logged regardless of send method\n\n**Email Mode**\n- Switch using the 'Switch to Email' button\n- Sends branded HTML emails via Resend\n- Perfect for longer, professional communications\n\n**Quick Actions (bottom toolbar):**\n- Photo: Send MMS\n- Document: Send templates\n- Star: Send review request\n- Card: Share digital card\n- Mic: Voice note\n- AI: Get AI suggestions",
                },
                {
                    "order": 4,
                    "title": "Managing Contacts",
                    "description": "**Adding Contacts:**\n- Tap '+' on the Contacts tab\n- Import from phone contacts\n- Upload CSV files\n- Contacts auto-created from inbound messages\n\n**Contact Profile:**\n- Tap any contact to see their full profile\n- Activity feed shows all interactions\n- Add tags for organization\n- Quick actions: SMS, Email, Call, Card, Review\n\n**Tags:**\n- Use tags to organize contacts (e.g., 'sold', 'prospect', 'service')\n- Tags power automation and reporting\n- The 'sold' tag triggers AI follow-up suggestions",
                },
                {
                    "order": 5,
                    "title": "Key Features",
                    "description": "**Digital Business Card**\n- Shareable link with your info, reviews, and contact details\n- Customers can save your vCard directly\n\n**Review Requests**\n- Send review links to customers\n- Reviews appear on your public profile\n- Track review submissions in reports\n\n**Congrats Cards**\n- Send branded congratulations cards for sales milestones\n- Auto-generates tracking links\n\n**Activity Reports**\n- View your performance metrics\n- Track emails sent, SMS sent, cards shared\n- Available under More > Performance\n\n**Team Chat**\n- Collaborate with your team\n- Share updates and coordinate",
                },
            ],
            "created_at": now,
        },

        # ====== INTEGRATION DOCUMENTATION ======
        {
            "title": "Integration & API Documentation",
            "summary": "Technical documentation for iMOs integrations, webhooks, and public API.",
            "category": "integrations",
            "icon": "git-network",
            "sort_order": 8,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "API Overview",
                    "description": "iMOs provides a RESTful API for third-party CRM integrations.\n\n**Base URL:** https://app.imosapp.com/api/v1\n\n**Authentication:**\nAll requests require an API key in the header:\n```\nX-API-Key: your_api_key_here\n```\n\n**Rate Limits:**\n- 100 requests per minute per API key\n- 10,000 requests per day\n- Bulk operations count as 1 request\n\n**Response Format:**\nAll responses are JSON. Successful responses return 200/201. Errors return appropriate HTTP status codes with detail messages.",
                },
                {
                    "order": 2,
                    "title": "Contacts API",
                    "description": "**List Contacts**\nGET /api/v1/contacts\nQuery params: page, limit, search, tag, sort_by\n\n**Get Contact**\nGET /api/v1/contacts/{contact_id}\n\n**Create Contact**\nPOST /api/v1/contacts\nBody: { first_name, last_name, email, phone, tags[] }\n\n**Update Contact**\nPUT /api/v1/contacts/{contact_id}\nBody: any contact fields to update\n\n**Delete Contact**\nDELETE /api/v1/contacts/{contact_id}\n\n**Bulk Tag**\nPOST /api/v1/contacts/bulk/tag\nBody: { contact_ids[], tags[] }\n\n**Search**\nGET /api/v1/contacts/search?q=term\nSearches name, email, phone, tags",
                },
                {
                    "order": 3,
                    "title": "Messages & Conversations API",
                    "description": "**List Conversations**\nGET /api/v1/conversations\n\n**Get Messages**\nGET /api/v1/conversations/{id}/messages\n\n**Send Message**\nPOST /api/v1/messages/send\nBody: { contact_id, content, channel: 'sms'|'email' }\n\n**Message Channels:**\n- `sms` - Send via Twilio (requires provisioned number)\n- `email` - Send branded HTML email via Resend\n- `sms_personal` - Log message sent from personal phone\n\nAll sent messages are automatically logged as contact events for activity tracking and reporting.",
                },
                {
                    "order": 4,
                    "title": "Webhooks",
                    "description": "iMOs can send real-time notifications to your systems via webhooks.\n\n**Supported Events (21 types):**\n- contact.created / contact.updated / contact.deleted\n- message.sent / message.received\n- campaign.enrolled / campaign.completed\n- review.submitted / review.approved\n- user.created / user.deactivated\n- tag.added / tag.removed\n\n**Webhook Format:**\n```\nPOST your-endpoint-url\nX-Webhook-Signature: hmac_sha256_signature\nContent-Type: application/json\n\n{\n  event: 'contact.created',\n  timestamp: '2026-02-27T...',\n  data: { ... }\n}\n```\n\n**Security:**\n- All webhooks signed with HMAC-SHA256\n- Verify signature before processing\n- Delivery logs available for 30 days\n- Auto-retry on failure (3 attempts, exponential backoff)",
                },
                {
                    "order": 5,
                    "title": "Zapier & CRM Integration",
                    "description": "iMOs integrates with popular CRM platforms via our API and webhooks:\n\n**Zapier Integration:**\n- Use webhooks as triggers in Zapier\n- Use API endpoints as actions\n- Example: New contact in iMOs > Create lead in Salesforce\n- Example: Deal closed in HubSpot > Add 'sold' tag in iMOs\n\n**Common Integrations:**\n- Salesforce: Sync contacts and activity\n- HubSpot: Bi-directional contact sync\n- DealerSocket: Import customer data\n- VinSolutions: Lead routing\n\n**Getting Started:**\n1. Generate an API key in Settings > Integrations\n2. Set up webhook subscriptions for events you need\n3. Configure your CRM to send/receive data\n4. Test with a single contact before bulk operations",
                    "tip": "Start with contact sync first. Once that's reliable, add message and event tracking."
                },
                {
                    "order": 6,
                    "title": "Email Integration (Resend)",
                    "description": "iMOs uses Resend for all transactional email delivery.\n\n**Features:**\n- Branded HTML templates with your store's logo and colors\n- Automatic sender identification\n- Delivery tracking (sent, delivered, opened, clicked)\n- CTA buttons linking to your iMOs profile\n\n**Email Branding Hierarchy:**\n1. Partner branding (highest priority)\n2. Organization branding\n3. Store branding\n4. Default iMOs branding\n\n**Sender Address:**\nnoreply@imosapp.com (domain verified)\n\n**Customization:**\n- Logo, primary color, and accent color from your Brand Kit\n- Social media links from your store profile\n- Store address in the footer\n- Custom \"Powered By\" text for white-label partners",
                },
            ],
            "created_at": now,
        },
    ]

    result = await db.company_docs.insert_many(docs)
    return {"message": f"Seeded {len(result.inserted_ids)} documents"}
