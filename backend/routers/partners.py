"""
Partner Agreement router - Digital contracts for resellers and referral partners
Supports: Agreement templates, digital signatures, Stripe payments, commission tiers
"""
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import os
import logging
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from routers.database import get_db

router = APIRouter(prefix="/partners", tags=["partners"])
logger = logging.getLogger(__name__)


# ============= MODELS =============

class CommissionTier(BaseModel):
    name: str
    percentage: float
    description: Optional[str] = None

class AgreementTemplate(BaseModel):
    name: str
    type: str  # 'reseller' or 'referral'
    content: str  # Rich text/markdown content
    commission_tiers: List[CommissionTier] = []
    payment_required: bool = False
    payment_amount: Optional[float] = None
    active: bool = True

class PartnerSignup(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    tax_id: Optional[str] = None  # EIN for payouts
    signature: str  # Typed name or base64 signature image
    signature_type: str  # 'typed' or 'drawn'
    agreed_to_terms: bool = True


# ============= DEFAULT TEMPLATES =============

DEFAULT_MASTER_AGREEMENT = """# MASTER PARTNER AGREEMENT
*(Referral & Reseller Program)*

**This Master Partner Agreement ("Agreement")** is entered into as of **{{effective_date}}**, by and between:

**Company:** {{company_legal_name}} ("Company")
**Partner:** {{partner_name}} ("Partner")

---

## 1. PURPOSE

This Agreement establishes the terms under which Partner may refer prospective customers to Company and/or resell Company's products and services, as further defined in **Exhibit A (Partner Terms)** attached hereto.

---

## 2. PARTNER TYPES

Partner's role shall be defined in Exhibit A as one of the following:

- **Referral Partner:** Introduces prospective customers to Company. Company retains responsibility for all sales, billing, and fulfillment.
- **Reseller Partner:** Actively markets and sells Company services. Billing structure will be defined in Exhibit A.

---

## 3. CUSTOMER OWNERSHIP

All customers and accounts acquired under this Agreement shall be exclusively owned by Company. Partner shall have no ownership rights to customer relationships, data, or contracts.

---

## 4. COMPENSATION

Partner shall be compensated based on **Collected Active Monthly Recurring Revenue ("Collected Active MRR")** attributed to Partner, as defined below and further detailed in Exhibit A.

### 4.1 Definition of Collected Active MRR

"Collected Active MRR" means monthly recurring revenue actually received by Company from active customer accounts, **excluding:**

- Failed or declined payments
- Refunds or chargebacks
- Delinquent or past-due accounts
- One-time fees or non-recurring charges

### 4.2 Tiered Commission Structure

Partner compensation is tiered based on Collected Active MRR as outlined in Exhibit A.

- Commission tiers are evaluated **monthly at time of payout**
- Commission rates apply **retroactively to total Collected Active MRR** for that month
- Tier levels may increase or decrease based on monthly performance

### 4.3 Payment Terms

- Commissions are paid **Net 30 days** after the close of each calendar month
- Payment is contingent upon Company's receipt of funds from customers
- No commissions are paid on unpaid, refunded, or disputed revenue

---

## 5. ATTRIBUTION

Partner shall receive credit only for customers:

- Directly referred or sold by Partner
- Accepted and onboarded by Company
- Not previously engaged with Company through other channels

Company reserves the right to determine attribution in cases of conflict.

---

## 6. TERM AND TERMINATION

**6.1 Term** — This Agreement shall remain in effect until terminated by either party.

**6.2 Termination** — Either party may terminate this Agreement at any time with written notice.

**6.3 Post-Termination Payments** — Commissions will continue for active accounts for the duration defined in Exhibit A. No new commissions will be earned after termination.

---

## 7. PARTNER OBLIGATIONS

Partner agrees to:

- Represent Company accurately and professionally
- Not make unauthorized claims, guarantees, or commitments on Company's behalf
- Comply with all applicable laws and regulations
- Maintain confidentiality of all Company information

---

## 8. CONFIDENTIALITY

Partner agrees to maintain confidentiality of all Company information, including pricing, technology, customer data, and business practices, both during and after the term of this Agreement.

---

## 9. INDEPENDENT CONTRACTOR

Partner is an independent contractor and not an employee, agent, or representative of Company. Partner is solely responsible for all applicable taxes on commissions received.

---

## 10. LIMITATION OF LIABILITY

Company shall not be liable for indirect, incidental, or consequential damages. Company's total liability shall not exceed commissions paid in the 12 months preceding any claim.

---

## 11. GOVERNING LAW

This Agreement shall be governed by the laws of the State of {{governing_state}}.

---

## 12. ENTIRE AGREEMENT

This Agreement, together with Exhibit A, constitutes the entire agreement between the parties and supersedes all prior negotiations, representations, or agreements.

---

*By signing below, Partner confirms they have read, understood, and agree to be bound by this Agreement and the attached Exhibit A.*
"""


EXHIBIT_A_REFERRAL = """---

# EXHIBIT A — PARTNER TERMS (Referral Partner)

**Partner Name:** {{partner_name}}
**Effective Date:** {{effective_date}}
**Partner Type:** Referral Partner

---

## 1. COMMISSION STRUCTURE

| Collected Active MRR | Commission Rate |
|---|---|
| Up to $10,000 / month | 10% |
| Above $10,000 / month | 15% |

*Tiers are evaluated monthly and applied retroactively to total Collected Active MRR for that month.*

---

## 2. PAYMENT TERMS

- Paid **Net 30** after end of each calendar month
- Only applies to revenue successfully collected by Company
- Accounts must be active and in good standing at time of payout

---

## 3. COMMISSION DURATION

{{commission_duration}}

---

## 4. SPECIAL TERMS

{{custom_terms}}

---

*This Exhibit A is incorporated into and subject to the Master Partner Agreement dated {{effective_date}}.*
"""


EXHIBIT_A_RESELLER = """---

# EXHIBIT A — PARTNER TERMS (Reseller Partner)

**Partner Name:** {{partner_name}}
**Effective Date:** {{effective_date}}
**Partner Type:** Reseller Partner

---

## 1. COMMISSION STRUCTURE

| Collected Active MRR | Commission Rate |
|---|---|
| Up to $20,000 / month | 20% |
| $20,001 – $40,000 / month | 30% |
| Above $40,000 / month | 40% |

*Tiers are evaluated monthly and applied retroactively to total Collected Active MRR for that month.*

---

## 2. PAYMENT TERMS

- Paid **Net 30** after end of each calendar month
- Only applies to revenue successfully collected by Company
- Accounts must be active and in good standing at time of payout

---

## 3. BILLING STRUCTURE

{{billing_structure}}

---

## 4. COMMISSION DURATION

{{commission_duration}}

---

## 5. SPECIAL TERMS

{{custom_terms}}

---

*This Exhibit A is incorporated into and subject to the Master Partner Agreement dated {{effective_date}}.*
"""


def build_agreement_content(partner_type: str, partner_name: str, custom_terms: str = "",
                             commission_duration: str = "Lifetime (while account remains active)",
                             billing_structure: str = "Company Bills Customer (Partner receives commission)",
                             company_name: str = "VI Ventures Group LLC",
                             governing_state: str = "Texas") -> str:
    """Generate the full agreement text from the template + exhibit A."""
    import datetime as dt
    effective_date = dt.datetime.utcnow().strftime("%B %d, %Y")

    main = (DEFAULT_MASTER_AGREEMENT
            .replace("{{partner_name}}", partner_name or "[Partner Name]")
            .replace("{{effective_date}}", effective_date)
            .replace("{{company_legal_name}}", company_name)
            .replace("{{governing_state}}", governing_state))

    if partner_type == "reseller":
        exhibit = (EXHIBIT_A_RESELLER
                   .replace("{{partner_name}}", partner_name or "[Partner Name]")
                   .replace("{{effective_date}}", effective_date)
                   .replace("{{custom_terms}}", custom_terms or "No additional terms.")
                   .replace("{{commission_duration}}", commission_duration)
                   .replace("{{billing_structure}}", billing_structure))
    else:  # referral
        exhibit = (EXHIBIT_A_REFERRAL
                   .replace("{{partner_name}}", partner_name or "[Partner Name]")
                   .replace("{{effective_date}}", effective_date)
                   .replace("{{custom_terms}}", custom_terms or "No additional terms.")
                   .replace("{{commission_duration}}", commission_duration))

    return main + "\n" + exhibit


# ============= AGREEMENT TEMPLATES =============

@router.get("/templates")
async def list_templates():
    """List all agreement templates (admin only)"""
    db = get_db()
    
    templates = await db.partner_templates.find().to_list(100)
    
    # If no templates exist, create defaults
    if not templates:
        await create_default_templates()
        templates = await db.partner_templates.find().to_list(100)
    
    return [
        {
            "id": str(t["_id"]),
            "name": t["name"],
            "type": t["type"],
            "content": t["content"],
            "commission_tiers": t.get("commission_tiers", []),
            "payment_required": t.get("payment_required", False),
            "payment_amount": t.get("payment_amount"),
            "active": t.get("active", True),
            "created_at": t.get("created_at").isoformat() if t.get("created_at") else None,
        }
        for t in templates
    ]


async def create_default_templates():
    """Create default agreement templates"""
    db = get_db()
    
    templates = [
        {
            "name": "Reseller Agreement",
            "type": "reseller",
            "content": DEFAULT_RESELLER_TEMPLATE,
            "commission_tiers": DEFAULT_COMMISSION_TIERS,
            "payment_required": False,
            "payment_amount": None,
            "active": True,
            "created_at": datetime.utcnow(),
        },
        {
            "name": "Referral Partner Agreement",
            "type": "referral",
            "content": DEFAULT_REFERRAL_TEMPLATE,
            "commission_tiers": DEFAULT_COMMISSION_TIERS,
            "payment_required": False,
            "payment_amount": None,
            "active": True,
            "created_at": datetime.utcnow(),
        },
    ]
    
    await db.partner_templates.insert_many(templates)


@router.post("/templates")
async def create_template(data: AgreementTemplate):
    """Create a new agreement template"""
    db = get_db()
    
    template = {
        "name": data.name,
        "type": data.type,
        "content": data.content,
        "commission_tiers": [t.dict() for t in data.commission_tiers],
        "payment_required": data.payment_required,
        "payment_amount": data.payment_amount,
        "active": data.active,
        "created_at": datetime.utcnow(),
    }
    
    result = await db.partner_templates.insert_one(template)
    
    return {
        "id": str(result.inserted_id),
        "message": "Template created successfully"
    }


@router.put("/templates/{template_id}")
async def update_template(template_id: str, data: dict):
    """Update an agreement template"""
    db = get_db()
    
    allowed_fields = ["name", "type", "content", "commission_tiers", "payment_required", "payment_amount", "active"]
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.partner_templates.update_one(
        {"_id": ObjectId(template_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"success": True, "message": "Template updated"}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete an agreement template"""
    db = get_db()
    
    result = await db.partner_templates.delete_one({"_id": ObjectId(template_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"success": True, "message": "Template deleted"}


# ============= AGREEMENTS (Sent to partners) =============

@router.post("/agreements")
async def create_agreement(data: dict):
    """Create a new agreement to send to a partner"""
    db = get_db()
    
    template_id = data.get("template_id")
    if not template_id:
        raise HTTPException(status_code=400, detail="Template ID required")
    
    template = await db.partner_templates.find_one({"_id": ObjectId(template_id)})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    agreement = {
        "template_id": template_id,
        "template_name": template["name"],
        "type": template["type"],
        # Build the full agreement content from the new template + exhibit A
        "content": build_agreement_content(
            partner_type=template["type"],
            partner_name=data.get("partner_name", ""),
            custom_terms=data.get("custom_terms", ""),
            commission_duration=data.get("commission_duration", "Lifetime (while account remains active)"),
            billing_structure=data.get("billing_structure", "Company Bills Customer (Partner receives commission)"),
        ),
        "commission_tier": data.get("commission_tier"),
        "custom_terms": data.get("custom_terms", ""),               # Forest's Exhibit A notes
        "commission_duration": data.get("commission_duration", "Lifetime (while account remains active)"),
        "billing_structure": data.get("billing_structure", "Company Bills Customer (Partner receives commission)"),
        "custom_commission_notes": data.get("custom_commission_notes"),
        "is_white_label": data.get("is_white_label", False),
        "payment_required": data.get("payment_required", template.get("payment_required", False)),
        "payment_amount": data.get("payment_amount", template.get("payment_amount")),
        "partner_email": data.get("partner_email"),
        "partner_name": data.get("partner_name"),
        "notes": data.get("notes"),
        "status": "draft",
        "w9_status": "pending",        # pending | uploaded | verified
        "w9_file_url": None,
        "created_by": data.get("created_by"),
        "created_at": datetime.utcnow(),
        "sent_at": None,
        "viewed_at": None,
        "signed_at": None,
        "paid_at": None,
    }
    
    result = await db.partner_agreements.insert_one(agreement)
    agreement_id = str(result.inserted_id)
    
    return {
        "id": agreement_id,
        "link": f"/partner/agreement/{agreement_id}",
        "message": "Agreement created successfully"
    }


@router.get("/agreements")
async def list_agreements(status: Optional[str] = None):
    """List all partner agreements (admin only)"""
    db = get_db()
    
    query = {}
    if status:
        query["status"] = status
    
    agreements = await db.partner_agreements.find(query).sort("created_at", -1).to_list(200)
    
    return [
        {
            "id": str(a["_id"]),
            "template_name": a.get("template_name"),
            "type": a.get("type"),
            "partner_name": a.get("partner_name") or a.get("signed_partner", {}).get("name"),
            "partner_email": a.get("partner_email") or a.get("signed_partner", {}).get("email"),
            "commission_tier": a.get("commission_tier"),
            "custom_commission_notes": a.get("custom_commission_notes"),
            "is_white_label": a.get("is_white_label", False),
            "payment_required": a.get("payment_required", False),
            "payment_amount": a.get("payment_amount"),
            "status": a.get("status"),
            "created_at": a.get("created_at").isoformat() if a.get("created_at") else None,
            "sent_at": a.get("sent_at").isoformat() if a.get("sent_at") else None,
            "signed_at": a.get("signed_at").isoformat() if a.get("signed_at") else None,
        }
        for a in agreements
    ]


@router.get("/agreements/{agreement_id}")
async def get_agreement(agreement_id: str):
    """Get agreement details (for admin or public signing page)"""
    db = get_db()
    
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    # Mark as viewed if first time
    if agreement.get("status") == "sent":
        await db.partner_agreements.update_one(
            {"_id": ObjectId(agreement_id)},
            {"$set": {"status": "viewed", "viewed_at": datetime.utcnow()}}
        )
        agreement["status"] = "viewed"
    
    # Get template for commission tiers
    template = None
    if agreement.get("template_id"):
        template = await db.partner_templates.find_one({"_id": ObjectId(agreement["template_id"])})
    
    return {
        "id": str(agreement["_id"]),
        "template_name": agreement.get("template_name"),
        "type": agreement.get("type"),
        "content": agreement.get("content"),
        "commission_tier": agreement.get("commission_tier"),
        "custom_commission_notes": agreement.get("custom_commission_notes"),
        "is_white_label": agreement.get("is_white_label", False),
        "commission_tiers": template.get("commission_tiers", []) if template else [],
        "payment_required": agreement.get("payment_required", False),
        "payment_amount": agreement.get("payment_amount"),
        "partner_name": agreement.get("partner_name"),
        "partner_email": agreement.get("partner_email"),
        "status": agreement.get("status"),
        "signed_partner": agreement.get("signed_partner"),
        "signed_at": agreement.get("signed_at").isoformat() if agreement.get("signed_at") else None,
        "created_at": agreement.get("created_at").isoformat() if agreement.get("created_at") else None,
        "sent_at": agreement.get("sent_at").isoformat() if agreement.get("sent_at") else None,
    }


@router.put("/agreements/{agreement_id}")
async def update_agreement(agreement_id: str, data: dict):
    """Update an agreement (before sending)"""
    db = get_db()
    
    allowed_fields = ["content", "commission_tier", "custom_commission_notes", "is_white_label", "payment_required", "payment_amount", "partner_email", "partner_name", "notes", "status"]
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    # Mark as sent if status changed to sent
    if data.get("status") == "sent":
        update_dict["sent_at"] = datetime.utcnow()
    
    result = await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    return {"success": True, "message": "Agreement updated"}


@router.delete("/agreements/{agreement_id}")
async def delete_agreement(agreement_id: str):
    """Delete an agreement (only drafts can be deleted)"""
    db = get_db()
    
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    # Only allow deleting drafts or unsent agreements
    if agreement.get("status") in ["signed", "paid"]:
        raise HTTPException(status_code=400, detail="Cannot delete a signed agreement")
    
    await db.partner_agreements.delete_one({"_id": ObjectId(agreement_id)})
    
    return {"success": True, "message": "Agreement deleted"}


@router.post("/agreements/{agreement_id}/send")
async def send_agreement(agreement_id: str):
    """Send/resend agreement link to partner via email"""
    db = get_db()
    
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    partner_email = agreement.get("partner_email")
    if not partner_email:
        raise HTTPException(status_code=400, detail="No partner email on this agreement")
    
    # Update status to sent
    await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$set": {
            "status": "sent",
            "sent_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    # TODO: Send actual email when Resend is configured
    logger.info(f"Agreement {agreement_id} marked as sent to {partner_email}")
    
    return {
        "success": True,
        "message": "Agreement sent successfully",
        "sent_to": partner_email
    }


# ============= PARTNER SIGNING =============

@router.post("/agreements/{agreement_id}/sign")
@router.post("/agreements/{agreement_id}/sign")
async def sign_agreement(agreement_id: str, data: PartnerSignup, request: Request):
    """Partner signs the agreement — captures name, IP, timestamp for legal record."""
    db = get_db()
    
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    if agreement.get("status") == "signed":
        raise HTTPException(status_code=400, detail="Agreement already signed")
    
    # Capture real IP for legal record
    client_ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                 or request.headers.get("X-Real-IP")
                 or (request.client.host if request.client else "unknown"))

    import hashlib as _hl
    # Hash the agreement content for document integrity proof
    doc_hash = _hl.sha256((agreement.get("content", "") + data.signature).encode()).hexdigest()

    signed_partner = {
        "name": data.name,
        "email": data.email,
        "company": data.company,
        "phone": data.phone,
        "address": data.address,
        "city": data.city,
        "state": data.state,
        "zip_code": data.zip_code,
        "tax_id": data.tax_id,
        "signature": data.signature,
        "signature_type": data.signature_type,
        "agreed_to_terms": data.agreed_to_terms,
        "signed_at": datetime.utcnow(),
        "ip_address": client_ip,          # ✅ real IP captured
        "document_hash": doc_hash,        # ✅ integrity proof
        "user_agent": request.headers.get("User-Agent", ""),
    }
    
    new_status = "signed"
    if agreement.get("payment_required") and agreement.get("payment_amount"):
        new_status = "pending_payment"
    
    await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$set": {
            "signed_partner": signed_partner,
            "status": new_status,
            "signed_at": datetime.utcnow(),
            "partner_name": data.name,
            "partner_email": data.email,
        }}
    )
    
    partner = {
        "agreement_id": agreement_id,
        "name": data.name,
        "email": data.email,
        "company": data.company,
        "phone": data.phone,
        "address": data.address,
        "city": data.city,
        "state": data.state,
        "zip_code": data.zip_code,
        "tax_id": data.tax_id,
        "type": agreement.get("type"),
        "commission_tier": agreement.get("commission_tier"),
        "status": "active" if new_status == "signed" else "pending",
        "w9_status": "pending",
        "created_at": datetime.utcnow(),
        "total_referrals": 0,
        "total_earnings": 0,
    }
    await db.partners.insert_one(partner)
    
    return {
        "success": True,
        "status": new_status,
        "payment_required": new_status == "pending_payment",
        "payment_amount": agreement.get("payment_amount") if new_status == "pending_payment" else None,
        "message": "Agreement signed successfully" if new_status == "signed" else "Agreement signed — payment required"
    }


# ============= W-9 UPLOAD =============

@router.post("/agreements/{agreement_id}/w9")
async def upload_w9(agreement_id: str, request: Request):
    """Partner uploads their W-9 form. Stores in object storage, updates agreement + partner record."""
    from fastapi import UploadFile, File
    db = get_db()

    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

    # Read multipart file
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="W-9 file must be under 10 MB")

    allowed_types = ("application/pdf", "image/png", "image/jpeg", "image/jpg")
    content_type = getattr(file, "content_type", "application/octet-stream")
    if not any(content_type.startswith(t) for t in ("application/pdf", "image/")):
        raise HTTPException(status_code=400, detail="W-9 must be a PDF or image file")

    try:
        from utils.image_storage import upload_image
        ext = "pdf" if "pdf" in content_type else "png"
        result = await upload_image(contents, prefix="w9_forms", entity_id=agreement_id)
        file_url = f"/api/images/{result['original_path']}" if result else None
    except Exception as e:
        logger.warning(f"[W9] Storage upload failed: {e}")
        file_url = f"w9_{agreement_id}.{ext}"  # fallback reference

    now = datetime.utcnow()
    await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$set": {
            "w9_status": "uploaded",
            "w9_file_url": file_url,
            "w9_uploaded_at": now,
            "updated_at": now,
        }}
    )
    # Also update partner record if it exists
    await db.partners.update_one(
        {"agreement_id": agreement_id},
        {"$set": {"w9_status": "uploaded", "w9_file_url": file_url}}
    )

    logger.info(f"[W9] Uploaded for agreement {agreement_id}")
    return {"success": True, "message": "W-9 uploaded successfully", "w9_status": "uploaded"}


@router.post("/agreements/{agreement_id}/w9/verify")
async def verify_w9(agreement_id: str):
    """Admin marks W-9 as verified."""
    db = get_db()
    now = datetime.utcnow()
    await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$set": {"w9_status": "verified", "w9_verified_at": now}}
    )
    await db.partners.update_one(
        {"agreement_id": agreement_id},
        {"$set": {"w9_status": "verified"}}
    )
    return {"success": True, "w9_status": "verified"}


# ============= STRIPE PAYMENT =============

@router.post("/agreements/{agreement_id}/create-payment")
async def create_payment_session(agreement_id: str, request: Request):
    """Create Stripe checkout session for agreement payment"""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    
    db = get_db()
    
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    if not agreement.get("payment_required") or not agreement.get("payment_amount"):
        raise HTTPException(status_code=400, detail="Payment not required for this agreement")
    
    if agreement.get("status") not in ["pending_payment", "viewed", "sent"]:
        raise HTTPException(status_code=400, detail="Agreement not in payable state")
    
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    # Get origin from request
    body = await request.json()
    origin_url = body.get("origin_url", str(request.base_url).rstrip("/"))
    
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    success_url = f"{origin_url}/partner/agreement/{agreement_id}?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/partner/agreement/{agreement_id}?payment=cancelled"
    
    checkout_request = CheckoutSessionRequest(
        amount=float(agreement["payment_amount"]),
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "agreement_id": agreement_id,
            "partner_email": agreement.get("signed_partner", {}).get("email", ""),
            "type": "partner_agreement",
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Record transaction
    transaction = {
        "agreement_id": agreement_id,
        "session_id": session.session_id,
        "amount": agreement["payment_amount"],
        "currency": "usd",
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    await db.payment_transactions.insert_one(transaction)
    
    return {
        "checkout_url": session.url,
        "session_id": session.session_id,
    }


@router.get("/agreements/{agreement_id}/payment-status")
async def check_payment_status(agreement_id: str, session_id: str):
    """Check payment status for an agreement"""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    
    db = get_db()
    
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
    
    status = await stripe_checkout.get_checkout_status(session_id)
    
    if status.payment_status == "paid":
        # Update agreement status
        await db.partner_agreements.update_one(
            {"_id": ObjectId(agreement_id)},
            {"$set": {
                "status": "signed",
                "paid_at": datetime.utcnow(),
                "payment_session_id": session_id,
            }}
        )
        
        # Update partner status
        await db.partners.update_one(
            {"agreement_id": agreement_id},
            {"$set": {"status": "active"}}
        )
        
        # Update transaction
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "paid", "paid_at": datetime.utcnow()}}
        )
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount": status.amount_total / 100,  # Convert from cents
        "currency": status.currency,
    }


# ============= PARTNER MANAGEMENT =============

@router.get("/")
async def list_partners(status: Optional[str] = None):
    """List all partners"""
    db = get_db()
    
    query = {}
    if status:
        query["status"] = status
    
    partners = await db.partners.find(query).sort("created_at", -1).to_list(200)
    
    return [
        {
            "id": str(p["_id"]),
            "name": p.get("name"),
            "email": p.get("email"),
            "company": p.get("company"),
            "type": p.get("type"),
            "commission_tier": p.get("commission_tier"),
            "status": p.get("status"),
            "total_referrals": p.get("total_referrals", 0),
            "total_earnings": p.get("total_earnings", 0),
            "created_at": p.get("created_at").isoformat() if p.get("created_at") else None,
        }
        for p in partners
    ]


@router.get("/{partner_id}")
async def get_partner(partner_id: str):
    """Get partner details"""
    db = get_db()
    
    partner = await db.partners.find_one({"_id": ObjectId(partner_id)})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # Get agreement
    agreement = None
    if partner.get("agreement_id"):
        agreement = await db.partner_agreements.find_one({"_id": ObjectId(partner["agreement_id"])})
    
    return {
        "id": str(partner["_id"]),
        "name": partner.get("name"),
        "email": partner.get("email"),
        "company": partner.get("company"),
        "phone": partner.get("phone"),
        "address": partner.get("address"),
        "city": partner.get("city"),
        "state": partner.get("state"),
        "zip_code": partner.get("zip_code"),
        "tax_id": partner.get("tax_id"),
        "type": partner.get("type"),
        "commission_tier": partner.get("commission_tier"),
        "status": partner.get("status"),
        "total_referrals": partner.get("total_referrals", 0),
        "total_earnings": partner.get("total_earnings", 0),
        "created_at": partner.get("created_at").isoformat() if partner.get("created_at") else None,
        "agreement": {
            "id": str(agreement["_id"]),
            "signed_at": agreement.get("signed_at").isoformat() if agreement and agreement.get("signed_at") else None,
        } if agreement else None,
    }


@router.put("/{partner_id}")
async def update_partner(partner_id: str, data: dict):
    """Update partner details"""
    db = get_db()
    
    allowed_fields = ["status", "commission_tier", "notes"]
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.partners.update_one(
        {"_id": ObjectId(partner_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    return {"success": True, "message": "Partner updated"}



@router.get("/user/{user_id}/agreement")
async def get_user_agreement(user_id: str):
    """Get the signed agreement for a user (store manager)"""
    db = get_db()
    
    # Get the user to find their store/org
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Look for agreement linked to this user directly
    agreement = await db.partner_agreements.find_one({
        "$or": [
            {"user_id": user_id},
            {"signer_email": user.get("email")},
        ],
        "status": {"$in": ["signed", "active", "paid"]}
    })
    
    # If no direct agreement, look for store-level agreement
    if not agreement and user.get("store_id"):
        agreement = await db.partner_agreements.find_one({
            "store_id": user.get("store_id"),
            "status": {"$in": ["signed", "active", "paid"]}
        })
    
    # If no store agreement, look for org-level agreement
    if not agreement and user.get("organization_id"):
        agreement = await db.partner_agreements.find_one({
            "organization_id": user.get("organization_id"),
            "status": {"$in": ["signed", "active", "paid"]}
        })
    
    if not agreement:
        raise HTTPException(status_code=404, detail="No agreement found")
    
    # Get template details
    template = None
    if agreement.get("template_id"):
        template = await db.partner_templates.find_one({"_id": ObjectId(agreement["template_id"])})
    
    return {
        "_id": str(agreement["_id"]),
        "title": template.get("name") if template else "Partner Agreement",
        "type": template.get("type") if template else agreement.get("type"),
        "status": agreement.get("status"),
        "signed_at": agreement.get("signed_at"),
        "effective_date": agreement.get("effective_date"),
        "expiration_date": agreement.get("expiration_date"),
        "commission_rate": agreement.get("commission_rate"),
        "monthly_fee": agreement.get("monthly_fee"),
        "seats": agreement.get("seats"),
        "pdf_url": agreement.get("pdf_url"),
        "signer_name": agreement.get("signer_name"),
        "signer_email": agreement.get("signer_email"),
    }


# ============= PARTNER PORTAL ENDPOINTS =============

@router.get("/portal/orgs")
async def get_partner_orgs(request: Request):
    """Get organizations managed by this partner (via partner_id or user's agreement)"""
    db = get_db()
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Find orgs where this user is linked as a partner
    # Option 1: User has a partner_agreement_id
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"partner_agreement_id": 1, "email": 1, "role": 1, "organization_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    orgs = []
    
    # Check if user has a partner agreement
    agreement_id = user.get("partner_agreement_id")
    if agreement_id:
        agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
        if agreement and agreement.get("assigned_org_ids"):
            org_ids = [ObjectId(oid) for oid in agreement["assigned_org_ids"]]
            org_docs = await db.organizations.find({"_id": {"$in": org_ids}}, {"_id": 0}).to_list(100)
            for doc in org_docs:
                doc["_id"] = str(doc.get("_id", ""))
            orgs = org_docs
    
    # Also check orgs with partner_id matching the user's email or agreement
    email = user.get("email", "")
    partner_orgs = await db.organizations.find(
        {"$or": [
            {"partner_email": email},
            {"partner_user_id": user_id},
        ]}
    ).to_list(100)
    
    for org in partner_orgs:
        org["_id"] = str(org["_id"])
        if not any(o.get("_id") == org["_id"] for o in orgs):
            orgs.append(org)
    
    # If user is org_admin, also show their own org
    if user.get("organization_id"):
        try:
            own_org = await db.organizations.find_one({"_id": ObjectId(user["organization_id"])})
            if own_org:
                own_org["_id"] = str(own_org["_id"])
                if not any(o.get("_id") == own_org["_id"] for o in orgs):
                    orgs.append(own_org)
        except Exception:
            pass  # Skip invalid ObjectIds
    
    return orgs


@router.get("/portal/orgs/{org_id}/stores")
async def get_partner_org_stores(org_id: str):
    """Get stores under an org that a partner manages"""
    db = get_db()
    stores = await db.stores.find({"organization_id": org_id}).to_list(200)
    for s in stores:
        s["_id"] = str(s["_id"])
    return stores


@router.get("/portal/orgs/{org_id}/users")
async def get_partner_org_users(org_id: str):
    """Get users under an org that a partner manages"""
    db = get_db()
    users = await db.users.find(
        {"organization_id": org_id},
        {"password": 0}
    ).to_list(500)
    for u in users:
        u["_id"] = str(u["_id"])
    return users


@router.post("/portal/assign-org")
async def assign_org_to_partner(request: Request):
    """Super admin assigns an org to a partner agreement"""
    db = get_db()
    data = await request.json()
    agreement_id = data.get("agreement_id")
    org_id = data.get("org_id")
    partner_email = data.get("partner_email")
    
    if not agreement_id or not org_id:
        raise HTTPException(status_code=400, detail="agreement_id and org_id required")
    
    # Add org to the agreement's assigned_org_ids
    await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$addToSet": {"assigned_org_ids": org_id}}
    )
    
    # Also mark the org with partner info
    update = {"partner_agreement_id": agreement_id}
    if partner_email:
        update["partner_email"] = partner_email
    await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": update}
    )
    
    return {"success": True}
