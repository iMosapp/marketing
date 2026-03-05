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

DEFAULT_RESELLER_TEMPLATE = """
# i'M On Social Reseller Agreement

This Reseller Agreement ("Agreement") is entered into as of the date of digital signature below.

## 1. Appointment as Reseller

i'M On Social hereby appoints the Reseller as a non-exclusive reseller of i'M On Social products and services in the territory agreed upon.

## 2. Reseller Obligations

The Reseller agrees to:
- Actively promote and market i'M On Social products
- Maintain professional standards in all customer interactions
- Provide accurate information about products and pricing
- Not make unauthorized modifications to products or services
- Comply with all applicable laws and regulations

## 3. Pricing and Payments

- Reseller receives products at the agreed wholesale discount
- Reseller sets retail pricing at or above minimum advertised price (MAP)
- Payment terms: Net 30 from invoice date
- All payments in USD

## 4. Commission Structure

Commission rates are based on the selected tier and are calculated on net revenue.

## 5. Term and Termination

This Agreement is effective from the date of signature and continues for one (1) year, automatically renewing unless terminated by either party with 30 days written notice.

## 6. Confidentiality

Reseller agrees to maintain confidentiality of all proprietary information, pricing structures, and business practices.

## 7. Limitation of Liability

i'M On Social's liability is limited to the fees paid under this Agreement in the 12 months preceding any claim.

---

By signing below, you acknowledge that you have read, understood, and agree to be bound by the terms of this Agreement.
"""

DEFAULT_REFERRAL_TEMPLATE = """
# i'M On Social Referral Partner Agreement

This Referral Partner Agreement ("Agreement") is entered into as of the date of digital signature below.

## 1. Referral Partnership

i'M On Social welcomes you as a Referral Partner. As a partner, you will earn commissions for qualified referrals that become paying customers.

## 2. How It Works

1. Share your unique referral link with potential customers
2. When they sign up and become paying customers, you earn commission
3. Commissions are paid monthly for all qualified referrals

## 3. Referral Partner Obligations

You agree to:
- Promote i'M On Social honestly and professionally
- Not engage in spam or misleading marketing
- Disclose your referral relationship when required by law
- Not bid on i'M On Social branded keywords in paid advertising

## 4. Commission Structure

Your commission rate is based on your selected tier. Commissions are calculated on the first 12 months of customer payments.

## 5. Payment Terms

- Minimum payout threshold: $100
- Payment schedule: Monthly, by the 15th
- Payment method: Direct deposit or check
- You are responsible for all applicable taxes

## 6. Term and Termination

This Agreement continues until terminated by either party with 14 days notice. Pending commissions for qualified referrals will still be paid.

## 7. No Employment Relationship

This Agreement does not create an employment, agency, or partnership relationship.

---

By signing below, you acknowledge that you have read, understood, and agree to be bound by the terms of this Agreement.
"""

DEFAULT_COMMISSION_TIERS = [
    {"name": "Bronze", "percentage": 10.0, "description": "Standard partner tier - 10% commission"},
    {"name": "Silver", "percentage": 15.0, "description": "High-volume partner - 15% commission"},
    {"name": "Gold", "percentage": 20.0, "description": "Premium partner - 20% commission"},
    {"name": "Platinum", "percentage": 25.0, "description": "Elite partner - 25% commission"},
]


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
        "content": data.get("content", template["content"]),  # Allow customization
        "commission_tier": data.get("commission_tier"),  # Selected tier
        "custom_commission_notes": data.get("custom_commission_notes"),  # Free-form commission structure
        "is_white_label": data.get("is_white_label", False),  # White label partner flag
        "payment_required": data.get("payment_required", template.get("payment_required", False)),
        "payment_amount": data.get("payment_amount", template.get("payment_amount")),
        "partner_email": data.get("partner_email"),  # Optional pre-fill
        "partner_name": data.get("partner_name"),  # Optional pre-fill
        "notes": data.get("notes"),  # Internal notes
        "status": "draft",  # draft, sent, viewed, signed, paid
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
async def sign_agreement(agreement_id: str, data: PartnerSignup):
    """Partner signs the agreement"""
    db = get_db()
    
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    if agreement.get("status") == "signed":
        raise HTTPException(status_code=400, detail="Agreement already signed")
    
    # Store partner info
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
        "ip_address": None,  # Can be added from request
    }
    
    # Determine new status
    new_status = "signed"
    if agreement.get("payment_required") and agreement.get("payment_amount"):
        new_status = "pending_payment"
    
    await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$set": {
            "signed_partner": signed_partner,
            "status": new_status,
            "signed_at": datetime.utcnow(),
        }}
    )
    
    # Create partner record
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
        "message": "Agreement signed successfully" if new_status == "signed" else "Agreement signed - payment required"
    }


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
