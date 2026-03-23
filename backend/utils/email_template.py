"""
White-label branded email template builder.
Pulls branding from store, organization, and partner settings.
"""
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


async def get_brand_context(db, user_id: str) -> dict:
    """Gather all branding info from user -> store -> org -> partner."""
    brand = {
        "store_name": "i'M On Social",
        "logo_url": "",
        "primary_color": "#007AFF",
        "accent_color": "#C9A962",
        "sender_name": "",
        "sender_title": "",
        "sender_phone": "",
        "sender_email": "",
        "sender_photo": "",
        "card_url": "",
        "social_links": {},
        "footer_text": "",
        "powered_by": "i'M On Social",
        "powered_by_url": "https://app.imonsocial.com/imos",
    }

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return brand

        brand["sender_name"] = user.get("name", "")
        brand["sender_title"] = user.get("title", "")
        brand["sender_phone"] = user.get("phone", "")
        brand["sender_email"] = user.get("email", "")
        
        # Build user photo URL
        import os
        app_url = os.environ.get("APP_URL", "https://app.imonsocial.com").rstrip("/")
        photo = user.get("photo_thumbnail_url") or user.get("photo_url") or ""
        if photo and photo.startswith("/"):
            photo = f"{app_url}{photo}"
        brand["sender_photo"] = photo
        
        # Build digital card URL
        brand["card_url"] = f"{app_url}/card/{user_id}"

        # Get store branding
        store_id = user.get("store_id")
        if store_id:
            try:
                store = await db.stores.find_one({"_id": ObjectId(store_id)})
            except Exception:
                store = await db.stores.find_one({"_id": store_id})
            if store:
                brand["store_name"] = store.get("name", brand["store_name"])
                brand["logo_url"] = store.get("logo_url", "")
                brand["primary_color"] = store.get("primary_color", brand["primary_color"])
                brand["social_links"] = store.get("social_links", {})
                addr_parts = [store.get("address", ""), store.get("city", ""), store.get("state", "")]
                brand["footer_text"] = ", ".join(p for p in addr_parts if p)
                # Check store-level email_brand_kit overrides
                sebk = store.get("email_brand_kit", {})
                if sebk.get("logo_url"):
                    brand["logo_url"] = sebk["logo_url"]
                if sebk.get("primary_color"):
                    brand["primary_color"] = sebk["primary_color"]
                if sebk.get("footer_text"):
                    brand["footer_text"] = sebk["footer_text"]

        # Get org branding (may override store)
        org_id = user.get("org_id") or user.get("organization_id")
        if org_id:
            try:
                org = await db.organizations.find_one({"_id": ObjectId(org_id)})
            except Exception:
                org = await db.organizations.find_one({"_id": org_id})
            if org:
                if org.get("name"):
                    brand["store_name"] = org["name"]
                if org.get("logo_url"):
                    brand["logo_url"] = org["logo_url"]
                if org.get("primary_color"):
                    brand["primary_color"] = org["primary_color"]
                if org.get("accent_color"):
                    brand["accent_color"] = org["accent_color"]
                # Check email_brand_kit for specific overrides
                ebk = org.get("email_brand_kit", {})
                if ebk.get("logo_url"):
                    brand["logo_url"] = ebk["logo_url"]
                if ebk.get("primary_color"):
                    brand["primary_color"] = ebk["primary_color"]
                if ebk.get("footer_text"):
                    brand["footer_text"] = ebk["footer_text"]
                if ebk.get("powered_by"):
                    brand["powered_by"] = ebk["powered_by"]

        # Get partner branding (highest priority)
        partner_id = user.get("partner_id")
        if not partner_id and store_id:
            try:
                store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"partner_id": 1})
            except Exception:
                store = await db.stores.find_one({"_id": store_id}, {"partner_id": 1})
            partner_id = store.get("partner_id") if store else None

        if partner_id:
            try:
                partner = await db.partners.find_one({"_id": ObjectId(partner_id)})
            except Exception:
                partner = await db.partners.find_one({"_id": partner_id})
            if partner:
                if partner.get("logo"):
                    brand["logo_url"] = partner["logo"]
                if partner.get("primary_color"):
                    brand["primary_color"] = partner["primary_color"]
                if partner.get("accent_color"):
                    brand["accent_color"] = partner["accent_color"]
                if partner.get("name"):
                    brand["powered_by"] = partner["name"]

    except Exception as e:
        logger.error(f"Error loading brand context: {e}")

    return brand


