"""
Legal Documents router - Terms of Service, Privacy Policy
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/legal", tags=["legal"])

# Last updated date
LAST_UPDATED = "February 19, 2026"
COMPANY_NAME = "iMos"
COMPANY_EMAIL = "legal@imonsocial.com"
COMPANY_ADDRESS = "Salt Lake City, Utah"

TERMS_OF_SERVICE = f"""
# Terms of Service

**Last Updated: {LAST_UPDATED}**

Welcome to {COMPANY_NAME}. These Terms of Service ("Terms") govern your access to and use of the {COMPANY_NAME} platform, mobile applications, and services (collectively, the "Service"). By accessing or using our Service, you agree to be bound by these Terms.

## 1. Acceptance of Terms

By creating an account, accessing, or using {COMPANY_NAME}, you acknowledge that you have read, understood, and agree to be bound by these Terms and our Privacy Policy. If you do not agree to these Terms, you may not access or use the Service.

If you are using the Service on behalf of a business or organization, you represent and warrant that you have the authority to bind that entity to these Terms.

## 2. Description of Service

{COMPANY_NAME} provides a relationship management system (RMS) and communication platform designed for sales professionals, including:

- Contact management and organization
- SMS/MMS messaging capabilities
- Campaign automation and nurture sequences
- Digital business cards and review collection
- AI-powered communication assistance
- Appointment scheduling and calendar integration
- Performance tracking and analytics

## 3. Account Registration

### 3.1 Eligibility
You must be at least 18 years old and capable of entering into a legally binding agreement to use the Service. By using {COMPANY_NAME}, you represent that you meet these requirements.

### 3.2 Account Information
You agree to provide accurate, current, and complete information during registration and to update such information to keep it accurate, current, and complete. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.

### 3.3 Account Security
You must notify us immediately of any unauthorized use of your account or any other breach of security. We will not be liable for any loss or damage arising from your failure to protect your account information.

## 4. Acceptable Use Policy

### 4.1 Permitted Use
You may use the Service only for lawful purposes and in accordance with these Terms. You agree to use the Service only for legitimate business communications with customers who have consented to receive such communications.

### 4.2 Prohibited Activities
You agree NOT to:

- Use the Service to send unsolicited messages (spam) or violate anti-spam laws
- Violate the Telephone Consumer Protection Act (TCPA) or similar regulations
- Send messages to individuals who have not provided proper consent
- Use the Service for any illegal, harmful, or fraudulent purpose
- Transmit any material that is defamatory, obscene, or offensive
- Impersonate any person or entity or misrepresent your affiliation
- Interfere with or disrupt the Service or servers
- Attempt to gain unauthorized access to any part of the Service
- Use automated systems to access the Service without permission
- Collect or harvest any information from the Service without authorization
- Use the Service to compete with {COMPANY_NAME}

### 4.3 Messaging Compliance
When using our messaging features, you must:

- Obtain proper consent before sending any messages
- Maintain records of consent for all recipients
- Honor opt-out requests within 24 hours
- Include proper identification in all messages
- Comply with all applicable telecommunications laws and regulations
- Follow carrier guidelines and best practices

## 5. SMS/MMS Messaging Terms

### 5.1 Consent Requirements
You represent and warrant that you have obtained all necessary consents from recipients before sending any SMS or MMS messages through our Service. This includes:

- Express written consent for marketing messages
- Clear disclosure of message frequency and content
- Easy opt-out mechanisms in every message

### 5.2 TCPA Compliance
You acknowledge that violation of the TCPA can result in significant penalties. You agree to:

- Maintain a do-not-call list and honor all opt-out requests
- Send messages only during appropriate hours
- Clearly identify yourself and your business in messages
- Not use automatic telephone dialing systems for marketing without consent

### 5.3 Message Content
You are solely responsible for the content of all messages sent through the Service. {COMPANY_NAME} does not review or approve message content before transmission.

## 6. AI Features and Automation

### 6.1 AI-Assisted Communications
{COMPANY_NAME} may offer AI-powered features to assist with message composition and customer interactions. You acknowledge that:

