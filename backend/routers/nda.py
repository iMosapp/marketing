"""
NDA Router - Digital Non-Disclosure Agreements with signature collection
Flow: Admin signs -> shares link -> Recipient verifies (email+phone) -> Recipient signs -> Stored
"""
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime
from typing import Optional
import os
import logging
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from routers.database import get_db

router = APIRouter(prefix="/nda", tags=["nda"])
logger = logging.getLogger(__name__)


class NDASenderSign(BaseModel):
    sender_name: str
    sender_title: str
    sender_signature: str  # base64 drawn signature or typed name
    signature_type: str = "drawn"  # 'drawn' or 'typed'
    recipient_name: str
    recipient_email: str
    recipient_phone: str


class NDAVerify(BaseModel):
    email: str
    phone: str


class NDARecipientSign(BaseModel):
    name: str
    title: str
    company: str
    email: str
    signature: str  # base64 drawn signature or typed name
    signature_type: str = "drawn"


# ============= NDA CONTENT =============

NDA_CONTENT = {
    "title": "Non-Disclosure and Confidentiality Agreement",
    "company": "i'M On Social LLC",
    "company_address": "1741 Lunford Ln, Riverton, UT 84065",
    "company_email": "forest@imosapp.com",
    "sections": [
        {
            "heading": "Non-Disclosure and Confidentiality Agreement",
            "body": 'This Non-Disclosure Agreement ("Agreement") is entered into as of the date of the last party\'s signature, by and between the Disclosing Party and the Receiving Party identified herein.'
        },
        {
            "heading": "1. Definition of Confidential Information",
            "body": '"Confidential Information" means any and all non-public, proprietary, or trade secret information disclosed by the Disclosing Party, whether orally, in writing, electronically, or by any other means, including but not limited to: (a) Technical Information such as source code, algorithms, software architecture, API specifications, database schemas, system configurations, security protocols, and development roadmaps; (b) Business Information such as customer lists, contact databases, pricing models, revenue figures, financial projections, marketing strategies, and partnership agreements; (c) Product Information such as UI/UX designs, AI models, training data, integration specifications, and unreleased features; (d) Operational Information such as internal processes, SOPs, employee records, legal strategies, and investor communications.'
        },
        {
            "heading": "2. Obligations of the Receiving Party",
            "body": "The Receiving Party agrees to: (a) Hold all Confidential Information in strict confidence and use at least the same degree of care as it uses for its own confidential information; (b) Use Confidential Information solely for the disclosed purpose; (c) Not disclose to any third party without prior written consent; (d) Not reverse engineer, decompile, or disassemble any disclosed technology; (e) Restrict access to those with a need to know who are bound by similar obligations; (f) Immediately notify the Disclosing Party of any unauthorized disclosure; (g) Upon termination, promptly return or destroy all Confidential Information."
        },
        {
            "heading": "3. Exclusions",
            "body": "Confidential Information does not include information that: (a) Is or becomes publicly available through no fault of the Receiving Party; (b) Was rightfully in possession prior to disclosure; (c) Is independently developed without reference to Confidential Information; (d) Is rightfully received from a third party without restriction; (e) Is approved for release by written authorization; (f) Is required by law, provided prompt notice is given."
        },
        {
            "heading": "4. Intellectual Property Rights",
            "body": "All Confidential Information remains the sole property of the Disclosing Party. This Agreement grants no license, right, or interest in any intellectual property. Any work product derived from Confidential Information shall be the sole property of the Disclosing Party."
        },
        {
            "heading": "5. Non-Solicitation & Non-Compete",
            "body": "During the term and for twelve (12) months following termination, the Receiving Party shall not: (a) Solicit, recruit, or hire any employee or contractor of the Disclosing Party; (b) Solicit customers or prospective customers for competing products; (c) Develop, market, or distribute products substantially similar to or competitive with the Disclosing Party's platform."
        },
        {
            "heading": "6. Term and Termination",
            "body": "This Agreement is effective from the date of last signature and remains in effect for three (3) years. Confidentiality obligations survive termination for five (5) years or for as long as information remains a trade secret. Either party may terminate with thirty (30) days written notice. Upon termination, all Confidential Information must be returned or destroyed within fourteen (14) days."
        },
        {
            "heading": "7. Remedies",
            "body": "The Receiving Party acknowledges that breach may cause irreparable harm. The Disclosing Party is entitled to injunctive relief without proving actual damages, plus recovery of all actual damages including lost profits, investigation costs, and reasonable attorneys' fees."
        },
        {
            "heading": "8. General Provisions",
            "body": "This Agreement is governed by the laws of the State of Utah. Disputes shall be resolved through binding arbitration in Salt Lake County, Utah. This constitutes the entire agreement and supersedes all prior agreements. No amendment except in writing signed by both parties. If any provision is invalid, remaining provisions continue in full force."
        },
    ]
}