def build_branded_email(content: str, brand: dict, contact_name: str = "") -> str:
    """Build a white-label HTML email with full branding and personal signature."""
    import os
    app_url = os.environ.get("APP_URL", "https://app.imonsocial.com").rstrip("/")
    
    pc = brand["primary_color"]
    ac = brand.get("accent_color", "#C9A962")
    logo = brand.get("logo_url", "")
    # Resolve relative URLs to absolute for email rendering
    if logo and logo.startswith("/"):
        logo = f"{app_url}{logo}"
    store = brand.get("store_name", "")
    sender = brand.get("sender_name", "")
    sender_title = brand.get("sender_title", "")
    sender_phone = brand.get("sender_phone", "")
    sender_email = brand.get("sender_email", "")
    sender_photo = brand.get("sender_photo", "")
    card_url = brand.get("card_url", "")
    social = brand.get("social_links", {})
    footer = brand.get("footer_text", "")
    powered_by = brand.get("powered_by", "IM On Social")
    powered_by_url = brand.get("powered_by_url", "https://app.imonsocial.com/imos")

    # Build social links row
    social_html = ""
    social_icons = {
        "website": ("globe-outline", "Website"),
        "facebook": ("logo-facebook", "Facebook"),
        "instagram": ("logo-instagram", "Instagram"),
        "twitter": ("logo-twitter", "Twitter"),
        "linkedin": ("logo-linkedin", "LinkedIn"),
        "youtube": ("logo-youtube", "YouTube"),
        "tiktok": ("musical-notes", "TikTok"),
    }
    for key, url in social.items():
        if url and key in social_icons:
            label = social_icons[key][1]
            social_html += f'<a href="{url}" style="color:{pc};text-decoration:none;font-size:13px;margin:0 8px;">{label}</a>'

    # Logo section
    logo_html = ""
    if logo:
        logo_html = f'''
        <div style="text-align:center;padding:24px 0 16px;">
            <img src="{logo}" alt="{store}" style="max-width:160px;max-height:60px;border-radius:8px;" />
        </div>'''
    else:
        logo_html = f'''
        <div style="text-align:center;padding:24px 0 16px;">
            <h2 style="margin:0;font-size:22px;color:{pc};font-weight:700;">{store}</h2>
        </div>'''

    # Personal signature block with photo, name, title, phone, email, card link
    photo_cell = ""
    if sender_photo:
        photo_cell = f'''
            <td style="vertical-align:top;padding-right:14px;">
                <img src="{sender_photo}" alt="{sender}" style="width:56px;height:56px;border-radius:50%;object-fit:cover;" />
            </td>'''
    
    sig_details = f'<p style="margin:0;font-size:15px;color:#1C1C1E;font-weight:600;">{sender}</p>'
    if sender_title:
        sig_details += f'<p style="margin:2px 0 0;font-size:13px;color:#8E8E93;">{sender_title} &middot; {store}</p>'
    else:
        sig_details += f'<p style="margin:2px 0 0;font-size:13px;color:#8E8E93;">{store}</p>'
    
    contact_lines = []
    if sender_phone:
        contact_lines.append(f'<a href="tel:{sender_phone}" style="color:{pc};text-decoration:none;font-size:13px;">{sender_phone}</a>')
    if sender_email:
        contact_lines.append(f'<a href="mailto:{sender_email}" style="color:{pc};text-decoration:none;font-size:13px;">{sender_email}</a>')
    if contact_lines:
        sig_details += f'<p style="margin:4px 0 0;">{" &nbsp;|&nbsp; ".join(contact_lines)}</p>'
    
    if card_url:
        sig_details += f'<p style="margin:6px 0 0;"><a href="{card_url}" style="color:{pc};text-decoration:none;font-size:12px;font-weight:500;">View My Digital Card</a></p>'

    signature_html = f'''
        <div style="padding:0 28px 20px;border-top:1px solid #F0F0F0;padding-top:16px;">
            <table cellpadding="0" cellspacing="0" border="0"><tr>
                {photo_cell}
                <td style="vertical-align:top;">
                    {sig_details}
                </td>
            </tr></table>
        </div>'''

    # CTA button
    cta_html = f'''
    <div style="text-align:center;margin:24px 0 8px;">
        <a href="{powered_by_url}" style="display:inline-block;background:{pc};color:#FFF;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:14px;">
            See {powered_by} in Action
        </a>
    </div>'''

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F2F2F7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:16px;">

    <!-- Header with brand color bar -->
    <div style="background:{pc};height:4px;border-radius:4px 4px 0 0;"></div>

    <div style="background:#FFFFFF;border-radius:0 0 16px 16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

        {logo_html}

        <!-- Message Content -->
        <div style="padding:0 28px 24px;">
            <div style="background:#F9F9FB;border-radius:12px;padding:20px 24px;border-left:3px solid {pc};">
                <p style="margin:0;font-size:15px;line-height:1.7;color:#1C1C1E;white-space:pre-wrap;">{content}</p>
            </div>
        </div>

        <!-- Personal Signature -->
        {signature_html}

        {cta_html}

        <!-- Social Links -->
        {f'<div style="text-align:center;padding:12px 0;">{social_html}</div>' if social_html else ''}

        <!-- Footer -->
        <div style="background:#F9F9FB;padding:16px 28px;text-align:center;border-top:1px solid #F0F0F0;">
            {f'<p style="margin:0 0 6px;font-size:12px;color:#8E8E93;">{footer}</p>' if footer else ''}
            <p style="margin:0;font-size:11px;color:#C7C7CC;">
                Powered by <a href="{powered_by_url}" style="color:{pc};text-decoration:none;font-weight:500;">{powered_by}</a>
            </p>
        </div>
    </div>
</div>
</body>
</html>'''

    return html