- AI suggestions are tools to assist you, not replace your judgment
- You are responsible for reviewing and approving all AI-generated content
- AI features may not be perfect and may occasionally produce errors
- You should not rely solely on AI for critical business decisions

### 6.2 Automation Responsibility
When using campaign automation features, you remain responsible for:

- The content and timing of automated messages
- Ensuring compliance with all applicable laws
- Monitoring and adjusting campaigns as needed
- Responding to customer inquiries and opt-outs promptly

## 7. Data and Privacy

### 7.1 Your Data
You retain ownership of all data you upload or input into the Service ("Your Data"). By using the Service, you grant {COMPANY_NAME} a limited license to use Your Data solely to provide the Service to you.

### 7.2 Data Security
We implement reasonable security measures to protect Your Data. However, no system is completely secure, and we cannot guarantee absolute security.

### 7.3 Data Retention
We retain Your Data for as long as your account is active or as needed to provide the Service. Upon account termination, we will delete Your Data in accordance with our data retention policies.

### 7.4 Privacy Policy
Our collection and use of personal information is governed by our Privacy Policy, which is incorporated into these Terms by reference.

## 8. Intellectual Property

### 8.1 {COMPANY_NAME} Property
The Service, including all software, designs, text, graphics, and other content, is owned by {COMPANY_NAME} and protected by intellectual property laws. You may not copy, modify, distribute, or create derivative works without our express permission.

### 8.2 Feedback
If you provide feedback, suggestions, or ideas about the Service, you grant {COMPANY_NAME} a perpetual, irrevocable, royalty-free license to use such feedback for any purpose.

### 8.3 Trademarks
{COMPANY_NAME} and related logos are trademarks of {COMPANY_NAME}. You may not use our trademarks without prior written consent.

## 9. Payment Terms

### 9.1 Fees
You agree to pay all applicable fees for the Service as described in our pricing. Fees are non-refundable except as expressly stated in these Terms.

### 9.2 Billing
We will bill you in accordance with your selected plan. You authorize us to charge your payment method for all fees incurred.

### 9.3 Price Changes
We may change our fees upon 30 days' notice. Continued use of the Service after a price change constitutes acceptance of the new pricing.

### 9.4 Taxes
You are responsible for all applicable taxes. If we are required to collect taxes, they will be added to your invoice.

## 10. Third-Party Services

### 10.1 Integrations
The Service may integrate with third-party services. Your use of such services is subject to their respective terms and policies.

### 10.2 No Endorsement
Integration with third-party services does not constitute an endorsement by {COMPANY_NAME}. We are not responsible for the actions or content of third parties.

## 11. Disclaimers

### 11.1 "As Is" Service
THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.

### 11.2 No Guarantee
We do not guarantee that the Service will be uninterrupted, error-free, or secure. We are not responsible for any delays, delivery failures, or other damage resulting from use of the Service.

### 11.3 Message Delivery
We do not guarantee delivery of any messages sent through the Service. Message delivery depends on carriers and other factors beyond our control.

## 12. Limitation of Liability

### 12.1 Exclusion of Damages
TO THE MAXIMUM EXTENT PERMITTED BY LAW, {COMPANY_NAME} SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOSS OF PROFITS, DATA, OR BUSINESS OPPORTUNITIES.

### 12.2 Cap on Liability
OUR TOTAL LIABILITY FOR ANY CLAIMS ARISING FROM THESE TERMS OR THE SERVICE SHALL NOT EXCEED THE AMOUNT YOU PAID TO {COMPANY_NAME} IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.

### 12.3 Essential Purpose
These limitations apply even if any remedy fails of its essential purpose.

## 13. Indemnification