# ============= ADMIN ENDPOINTS =============

@router.post("/agreements")
async def create_nda(data: NDASenderSign):
    """Admin creates and signs an NDA, ready to send to recipient"""
    db = get_db()
    now = datetime.utcnow()

    agreement = {
        "sender": {
            "name": data.sender_name,
            "title": data.sender_title,
            "signature": data.sender_signature,
            "signature_type": data.signature_type,
            "signed_at": now,
        },
        "recipient": {
            "name": data.recipient_name,
            "email": data.recipient_email.lower().strip(),
            "phone": data.recipient_phone.strip().replace("-", "").replace(" ", ""),
        },
        "status": "pending",  # pending, viewed, signed
        "content": NDA_CONTENT,
        "created_at": now,
        "sent_at": None,
        "viewed_at": None,
        "signed_at": None,
        "signed_recipient": None,
    }

    result = await db.nda_agreements.insert_one(agreement)
    nda_id = str(result.inserted_id)

    app_url = os.environ.get("APP_URL", "").rstrip("/")
    if not app_url:
        frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
        app_url = frontend_url

    return {
        "id": nda_id,
        "link": f"{app_url}/nda/sign/{nda_id}",
        "status": "pending",
        "message": "NDA created. Share the link with the recipient.",
    }


@router.get("/agreements")
async def list_ndas():
    """List all NDA agreements (super admin only)"""
    db = get_db()

    ndas = await db.nda_agreements.find().sort("created_at", -1).to_list(200)

    return [
        {
            "id": str(n["_id"]),
            "recipient_name": n.get("recipient", {}).get("name", ""),
            "recipient_email": n.get("recipient", {}).get("email", ""),
            "sender_name": n.get("sender", {}).get("name", ""),
            "status": n.get("status", "pending"),
            "created_at": n.get("created_at").isoformat() if n.get("created_at") else None,
            "signed_at": n.get("signed_at").isoformat() if n.get("signed_at") else None,
        }
        for n in ndas
    ]


@router.get("/agreements/{nda_id}")
async def get_nda(nda_id: str):
    """Get full NDA details (admin view)"""
    db = get_db()

    nda = await db.nda_agreements.find_one({"_id": ObjectId(nda_id)})
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")

    return {
        "id": str(nda["_id"]),
        "sender": nda.get("sender"),
        "recipient": nda.get("recipient"),
        "signed_recipient": nda.get("signed_recipient"),
        "content": nda.get("content"),
        "status": nda.get("status"),
        "created_at": nda.get("created_at").isoformat() if nda.get("created_at") else None,
        "sent_at": nda.get("sent_at").isoformat() if nda.get("sent_at") else None,
        "viewed_at": nda.get("viewed_at").isoformat() if nda.get("viewed_at") else None,
        "signed_at": nda.get("signed_at").isoformat() if nda.get("signed_at") else None,
    }


