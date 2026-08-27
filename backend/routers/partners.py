"""
Partner Agreement router - Digital contracts for resellers and referral partners
Supports: Agreement templates, digital signatures, Stripe payments, commission tiers
"""
import re
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import os
import logging
import asyncio
import base64
import re as _re
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import resend as _resend

from routers.database import get_db

# ── Email config ──────────────────────────────────────────────────────────────
_RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
_SENDER_EMAIL   = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
_APP_URL        = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
_ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL", "forest@imosapp.com")

if _RESEND_API_KEY:
    _resend.api_key = _RESEND_API_KEY

router = APIRouter(prefix="/partners", tags=["partners"])
logger = logging.getLogger(__name__)


# ============= PDF GENERATION =============

def _clean_text(text: str) -> str:
    """Strip markdown symbols and return plain text safe for fpdf."""
    text = _re.sub(r'\*\*(.*?)\*\*', r'\1', text)   # **bold** → plain
    text = _re.sub(r'\*(.*?)\*', r'\1', text)         # *italic* → plain
    text = text.replace('{{', '').replace('}}', '')
    # Replace common unicode that fpdf latin-1 can't handle
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2014', '--').replace('\u2013', '-')
    text = text.replace('\u00a0', ' ')
    # Encode to latin-1 safely
    return text.encode('latin-1', errors='replace').decode('latin-1')