You agree to indemnify, defend, and hold harmless {COMPANY_NAME}, its officers, directors, employees, and agents from any claims, damages, losses, or expenses (including reasonable attorneys' fees) arising from:

- Your use of the Service
- Your violation of these Terms
- Your violation of any laws or regulations
- Your violation of any third-party rights
- Messages or content you send through the Service

## 14. Termination

### 14.1 By You
You may terminate your account at any time by contacting us or through your account settings. Termination does not relieve you of any obligations incurred before termination.

### 14.2 By Us
We may suspend or terminate your account at any time for any reason, including violation of these Terms. We will provide notice when reasonable under the circumstances.

### 14.3 Effect of Termination
Upon termination, your right to use the Service will immediately cease. Provisions that by their nature should survive termination will survive.

## 15. Dispute Resolution

### 15.1 Informal Resolution
Before filing any formal dispute, you agree to contact us and attempt to resolve the dispute informally for at least 30 days.

### 15.2 Arbitration
Any dispute not resolved informally shall be resolved by binding arbitration in accordance with the American Arbitration Association's rules. The arbitration shall take place in Salt Lake City, Utah.

### 15.3 Class Action Waiver
YOU AGREE TO RESOLVE DISPUTES ONLY ON AN INDIVIDUAL BASIS AND WAIVE ANY RIGHT TO PARTICIPATE IN A CLASS ACTION.

### 15.4 Exceptions
Either party may seek injunctive relief in court for intellectual property violations or unauthorized access to the Service.

## 16. General Provisions

### 16.1 Governing Law
These Terms are governed by the laws of the State of Utah, without regard to conflict of law principles.

### 16.2 Entire Agreement
These Terms, together with our Privacy Policy, constitute the entire agreement between you and {COMPANY_NAME} regarding the Service.

### 16.3 Severability
If any provision of these Terms is found unenforceable, the remaining provisions will continue in effect.

### 16.4 Waiver
Our failure to enforce any provision of these Terms does not constitute a waiver of that provision.

### 16.5 Assignment
You may not assign these Terms without our prior written consent. We may assign these Terms without restriction.

### 16.6 Notices
We may provide notices through the Service, email, or other reasonable means. You may contact us at {COMPANY_EMAIL}.

### 16.7 Force Majeure
We are not liable for any delay or failure due to causes beyond our reasonable control.

## 17. Changes to Terms

We may modify these Terms at any time. We will notify you of material changes by email or through the Service. Your continued use of the Service after changes take effect constitutes acceptance of the modified Terms.

## 18. Contact Information

If you have questions about these Terms, please contact us:

**{COMPANY_NAME}**
Email: {COMPANY_EMAIL}
Address: {COMPANY_ADDRESS}

---

By using {COMPANY_NAME}, you acknowledge that you have read, understood, and agree to these Terms of Service.
"""

PRIVACY_POLICY = f"""
# Privacy Policy

**Last Updated: {LAST_UPDATED}**

{COMPANY_NAME} ("we," "us," or "our") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our platform and services.

## 1. Information We Collect

### 1.1 Information You Provide

**Account Information:**
- Name, email address, phone number
- Company/organization name
- Job title and role
- Billing and payment information
- Profile photo and bio

**Contact Data:**
- Names, phone numbers, and email addresses of your contacts
- Communication history and notes
- Tags and custom fields you create
- Appointment and task information

**Communication Content:**
- Messages sent and received through our platform
- Campaign content and templates
- Voice recordings (if voice features are used)

**Business Information:**
- Store/dealership information
- Business hours and location
- Review links and social media profiles

### 1.2 Information Collected Automatically

**Usage Data:**
- Features accessed and actions taken
- Time spent on the platform
- Device and browser information
- IP address and location data
- Referral sources

**Technical Data:**
- Device identifiers
- Operating system and version
- Browser type and version
- Mobile network information

**Cookies and Tracking:**
- Session cookies for authentication
- Preference cookies for settings
- Analytics cookies for improvement

### 1.3 Information from Third Parties

- OAuth providers (Google, etc.) for single sign-on
- Payment processors for billing
- RMS and DMS integrations you authorize
- Public business information

## 2. How We Use Your Information

### 2.1 To Provide the Service

- Create and manage your account
- Process and deliver messages
- Execute automated campaigns
- Generate AI-assisted content
- Provide customer support

### 2.2 To Improve the Service

- Analyze usage patterns and trends
- Develop new features and functionality
- Fix bugs and technical issues
- Optimize performance

### 2.3 To Communicate With You

- Send service-related announcements
- Provide updates about your account
- Respond to inquiries and requests
- Send marketing communications (with consent)

### 2.4 For Business Operations

- Process payments and billing
- Prevent fraud and abuse
- Enforce our Terms of Service
- Comply with legal obligations

### 2.5 AI and Machine Learning

- Improve AI suggestion accuracy
- Train models on anonymized data
- Enhance natural language processing
- Personalize user experience

## 3. How We Share Your Information

### 3.1 Service Providers

We share information with vendors who help us operate the Service:

- Cloud hosting providers (data storage)
- Payment processors (billing)
- Communication providers (SMS/MMS delivery)
- Analytics services (usage tracking)
- AI/ML providers (content generation)

### 3.2 Business Partners

With your authorization, we may share data with:

- RMS systems you integrate
- DMS platforms you connect
- Calendar applications
- Other third-party tools you enable

### 3.3 Your Contacts

When you send messages through our platform:

- Recipients receive your communications
- Your business information may be shared
- Digital business cards display your profile

### 3.4 Legal Requirements

We may disclose information:

- To comply with laws and regulations
- To respond to legal process
- To protect rights and safety
- To investigate potential violations

### 3.5 Business Transfers

In the event of a merger, acquisition, or sale of assets, your information may be transferred as a business asset.

## 4. Data Security

### 4.1 Security Measures

We implement appropriate security measures including:

- Encryption of data in transit (TLS/SSL)
- Encryption of data at rest
- Access controls and authentication
- Regular security assessments
- Employee training on data protection

### 4.2 Your Responsibilities

You are responsible for:

- Maintaining strong passwords
- Protecting your account credentials
- Reporting unauthorized access
- Keeping your devices secure

### 4.3 No Guarantee

While we strive to protect your information, no method of transmission or storage is 100% secure. We cannot guarantee absolute security.

## 5. Data Retention

### 5.1 Active Accounts

We retain your data for as long as your account is active and as needed to provide the Service.

### 5.2 Terminated Accounts

After account termination:

- Account data is retained for 30 days for reactivation
- Some data may be retained longer for legal compliance
- Anonymized data may be retained for analytics

### 5.3 Communication Records

Message records are retained in accordance with telecommunications regulations and your subscription plan.

## 6. Your Rights and Choices

### 6.1 Access and Portability

You can:

- Access your account data through settings
- Export your contacts and communications
- Request a copy of your data

### 6.2 Correction

You can update or correct your information through your account settings or by contacting us.

### 6.3 Deletion

You can:

- Delete individual contacts and messages
- Request deletion of your account
- Request erasure of personal data (subject to legal obligations)

### 6.4 Opt-Out

You can:

- Unsubscribe from marketing emails
- Disable optional cookies
- Opt out of certain data sharing

### 6.5 Restriction

You can request that we restrict processing of your data in certain circumstances.

## 7. Children's Privacy

The Service is not intended for children under 18. We do not knowingly collect information from children. If we learn that we have collected information from a child, we will delete it promptly.

## 8. International Data Transfers

If you access the Service from outside the United States, your information may be transferred to and processed in the United States. By using the Service, you consent to such transfers.

## 9. California Privacy Rights

If you are a California resident, you have additional rights under the California Consumer Privacy Act (CCPA):

- Right to know what personal information is collected
- Right to know if personal information is sold or disclosed
- Right to opt out of the sale of personal information
- Right to delete personal information
- Right to non-discrimination for exercising your rights

To exercise these rights, contact us at {COMPANY_EMAIL}.

## 10. GDPR Rights (European Users)

If you are in the European Economic Area, you have rights under GDPR including:

- Right of access
- Right to rectification
- Right to erasure
- Right to restrict processing
- Right to data portability
- Right to object
- Rights related to automated decision-making

## 11. SMS/Messaging Privacy

### 11.1 Message Content

We process message content to:

- Deliver your communications
- Provide AI suggestions
- Enforce our policies
- Comply with law enforcement requests

### 11.2 Carrier Data

We receive delivery status information from carriers. This data is used to:

- Confirm message delivery
- Troubleshoot delivery issues
- Optimize delivery routes

### 11.3 Opt-Out Handling

We process opt-out requests to ensure compliance with your contacts' preferences and applicable laws.

## 12. Cookies Policy

### 12.1 Types of Cookies

**Essential Cookies:** Required for basic functionality
**Preference Cookies:** Remember your settings
**Analytics Cookies:** Help us improve the Service
**Marketing Cookies:** Enable targeted advertising (optional)

### 12.2 Managing Cookies

You can manage cookies through:

- Browser settings
- Our cookie preference center
- Third-party opt-out tools

## 13. Third-Party Links

The Service may contain links to third-party websites. We are not responsible for their privacy practices. We encourage you to review their privacy policies.

## 14. Changes to This Policy

We may update this Privacy Policy from time to time. We will notify you of material changes by:

- Email notification
- In-app announcement
- Posting the updated policy

Your continued use after changes constitutes acceptance of the updated policy.

## 15. Contact Us

If you have questions about this Privacy Policy or our data practices, please contact us:

**{COMPANY_NAME}**
Email: {COMPANY_EMAIL}
Address: {COMPANY_ADDRESS}

For data protection inquiries, you may also contact our Data Protection Officer at: dpo@imonsocial.com

---

By using {COMPANY_NAME}, you acknowledge that you have read and understood this Privacy Policy.
"""

CUSTOMER_TERMS = f"""
# Customer Terms of Use

**Last Updated: {LAST_UPDATED}**

These terms apply when you interact with {COMPANY_NAME} services as a customer of one of our business users, including when you:

- View a digital business card
- Submit a review or feedback
- Receive SMS/MMS messages
- Schedule appointments

## 1. Message Consent

By providing your phone number to a {COMPANY_NAME} user (salesperson/business), you consent to receive:

- Informational messages about your inquiry or transaction
- Follow-up communications related to your business relationship
- Marketing messages (if you opted in)

## 2. Opting Out

You can stop receiving messages at any time by:

- Replying STOP to any message
- Contacting the business directly
- Using the opt-out link in messages

## 3. Message Frequency

Message frequency varies based on your interactions and any campaigns you're enrolled in. Standard message and data rates may apply.

## 4. Your Information

When you interact with our platform:

- Your contact information is stored by the business user
- Your feedback/reviews may be shared (with your consent)
- Your data is protected by our Privacy Policy

## 5. Review Submissions

When submitting reviews:

- Be honest and accurate
- Don't include personal information of others
- Don't use defamatory or offensive language
- Your review may be shared publicly (if you consent)

## 6. Digital Business Cards

When you save a contact from a digital business card:

- You may be enrolled in follow-up communications
- You can opt out at any time
- The business receives notification of your interaction

## 7. Privacy

Your privacy is important. The business you're interacting with is responsible for their use of your data. Our Privacy Policy explains how {COMPANY_NAME} handles data on our platform.

## 8. Contact

For questions about communications you've received, contact the business directly. For questions about {COMPANY_NAME}, email us at {COMPANY_EMAIL}.
"""


@router.get("/terms")
async def get_terms_of_service():
    """Get Terms of Service content"""
    return {
        "title": "Terms of Service",
        "last_updated": LAST_UPDATED,
        "content": TERMS_OF_SERVICE,
    }


@router.get("/privacy")
async def get_privacy_policy():
    """Get Privacy Policy content"""
    return {
        "title": "Privacy Policy",
        "last_updated": LAST_UPDATED,
        "content": PRIVACY_POLICY,
    }


@router.get("/customer-terms")
async def get_customer_terms():
    """Get Customer-facing Terms content"""
    return {
        "title": "Customer Terms of Use",
        "last_updated": LAST_UPDATED,
        "content": CUSTOMER_TERMS,
    }


@router.get("/all")
async def get_all_legal_documents():
    """Get all legal documents"""
    return {
        "terms_of_service": {
            "title": "Terms of Service",
            "last_updated": LAST_UPDATED,
            "content": TERMS_OF_SERVICE,
        },
        "privacy_policy": {
            "title": "Privacy Policy",
            "last_updated": LAST_UPDATED,
            "content": PRIVACY_POLICY,
        },
        "customer_terms": {
            "title": "Customer Terms of Use",
            "last_updated": LAST_UPDATED,
            "content": CUSTOMER_TERMS,
        },
    }