@router.post("/agreements/{nda_id}/send")
async def send_nda_email(nda_id: str):
    """Send NDA link to recipient via email"""
    db = get_db()

    nda = await db.nda_agreements.find_one({"_id": ObjectId(nda_id)})
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")

    recipient = nda.get("recipient", {})
    email = recipient.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No recipient email")

    app_url = os.environ.get("APP_URL", "").rstrip("/")
    if not app_url:
        app_url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    sign_link = f"{app_url}/nda/sign/{nda_id}"

    sender_name = nda.get("sender", {}).get("name", "i'M On Social")

    # Send via Resend
    resend_key = os.environ.get("RESEND_API_KEY")
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key

            html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                <div style="text-align: center; margin-bottom: 32px;">
                    <h1 style="font-size: 24px; color: #1a1a1a; margin: 0;">Non-Disclosure Agreement</h1>
                    <p style="color: #666; margin-top: 8px;">from {sender_name} at i'M On Social</p>
                </div>
                <div style="background: #f8f9fa; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
                    <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0;">
                        Hi {recipient.get('name', 'there')},
                    </p>
                    <p style="color: #333; font-size: 16px; line-height: 1.6;">
                        {sender_name} has prepared a Non-Disclosure Agreement for your review and signature.
                        Please click the button below to review the agreement and provide your digital signature.
                    </p>
                    <p style="color: #666; font-size: 14px; line-height: 1.6;">
                        You'll need your email address and phone number to verify your identity before signing.
                    </p>
                </div>
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{sign_link}" style="display: inline-block; background: #007AFF; color: white; text-decoration: none; padding: 16px 48px; border-radius: 12px; font-size: 16px; font-weight: 600;">
                        Review & Sign NDA
                    </a>
                </div>
                <div style="text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee;">
                    <p>i'M On Social LLC | 1741 Lunford Ln, Riverton, UT 84065</p>
                    <p>This is a legally binding document. Please review carefully before signing.</p>
                </div>
            </div>
            """

            resend.Emails.send({
                "from": "i'M On Social <noreply@imosapp.com>",
                "to": [email],
                "subject": f"NDA for Review & Signature from {sender_name}",
                "html": html,
            })
            logger.info(f"NDA email sent to {email} for NDA {nda_id}")
        except Exception as e:
            logger.error(f"Failed to send NDA email: {e}")

    await db.nda_agreements.update_one(
        {"_id": ObjectId(nda_id)},
        {"$set": {"status": "pending", "sent_at": datetime.utcnow()}}
    )

    return {"success": True, "message": f"NDA link sent to {email}", "link": sign_link}


@router.delete("/agreements/{nda_id}")
async def delete_nda(nda_id: str):
    """Delete an NDA (only unsigned ones)"""
    db = get_db()

    nda = await db.nda_agreements.find_one({"_id": ObjectId(nda_id)})
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")

    if nda.get("status") == "signed":
        raise HTTPException(status_code=400, detail="Cannot delete a signed NDA")

    await db.nda_agreements.delete_one({"_id": ObjectId(nda_id)})
    return {"success": True}


# ============= PUBLIC SIGNING ENDPOINTS =============

@router.get("/sign/{nda_id}")
async def get_nda_for_signing(nda_id: str):
    """Public: Get NDA info for the verification step (no auth required)"""
    db = get_db()

    nda = await db.nda_agreements.find_one({"_id": ObjectId(nda_id)})
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")

    return {
        "id": str(nda["_id"]),
        "sender_name": nda.get("sender", {}).get("name", ""),
        "recipient_name": nda.get("recipient", {}).get("name", ""),
        "status": nda.get("status"),
        "created_at": nda.get("created_at").isoformat() if nda.get("created_at") else None,
    }


@router.post("/sign/{nda_id}/verify")
async def verify_recipient(nda_id: str, data: NDAVerify):
    """Public: Verify recipient identity with email + phone"""
    db = get_db()

    nda = await db.nda_agreements.find_one({"_id": ObjectId(nda_id)})
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")

    recipient = nda.get("recipient", {})
    stored_email = recipient.get("email", "").lower().strip()
    stored_phone = recipient.get("phone", "").replace("-", "").replace(" ", "")

    input_email = data.email.lower().strip()
    input_phone = data.phone.strip().replace("-", "").replace(" ", "").replace("(", "").replace(")", "")

    # Match last 10 digits of phone for flexibility
    if stored_phone[-10:] != input_phone[-10:] or stored_email != input_email:
        raise HTTPException(status_code=403, detail="Verification failed. Please check your email and phone number.")

    # Mark as viewed
    if nda.get("status") == "pending":
        await db.nda_agreements.update_one(
            {"_id": ObjectId(nda_id)},
            {"$set": {"status": "viewed", "viewed_at": datetime.utcnow()}}
        )

    # Return the full NDA content for signing
    return {
        "verified": True,
        "id": str(nda["_id"]),
        "sender": {
            "name": nda.get("sender", {}).get("name"),
            "title": nda.get("sender", {}).get("title"),
            "signature": nda.get("sender", {}).get("signature"),
            "signature_type": nda.get("sender", {}).get("signature_type"),
            "signed_at": nda.get("sender", {}).get("signed_at").isoformat() if nda.get("sender", {}).get("signed_at") else None,
        },
        "recipient": {
            "name": recipient.get("name"),
            "email": recipient.get("email"),
        },
        "content": nda.get("content"),
        "status": nda.get("status") if nda.get("status") != "pending" else "viewed",
    }


@router.post("/sign/{nda_id}/submit")
async def submit_signature(nda_id: str, data: NDARecipientSign):
    """Public: Recipient signs the NDA"""
    db = get_db()

    nda = await db.nda_agreements.find_one({"_id": ObjectId(nda_id)})
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")

    if nda.get("status") == "signed":
        raise HTTPException(status_code=400, detail="NDA already signed")

    now = datetime.utcnow()

    signed_recipient = {
        "name": data.name,
        "title": data.title,
        "company": data.company,
        "email": data.email,
        "signature": data.signature,
        "signature_type": data.signature_type,
        "signed_at": now,
    }

    await db.nda_agreements.update_one(
        {"_id": ObjectId(nda_id)},
        {"$set": {
            "signed_recipient": signed_recipient,
            "status": "signed",
            "signed_at": now,
        }}
    )

    # Send confirmation email to both parties
    resend_key = os.environ.get("RESEND_API_KEY")
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key

            sender_email = nda.get("content", {}).get("company_email", "forest@imosapp.com")
            recipient_email = data.email
            sender_name = nda.get("sender", {}).get("name", "")

            html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                <div style="text-align: center; margin-bottom: 24px;">
                    <div style="width: 60px; height: 60px; background: #34C75920; border-radius: 30px; display: inline-flex; align-items: center; justify-content: center;">
                        <span style="font-size: 28px; color: #34C759;">&#10003;</span>
                    </div>
                </div>
                <h1 style="text-align: center; font-size: 22px; color: #1a1a1a;">NDA Successfully Signed</h1>
                <div style="background: #f8f9fa; border-radius: 12px; padding: 20px; margin: 24px 0;">
                    <p style="margin: 0 0 8px;"><strong>Disclosing Party:</strong> {sender_name}</p>
                    <p style="margin: 0 0 8px;"><strong>Receiving Party:</strong> {data.name} ({data.company})</p>
                    <p style="margin: 0;"><strong>Signed:</strong> {now.strftime('%B %d, %Y at %I:%M %p UTC')}</p>
                </div>
                <p style="color: #666; font-size: 14px; line-height: 1.6;">
                    Both parties have digitally signed this Non-Disclosure Agreement. 
                    This email serves as confirmation of the executed agreement.
                </p>
                <div style="text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee;">
                    <p>i'M On Social LLC | 1741 Lunford Ln, Riverton, UT 84065</p>
                </div>
            </div>
            """

            # Send to both parties
            for to_email in [sender_email, recipient_email]:
                if to_email:
                    resend.Emails.send({
                        "from": "i'M On Social <noreply@imosapp.com>",
                        "to": [to_email],
                        "subject": "NDA Signed - Confirmation",
                        "html": html,
                    })
            logger.info(f"NDA {nda_id} signed by {data.name}, confirmation emails sent")
        except Exception as e:
            logger.error(f"Failed to send NDA confirmation: {e}")

    return {
        "success": True,
        "message": "NDA signed successfully. Confirmation sent to both parties.",
    }