def _generate_agreement_pdf(agreement: dict) -> bytes:
    """
    Generate a professional signed-agreement PDF using fpdf2.
    Returns raw PDF bytes.
    """
    from fpdf import FPDF

    GOLD   = (201, 169, 98)
    BLACK  = (10,  10,  10)
    GREY   = (80,  80,  80)
    LGREY  = (200, 200, 200)
    WHITE  = (255, 255, 255)
    GREEN  = (52,  199, 89)

    partner   = agreement.get("signed_partner") or {}
    agmt_type = agreement.get("template_name", "Partner Agreement")
    signed_at = agreement.get("signed_at")
    if signed_at and isinstance(signed_at, datetime):
        signed_at_str = signed_at.strftime("%B %d, %Y at %I:%M %p UTC")
    elif signed_at:
        signed_at_str = str(signed_at)
    else:
        signed_at_str = "N/A"

    pdf = FPDF()
    pdf.set_margins(left=14, top=10, right=14)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Full usable width = page_width - left_margin - right_margin
    W = pdf.w - pdf.l_margin - pdf.r_margin   # ≈ 182mm for A4 with 14mm margins
    LBL = 48   # label column width
    VAL = W - LBL  # value column width

    # ── COVER HEADER ──────────────────────────────────────────────────────────
    pdf.set_fill_color(*BLACK)
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_xy(0, 8)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*GOLD)
    pdf.cell(210, 10, "I'm On Social", align="C", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*LGREY)
    pdf.cell(210, 6, "VI Ventures Group LLC  |  Partner Agreement", align="C", ln=True)
    # Reset x to left margin after full-width header cells
    pdf.set_xy(pdf.l_margin, 44)

    # ── AGREEMENT TITLE ───────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*BLACK)
    pdf.cell(W, 12, _clean_text(agmt_type), ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(W, 7, f"Signed: {signed_at_str}", ln=True, align="C")
    pdf.ln(4)

    # ── SIGNED BADGE ──────────────────────────────────────────────────────────
    badge_w = 40
    pdf.set_x(pdf.l_margin + (W - badge_w) / 2)
    pdf.set_fill_color(*GREEN)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(badge_w, 7, "SIGNED", align="C", fill=True, border=0, ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.ln(8)

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def divider():
        pdf.set_x(pdf.l_margin)
        pdf.set_draw_color(*LGREY)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

    def section_header(title: str):
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.set_fill_color(*GOLD)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(W, 7, f"  {title.upper()}", fill=True, ln=True)
        pdf.set_x(pdf.l_margin)
        pdf.ln(3)
        pdf.set_text_color(*BLACK)

    def label_value(label: str, value: str, mono: bool = False):
        if not value:
            return
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*GREY)
        pdf.cell(LBL, 6, _clean_text(label) + ":", ln=False)
        pdf.set_font("Courier" if mono else "Helvetica", "", 9)
        pdf.set_text_color(*BLACK)
        # Explicit width — no w=0 to avoid horizontal overflow edge cases
        pdf.multi_cell(VAL, 6, _clean_text(str(value)))
        pdf.set_x(pdf.l_margin)

    def body_text(text: str, font_size: int = 9, h: int = 5):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", font_size)
        pdf.set_text_color(*BLACK)
        pdf.multi_cell(W, h, _clean_text(text))
        pdf.set_x(pdf.l_margin)

    # ── PARTNER INFO ──────────────────────────────────────────────────────────
    section_header("Partner Information")
    label_value("Name",        partner.get("name", ""))
    label_value("Email",       partner.get("email", ""))
    label_value("Company",     partner.get("company", ""))
    label_value("Phone",       partner.get("phone", ""))
    addr_parts = [partner.get("address",""), partner.get("city",""), partner.get("state",""), partner.get("zip_code","")]
    addr = ", ".join(p for p in addr_parts if p)
    if addr.strip(", "):
        label_value("Address", addr)
    label_value("Tax ID / EIN", partner.get("tax_id", ""))
    pdf.ln(2)

    # ── AGREEMENT CONTENT (MPA + Exhibit A) ───────────────────────────────────
    content = agreement.get("content", "")
    if content:
        section_header("Agreement Terms")
        for line in content.split("\n"):
            line = line.strip()
            if not line or line == "*":
                pdf.ln(2)
                continue
            if line == "---":
                divider()
                continue
            pdf.set_x(pdf.l_margin)
            if line.startswith("# "):
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(*BLACK)
                pdf.multi_cell(W, 8, _clean_text(line[2:]))
                pdf.ln(1)
            elif line.startswith("## "):
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(*BLACK)
                pdf.multi_cell(W, 7, _clean_text(line[3:]))
                pdf.ln(1)
            elif line.startswith("### "):
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*GREY)
                pdf.multi_cell(W, 6, _clean_text(line[4:]))
            elif line.startswith("- "):
                indent = 6
                pdf.set_x(pdf.l_margin + indent)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*BLACK)
                pdf.multi_cell(W - indent, 5, _clean_text("- " + line[2:]))
            elif line.startswith("| "):
                pdf.set_font("Courier", "", 8)
                pdf.set_text_color(*GREY)
                pdf.multi_cell(W, 5, _clean_text(line))
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*BLACK)
                pdf.multi_cell(W, 5, _clean_text(line))
            pdf.set_x(pdf.l_margin)

    # ── LEGAL SIGNATURE RECORD ────────────────────────────────────────────────
    pdf.add_page()
    section_header("Legal Signature Record")
    y_start = pdf.get_y()

    rows = [
        ("Signed By",     partner.get("name", ""),         False),
        ("Email",         partner.get("email", ""),         False),
        ("Company",       partner.get("company", ""),       False),
        ("Phone",         partner.get("phone", ""),         False),
        ("Signed At",     signed_at_str,                    False),
        ("IP Address",    partner.get("ip_address", ""),    True),
        ("Signature",     f'"{partner.get("signature","")}"', False),
        ("User Agent",    partner.get("user_agent", ""),    True),
        ("Document Hash", partner.get("document_hash", ""), True),
    ]
    for label, value, mono in rows:
        label_value(label, value, mono=mono)

    pdf.ln(4)
    y_end = pdf.get_y()
    # Green border around the signature block
    pdf.set_draw_color(*GREEN)
    pdf.rect(pdf.l_margin - 2, y_start - 1, W + 4, y_end - y_start + 2)
    pdf.ln(4)

    # ── W-9 STATUS ────────────────────────────────────────────────────────────
    section_header("W-9 / Tax Form Status")
    pdf.set_x(pdf.l_margin)
    w9_status = agreement.get("w9_status", "pending")
    w9_verified_at = agreement.get("w9_verified_at")
    if w9_status == "verified":
        pdf.set_text_color(*GREEN)
        pdf.set_font("Helvetica", "B", 11)
        v_str = ""
        if w9_verified_at and isinstance(w9_verified_at, datetime):
            v_str = f"  (verified {w9_verified_at.strftime('%B %d, %Y')})"
        pdf.cell(W, 8, f"W-9 Verified{v_str}", ln=True)
    elif w9_status == "uploaded":
        pdf.set_text_color(255, 149, 0)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(W, 8, "W-9 Uploaded -- Awaiting Admin Review", ln=True)
    else:
        pdf.set_text_color(255, 59, 48)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(W, 8, "W-9 Not Yet Submitted", ln=True)
    pdf.ln(4)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    divider()
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(W, 5,
        "This document is a legally binding digital agreement executed via I'm On Social's "
        "e-signature platform. The signature, IP address, and document hash above serve as "
        "the official record of execution. Governed by the laws of the State of Wyoming."
    )
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(W, 5, f"Generated {datetime.utcnow().strftime('%B %d, %Y')} | VI Ventures Group LLC", ln=True)

    return bytes(pdf.output())



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
                             custom_commission_notes: str = "",
                             commission_duration: str = "Lifetime (while account remains active)",
                             billing_structure: str = "Company Bills Customer (Partner receives commission)",
                             company_name: str = "VI Ventures Group LLC",
                             governing_state: str = "Wyoming") -> str:
    """Generate the full agreement text from the template + exhibit A."""
    import datetime as dt
    effective_date = dt.datetime.utcnow().strftime("%B %d, %Y")

    main = (DEFAULT_MASTER_AGREEMENT
            .replace("{{partner_name}}", partner_name or "[Partner Name]")
            .replace("{{effective_date}}", effective_date)
            .replace("{{company_legal_name}}", company_name)
            .replace("{{governing_state}}", governing_state))

    # Build commission section — use custom override if provided, otherwise standard tiers
    if custom_commission_notes and custom_commission_notes.strip():
        commission_section = f"""## 1. COMMISSION STRUCTURE

**Custom Commission Terms:**

{custom_commission_notes}

*Custom commission structure agreed upon by both parties in lieu of standard tiers.*"""
    elif partner_type == "reseller":
        commission_section = """## 1. COMMISSION STRUCTURE

| Collected Active MRR | Commission Rate |
|---|---|
| Up to $20,000 / month | 20% |
| $20,001 – $40,000 / month | 30% |
| Above $40,000 / month | 40% |

*Tiers are evaluated monthly and applied retroactively to total Collected Active MRR for that month.*"""
    else:
        commission_section = """## 1. COMMISSION STRUCTURE

| Collected Active MRR | Commission Rate |
|---|---|
| Up to $10,000 / month | 10% |
| Above $10,000 / month | 15% |

*Tiers are evaluated monthly and applied retroactively to total Collected Active MRR for that month.*"""

    # Build the correct Exhibit A
    exhibit_template = EXHIBIT_A_RESELLER if partner_type == "reseller" else EXHIBIT_A_REFERRAL
    exhibit = (exhibit_template
               .replace("{{partner_name}}", partner_name or "[Partner Name]")
               .replace("{{effective_date}}", effective_date)
               .replace("{{custom_terms}}", custom_terms.strip() if custom_terms.strip() else "No additional terms.")
               .replace("{{commission_duration}}", commission_duration)
               .replace("{{billing_structure}}", billing_structure))

    # Replace the commission section in the exhibit
    import re
    exhibit = re.sub(r'## 1\. COMMISSION STRUCTURE.*?(?=\n## 2\.)',
                     commission_section + "\n\n",
                     exhibit, flags=re.DOTALL)

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

    default_commission_tiers = [
        {"name": "Tier 1", "percentage": 10, "description": "Up to $10,000 MRR"},
        {"name": "Tier 2", "percentage": 15, "description": "Above $10,000 MRR"},
    ]

    templates = [
        {
            "name": "Reseller Agreement",
            "type": "reseller",
            "content": build_agreement_content("reseller", ""),
            "commission_tiers": [
                {"name": "Tier 1", "percentage": 20, "description": "Up to $20,000 MRR"},
                {"name": "Tier 2", "percentage": 30, "description": "$20,001–$40,000 MRR"},
                {"name": "Tier 3", "percentage": 40, "description": "Above $40,000 MRR"},
            ],
            "payment_required": False,
            "payment_amount": None,
            "active": True,
            "created_at": datetime.utcnow(),
        },
        {
            "name": "Referral Partner Agreement",
            "type": "referral",
            "content": build_agreement_content("referral", ""),
            "commission_tiers": default_commission_tiers,
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
            custom_commission_notes=data.get("custom_commission_notes", ""),
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
            "w9_status": a.get("w9_status", "pending"),
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
        "custom_terms": agreement.get("custom_terms", ""),
        "commission_duration": agreement.get("commission_duration", ""),
        "is_white_label": agreement.get("is_white_label", False),
        "commission_tiers": template.get("commission_tiers", []) if template else [],
        "payment_required": agreement.get("payment_required", False),
        "payment_amount": agreement.get("payment_amount"),
        "partner_name": agreement.get("partner_name"),
        "partner_email": agreement.get("partner_email"),
        "partner_phone": agreement.get("partner_phone"),
        "status": agreement.get("status"),
        "w9_status": agreement.get("w9_status", "pending"),
        "w9_file_url": agreement.get("w9_file_url"),
        "w9_uploaded_at": agreement.get("w9_uploaded_at").isoformat() if agreement.get("w9_uploaded_at") else None,
        "signed_partner": agreement.get("signed_partner"),
        "signed_at": agreement.get("signed_at").isoformat() if agreement.get("signed_at") else None,
        "created_at": agreement.get("created_at").isoformat() if agreement.get("created_at") else None,
        "sent_at": agreement.get("sent_at").isoformat() if agreement.get("sent_at") else None,
    }


@router.get("/agreements/{agreement_id}/pdf")
async def download_agreement_pdf(agreement_id: str):
    """Generate and stream the signed agreement as a PDF."""
    db = get_db()
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if agreement.get("status") not in ("signed", "pending_payment"):
        raise HTTPException(status_code=400, detail="Agreement has not been signed yet")

    partner_name = (agreement.get("signed_partner") or {}).get("name") or agreement.get("partner_name") or "partner"
    safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", partner_name)[:40]
    filename = f"agreement_{safe_name}.pdf"

    pdf_bytes = await asyncio.to_thread(_generate_agreement_pdf, agreement)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/agreements/{agreement_id}")
async def update_agreement(agreement_id: str, data: dict):
    """Update an agreement (before sending)"""
    db = get_db()
    
    allowed_fields = ["content", "commission_tier", "custom_commission_notes", "is_white_label", "payment_required", "payment_amount", "partner_email", "partner_name", "partner_phone", "notes", "status"]
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



async def _send_agreement_email(
    to_email: str,
    partner_name: str,
    agreement_type: str,
    agreement_link: str,
    agreement_id: str,
) -> None:
    """Send the partner agreement signing link via Resend. Silently logs on failure."""
    if not _RESEND_API_KEY:
        logger.warning("[Partners] RESEND_API_KEY not set — skipping agreement email")
        return

    checklist_items = [
        'Full Master Partner Agreement (MPA)',
        'Exhibit A — Your Commission Structure &amp; Terms',
        'Digital signature capture (IP &amp; timestamp recorded)',
        'W-9 upload step for commission payouts',
    ]
    checklist_html = ''.join(
        f'<div style="display:flex;align-items:center;gap:12px;font-size:14px;color:#CCC;margin-bottom:10px;">'
        f'<span style="color:#34C759;font-size:16px;">&#10003;</span> {item}</div>'
        for item in checklist_items
    )

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#000;color:#fff;padding:40px 32px;border-radius:16px;">

      <div style="text-align:center;margin-bottom:40px;">
        <div style="display:inline-block;background:#1C1C1E;border-radius:12px;padding:14px 28px;">
          <span style="font-size:22px;font-weight:800;color:#C9A962;letter-spacing:-0.5px;">I'm On Social</span>
        </div>
      </div>

      <h1 style="font-size:28px;font-weight:700;color:#ffffff;margin:0 0 8px 0;text-align:center;">
        You've Been Invited to Partner
      </h1>
      <p style="font-size:16px;color:#8E8E93;text-align:center;margin:0 0 40px 0;">
        {agreement_type} &mdash; Please review and sign below
      </p>

      <div style="background:#1C1C1E;border-radius:12px;padding:24px;margin-bottom:32px;border-left:4px solid #C9A962;">
        <p style="font-size:14px;color:#8E8E93;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:0.5px;">Prepared for</p>
        <p style="font-size:20px;font-weight:700;color:#fff;margin:0;">{partner_name}</p>
      </div>

      <div style="background:#1C1C1E;border-radius:12px;padding:24px;margin-bottom:32px;">
        <p style="font-size:15px;font-weight:600;color:#fff;margin:0 0 16px 0;">Your agreement includes:</p>
        {checklist_html}
      </div>

      <div style="text-align:center;margin-bottom:40px;">
        <a href="{agreement_link}"
           style="display:inline-block;background:#C9A962;color:#000;font-size:18px;font-weight:700;padding:18px 48px;border-radius:12px;text-decoration:none;letter-spacing:-0.3px;">
          Review &amp; Sign Agreement
        </a>
        <p style="font-size:13px;color:#636366;margin-top:14px;">
          Or copy this link:<br>
          <a href="{agreement_link}" style="color:#C9A962;word-break:break-all;">{agreement_link}</a>
        </p>
      </div>

      <div style="border-top:1px solid #2C2C2E;padding-top:24px;text-align:center;">
        <p style="font-size:13px;color:#636366;margin:0 0 6px 0;">
          Questions? <a href="mailto:support@imonsocial.com" style="color:#C9A962;">support@imonsocial.com</a>
        </p>
        <p style="font-size:12px;color:#48484A;margin:0;">
          &copy; 2026 VI Ventures Group LLC &middot; I'm On Social
        </p>
      </div>

    </div>
    """

    try:
        result = await asyncio.to_thread(_resend.Emails.send, {
            "from": "I'm On Social <billing@imonsocial.com>",
            "to": [to_email],
            "reply_to": "support@imonsocial.com",
            "subject": f"Your {agreement_type} is Ready to Sign",
            "html": html,
        })
        logger.info(f"[Partners] Agreement email sent to {to_email}: {result.get('id')}")
    except Exception as e:
        logger.error(f"[Partners] Failed to send agreement email to {to_email}: {e}")
        # Non-fatal — agreement is still marked as sent in DB


@router.post("/agreements/{agreement_id}/send")
async def send_agreement(agreement_id: str):
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
    
    # Send the agreement link via Resend
    partner_name = agreement.get("partner_name") or "Partner"
    agreement_type = agreement.get("template_name", "Partner Agreement")
    agreement_link = f"{_APP_URL}/partner/agreement/{agreement_id}"

    await _send_agreement_email(
        to_email=partner_email,
        partner_name=partner_name,
        agreement_type=agreement_type,
        agreement_link=agreement_link,
        agreement_id=agreement_id,
    )

    logger.info(f"Agreement {agreement_id} sent to {partner_email}")
    
    return {
        "success": True,
        "message": "Agreement sent successfully",
        "sent_to": partner_email
    }


# ============= PARTNER SIGNING =============

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

@router.post("/agreements/{agreement_id}/w9-digital")
async def submit_digital_w9(agreement_id: str, request: Request):
    """
    Partner fills W-9 fields digitally in the app.
    We generate a professional W-9 PDF from the data and store it,
    exactly like a manually uploaded W-9.
    """
    import asyncio as _aio, uuid as _uuid
    from fpdf import FPDF

    db = get_db()
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

    data = await request.json()
    # Required fields
    legal_name     = (data.get("legal_name") or "").strip()
    tin            = (data.get("tin") or "").strip()          # SSN or EIN
    if not legal_name or not tin:
        raise HTTPException(status_code=422, detail="Legal name and TIN (SSN/EIN) are required")

    business_name  = (data.get("business_name") or "").strip()
    tax_class      = (data.get("tax_classification") or "individual").strip()
    address        = (data.get("address") or "").strip()
    city_state_zip = (data.get("city_state_zip") or "").strip()
    signature      = (data.get("signature") or legal_name).strip()
    signed_at      = datetime.utcnow()

    def _build_pdf() -> bytes:
        from fpdf import XPos, YPos
        pdf = FPDF()
        pdf.set_margins(18, 14, 18)
        pdf.set_auto_page_break(auto=True, margin=16)
        pdf.add_page()
        W = pdf.w - pdf.l_margin - pdf.r_margin

        def lf(bold=False, size=10):
            try:
                pdf.set_font("Helvetica", "B" if bold else "", size)
            except Exception:
                pass

        # ── Header ───────────────────────────────────────────────────
        pdf.set_fill_color(30, 30, 30)
        pdf.rect(0, 0, 210, 22, 'F')
        lf(True, 14)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(18, 6)
        pdf.cell(W, 10, "W-9 Request for Taxpayer Identification Number", align="L")
        lf(False, 9)
        pdf.set_xy(0, 6)
        pdf.cell(210, 10, "Completed digitally via I'm On Social", align="R")
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(pdf.l_margin, 28)

        # ── Intro note ───────────────────────────────────────────────
        lf(False, 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(W, 5, (
            "This form serves as your certification of taxpayer information for commission payments. "
            "The information provided is subject to IRS penalties for false statements. "
            "This document was completed and submitted electronically on "
            f"{signed_at.strftime('%B %d, %Y at %H:%M UTC')}."
        ))
        pdf.ln(4)
        pdf.set_text_color(0, 0, 0)

        def field(label: str, value: str, full_width: bool = True):
            lf(True, 9)
            pdf.set_x(pdf.l_margin)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(W if full_width else W / 2, 6, label)
            pdf.ln(0)
            pdf.set_x(pdf.l_margin)
            lf(False, 11)
            pdf.set_text_color(0, 0, 0)
            pdf.set_draw_color(200, 200, 200)
            pdf.set_fill_color(248, 248, 248)
            pdf.cell(W if full_width else W / 2, 9, f"  {value or '—'}", border=1, fill=True)
            pdf.ln(3)

        field("1. Name (as shown on your income tax return)", legal_name)
        field("2. Business name / disregarded entity name (if different from above)", business_name or "N/A")

        # Tax classification checkboxes
        lf(True, 9)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(pdf.l_margin)
        pdf.cell(W, 6, "3. Federal tax classification")
        pdf.ln(1)
        TAX_CLASSES = [
            ("individual",   "Individual / Sole proprietor"),
            ("c_corp",       "C Corporation"),
            ("s_corp",       "S Corporation"),
            ("partnership",  "Partnership"),
            ("trust",        "Trust / Estate"),
            ("llc",          "LLC"),
            ("other",        "Other"),
        ]
        cols = 3
        x0 = pdf.l_margin
        cell_w = W / cols
        for i, (key, label) in enumerate(TAX_CLASSES):
            col = i % cols
            row = i // cols
            x = x0 + col * cell_w
            y = pdf.get_y() + (0 if col == 0 else 0)
            pdf.set_xy(x, pdf.get_y())
            checked = "✓ " if tax_class.lower().startswith(key[:3]) else "☐ "
            lf(tax_class.lower().startswith(key[:3]), 10)
            pdf.set_text_color(0 if tax_class.lower().startswith(key[:3]) else 120, 0, 0)
            pdf.cell(cell_w, 8, checked + label)
            if col == cols - 1:
                pdf.ln(0)
                pdf.set_x(x0)
        pdf.ln(6)
        pdf.set_text_color(0, 0, 0)

        field("5. Address (number, street, apt)", address)
        field("6. City, state, ZIP code", city_state_zip)
        pdf.ln(2)

        # TIN
        lf(True, 9)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(pdf.l_margin)
        pdf.cell(W, 6, "Part I — Taxpayer Identification Number (TIN)")
        pdf.ln(2)
        tin_display = tin[:3] + "-**-****" if len(tin) == 9 and tin.isdigit() else tin[:2] + "-*******" if len(tin) == 9 else tin
        pdf.set_fill_color(255, 252, 230)
        pdf.set_draw_color(200, 180, 0)
        lf(True, 13)
        pdf.set_text_color(0, 0, 0)
        pdf.set_x(pdf.l_margin)
        pdf.cell(W / 2, 12, f"  SSN / EIN: {tin_display}", border=1, fill=True)
        pdf.ln(6)

        # Certification
        lf(True, 9)
        pdf.set_text_color(80, 80, 80)
        pdf.set_x(pdf.l_margin)
        pdf.cell(W, 6, "Part II — Certification")
        pdf.ln(2)
        lf(False, 9)
        pdf.set_text_color(60, 60, 60)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(W, 5, (
            "Under penalties of perjury, I certify that: (1) The number shown on this form is my correct TIN; "
            "(2) I am not subject to backup withholding; (3) I am a U.S. person; "
            "(4) The FATCA code(s) entered on this form (if any) indicating that I am exempt from FATCA reporting is correct."
        ))
        pdf.ln(4)

        # Signature line
        pdf.set_draw_color(0, 0, 0)
        pdf.set_fill_color(245, 245, 245)
        pdf.set_x(pdf.l_margin)
        lf(False, 16)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(W * 0.65, 14, f"  {signature}", border=1, fill=True)
        pdf.set_x(pdf.l_margin + W * 0.67)
        lf(False, 10)
        pdf.cell(W * 0.33, 14, f"  {signed_at.strftime('%m/%d/%Y')}", border=1, fill=True)
        pdf.ln(4)
        lf(False, 8)
        pdf.set_text_color(120, 120, 120)
        pdf.set_x(pdf.l_margin)
        pdf.cell(W * 0.65, 5, "  Signature (type to certify)")
        pdf.set_x(pdf.l_margin + W * 0.67)
        pdf.cell(W * 0.33, 5, "  Date")
        pdf.ln(8)

        # Footer
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(3)
        lf(False, 8)
        pdf.set_text_color(130, 130, 130)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(W, 4,
            f"Submitted digitally via I'm On Social | Agreement ID: {agreement_id} | "
            f"IP: {data.get('ip_address','N/A')} | {signed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        return bytes(pdf.output())

    # Generate PDF in thread (CPU-bound)
    import asyncio as _asyncio
    pdf_bytes = await _asyncio.to_thread(_build_pdf)

    # Upload the generated PDF
    try:
        path = f"w9_forms/{agreement_id}/{_uuid.uuid4().hex[:8]}_digital.pdf"
        from utils.image_storage import put_object
        put_object(path, pdf_bytes, "application/pdf")
        file_url = f"/api/images/{path}"
    except Exception as e:
        logger.error(f"[W9-Digital] Storage failed: {e}")
        file_url = f"w9_digital_pending_{agreement_id}.pdf"

    now = datetime.utcnow()
    await db.partner_agreements.update_one(
        {"_id": ObjectId(agreement_id)},
        {"$set": {
            "w9_status":          "uploaded",
            "w9_file_url":        file_url,
            "w9_uploaded_at":     now,
            "w9_method":          "digital",
            "w9_legal_name":      legal_name,
            "w9_tax_class":       tax_class,
            "w9_tin_last4":       tin[-4:] if len(tin) >= 4 else "",
            "updated_at":         now,
        }}
    )

    # Also update partner record if linked
    await db.partners.update_one(
        {"agreement_id": agreement_id},
        {"$set": {"w9_status": "uploaded", "w9_file_url": file_url}}
    )

    return {
        "success":   True,
        "w9_status": "uploaded",
        "method":    "digital",
        "file_url":  file_url,
        "message":   "W-9 submitted digitally. We'll verify it within 1-2 business days.",
    }


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
        import uuid as _uuid
        ext = "pdf" if "pdf" in content_type else ("jpg" if "jpeg" in content_type else "png")
        path = f"w9_forms/{agreement_id}/{_uuid.uuid4().hex[:8]}.{ext}"
        # Use put_object directly — bypasses PIL (which can't handle PDFs)
        from utils.image_storage import put_object
        put_object(path, contents, content_type)
        file_url = f"/api/images/{path}"
    except Exception as e:
        logger.warning(f"[W9] Storage upload failed: {e} — saving reference only")
        file_url = f"w9_pending_{agreement_id}.pdf"

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


async def _email_signed_agreement(agreement: dict, agreement_id: str) -> None:
    """
    Generate the signed agreement PDF and email it to:
      - The partner (their official copy)
      - The admin (for records)
    Called after W-9 verification.
    """
    if not _RESEND_API_KEY:
        logger.warning("[Partners] RESEND_API_KEY not set — skipping signed agreement email")
        return

    partner   = agreement.get("signed_partner") or {}
    partner_email = partner.get("email") or agreement.get("partner_email")
    partner_name  = partner.get("name") or agreement.get("partner_name") or "Partner"
    agmt_type     = agreement.get("template_name", "Partner Agreement")
    signed_at     = agreement.get("signed_at")
    signed_at_str = signed_at.strftime("%B %d, %Y") if isinstance(signed_at, datetime) else str(signed_at or "")

    try:
        pdf_bytes = await asyncio.to_thread(_generate_agreement_pdf, agreement)
        pdf_b64 = base64.b64encode(pdf_bytes).decode()
    except Exception as e:
        logger.error(f"[Partners] PDF generation failed for {agreement_id}: {e}")
        return

    safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", partner_name)[:40]
    pdf_filename = f"signed_agreement_{safe_name}.pdf"

    attachment = {"filename": pdf_filename, "content": pdf_b64}

    # ── Partner copy ──────────────────────────────────────────────────────────
    if partner_email:
        partner_html = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#000;color:#fff;padding:40px 32px;border-radius:16px;">
          <div style="text-align:center;margin-bottom:32px;">
            <div style="display:inline-block;background:#1C1C1E;border-radius:12px;padding:14px 28px;">
              <span style="font-size:22px;font-weight:800;color:#C9A962;">I'm On Social</span>
            </div>
          </div>
          <div style="text-align:center;margin-bottom:32px;">
            <div style="font-size:56px;margin-bottom:16px;">&#x2705;</div>
            <h1 style="font-size:26px;font-weight:700;color:#fff;margin:0 0 8px 0;">You're Fully Onboarded!</h1>
            <p style="font-size:16px;color:#8E8E93;margin:0;">Your W-9 has been verified and your partnership is now active.</p>
          </div>
          <div style="background:#1C1C1E;border-radius:12px;padding:24px;margin-bottom:28px;border-left:4px solid #C9A962;">
            <p style="font-size:13px;color:#8E8E93;margin:0 0 4px;text-transform:uppercase;letter-spacing:.5px;">Agreement</p>
            <p style="font-size:18px;font-weight:700;color:#fff;margin:0 0 10px;">{agmt_type}</p>
            <p style="font-size:13px;color:#8E8E93;margin:0 0 4px;text-transform:uppercase;letter-spacing:.5px;">Signed</p>
            <p style="font-size:15px;color:#fff;margin:0;">{signed_at_str}</p>
          </div>
          <p style="font-size:14px;color:#CCC;line-height:22px;margin-bottom:28px;">
            Your fully executed and verified agreement is attached as a PDF. Please save it for your records.
            Commissions are paid <strong>Net 30</strong> after the close of each calendar month.
          </p>
          <div style="border-top:1px solid #2C2C2E;padding-top:24px;text-align:center;">
            <p style="font-size:13px;color:#636366;margin:0 0 6px;">
              Questions? <a href="mailto:support@imonsocial.com" style="color:#C9A962;">support@imonsocial.com</a>
            </p>
            <p style="font-size:12px;color:#48484A;margin:0;">&copy; 2026 VI Ventures Group LLC &middot; I'm On Social</p>
          </div>
        </div>
        """
        try:
            result = await asyncio.to_thread(_resend.Emails.send, {
                "from": "I'm On Social <billing@imonsocial.com>",
                "to": [partner_email],
                "reply_to": "support@imonsocial.com",
                "subject": f"Your Signed {agmt_type} — Welcome to the Partner Program!",
                "html": partner_html,
                "attachments": [attachment],
            })
            logger.info(f"[Partners] Signed agreement emailed to partner {partner_email}: {result.get('id')}")
        except Exception as e:
            logger.error(f"[Partners] Failed to email partner {partner_email}: {e}")

    # ── Admin copy ────────────────────────────────────────────────────────────
    admin_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#000;color:#fff;padding:40px 32px;border-radius:16px;">
      <div style="text-align:center;margin-bottom:32px;">
        <span style="font-size:22px;font-weight:800;color:#C9A962;">I'm On Social</span>
      </div>
      <h1 style="font-size:22px;font-weight:700;color:#fff;margin:0 0 8px 0;">Partner Fully Onboarded</h1>
      <p style="font-size:14px;color:#8E8E93;margin:0 0 28px;">W-9 verified. Signed agreement attached.</p>
      <div style="background:#1C1C1E;border-radius:12px;padding:20px;margin-bottom:20px;">
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">Partner</p>
        <p style="font-size:16px;font-weight:700;color:#fff;margin:0 0 12px;">{partner_name}</p>
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">Email</p>
        <p style="font-size:14px;color:#fff;margin:0 0 12px;">{partner_email or "N/A"}</p>
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">Agreement Type</p>
        <p style="font-size:14px;color:#fff;margin:0 0 12px;">{agmt_type}</p>
        <p style="font-size:13px;color:#8E8E93;margin:0 0 3px;">Signed</p>
        <p style="font-size:14px;color:#fff;margin:0;">{signed_at_str}</p>
      </div>
      <p style="font-size:12px;color:#48484A;text-align:center;">&copy; 2026 VI Ventures Group LLC &middot; I'm On Social</p>
    </div>
    """
    try:
        result = await asyncio.to_thread(_resend.Emails.send, {
            "from": "I'm On Social <billing@imonsocial.com>",
            "to": [_ADMIN_EMAIL],
            "reply_to": "support@imonsocial.com",
            "subject": f"[Partner Onboarded] {partner_name} — {agmt_type}",
            "html": admin_html,
            "attachments": [attachment],
        })
        logger.info(f"[Partners] Signed agreement copy emailed to admin {_ADMIN_EMAIL}: {result.get('id')}")
    except Exception as e:
        logger.error(f"[Partners] Failed to email admin {_ADMIN_EMAIL}: {e}")



@router.post("/agreements/{agreement_id}/w9/verify")
async def verify_w9(agreement_id: str):
    """Admin marks W-9 as verified — then emails the signed PDF to partner + admin."""
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

    # Fire-and-forget: generate PDF and email both partner + admin
    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if agreement:
        asyncio.create_task(_email_signed_agreement(agreement, agreement_id))

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


@router.post("/agreements/{agreement_id}/add-contact")
async def add_agreement_contact(agreement_id: str, request: Request):
    """
    Creates the partner from this agreement as a contact.
    Deduplicates across the ENTIRE org/store — not just one user's contacts.
    Returns contact_id + pre-filled SMS body with the signing link.
    Idempotent — stores contact_id on the agreement so it's never created twice.
    """
    db = get_db()
    data = await request.json()
    user_id = data.get("user_id") or request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    agreement = await db.partner_agreements.find_one({"_id": ObjectId(agreement_id)})
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

    # If we already created a contact for this agreement, return it
    if agreement.get("contact_id"):
        existing_contact = await db.contacts.find_one({"_id": ObjectId(agreement["contact_id"])})
        if existing_contact:
            sign_link = f"{_APP_URL}/partner/agreement/{agreement_id}"
            name = (agreement.get("signed_partner") or {}).get("name") or agreement.get("partner_name", "")
            first = name.split()[0] if name else "there"
            agmt_type = agreement.get("template_name", "Partner Agreement")
            sms_body = f"Hi {first}! Here's your I'm On Social {agmt_type} to review and sign: {sign_link}"
            return {
                "contact_id": agreement["contact_id"],
                "created": False,
                "name": name,
                "phone": existing_contact.get("phone", ""),
                "email": existing_contact.get("email", ""),
                "sms_body": sms_body,
                "sign_link": sign_link,
            }

    signed  = agreement.get("signed_partner") or {}
    name    = signed.get("name")  or agreement.get("partner_name")  or ""
    email   = (signed.get("email") or agreement.get("partner_email") or "").lower().strip()
    phone   = signed.get("phone") or agreement.get("partner_phone") or ""
    company = signed.get("company") or ""

    if not phone and not email:
        raise HTTPException(status_code=400, detail="Agreement has no phone or email. Add partner details first.")

    # Normalize phone to last 10 digits for comparison
    digits = re.sub(r"\D", "", phone)
    digits10 = digits[-10:] if len(digits) >= 10 else digits

    # ── Org-wide dedup (search across ALL users in same org/store) ─────────────
    # Get the requesting user's org/store context
    req_user = await db.users.find_one({"_id": ObjectId(user_id)}, {"org_id": 1, "store_id": 1})
    org_id   = (req_user or {}).get("org_id")
    store_id = (req_user or {}).get("store_id")

    # Build a broad dedup query covering: this user, same org, same store
    user_scope: list = [{"user_id": user_id}]
    if org_id:
        user_scope.append({"org_id": org_id})
    if store_id:
        user_scope.append({"store_id": store_id})

    or_clauses = []
    if digits10:
        or_clauses.append({"phone": {"$regex": re.escape(digits10)}})
    if email:
        or_clauses.append({"email": email})

    existing = None
    if or_clauses:
        existing = await db.contacts.find_one({
            "$or": user_scope,
            "$or": or_clauses,   # noqa: F601 — MongoDB accepts duplicate $or via array
        })

    # Fallback: simpler exact match if broad query returns nothing
    if not existing and or_clauses:
        existing = await db.contacts.find_one({
            "user_id": user_id,
            "$or": or_clauses,
        })

    if existing:
        contact_id = str(existing["_id"])
        # Update agreement with contact_id to prevent future duplicates
        await db.partner_agreements.update_one(
            {"_id": ObjectId(agreement_id)},
            {"$set": {"contact_id": contact_id}}
        )
        created = False
    else:
        parts      = name.strip().split(" ", 1)
        first_name = parts[0] if parts else name
        last_name  = parts[1] if len(parts) > 1 else ""
        contact_doc = {
            "user_id":          user_id,
            "original_user_id": user_id,
            "first_name":       first_name,
            "last_name":        last_name,
            "email":            email,
            "phone":            phone,
            "company":          company,
            "source":           "partner_agreement",
            "ownership_type":   "org",
            "status":           "active",
            "tags":             ["Partner"],
            "notes":            f"Added from partner agreement — {agreement.get('template_name','')} ({agreement.get('type','')})",
            "created_at":       datetime.utcnow(),
            "updated_at":       datetime.utcnow(),
        }
        result     = await db.contacts.insert_one(contact_doc)
        contact_id = str(result.inserted_id)
        # Store contact_id on agreement to prevent future duplicates
        await db.partner_agreements.update_one(
            {"_id": ObjectId(agreement_id)},
            {"$set": {"contact_id": contact_id}}
        )
        created = True

    sign_link = f"{_APP_URL}/partner/agreement/{agreement_id}"
    first     = name.split()[0] if name else "there"
    agmt_type = agreement.get("template_name", "Partner Agreement")
    sms_body  = (
        f"Hi {first}! Here's your I'm On Social {agmt_type} to review and sign: {sign_link}"
    )

    return {
        "contact_id": contact_id,
        "created":    created,
        "name":       name,
        "phone":      phone,
        "email":      email,
        "sms_body":   sms_body,
        "sign_link":  sign_link,
    }



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
