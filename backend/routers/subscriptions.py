"""
Subscriptions & Quotes Router
Handles MVPLine subscription plans, quotes, and Stripe billing
"""
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional
import logging
import os

from routers.database import get_db

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])
logger = logging.getLogger(__name__)

# ============= PRICING PLANS =============
# These are fixed server-side - NEVER accept amounts from frontend

# Individual Plans
INDIVIDUAL_PLANS = {
    "monthly": {
        "id": "monthly",
        "name": "Monthly",
        "type": "individual",
        "price": 100.00,
        "interval": "month",
        "trial_days": 7,
        "description": "Month-to-month flexibility",
        "features": [
            "Full MVPLine access",
            "Unlimited contacts",
            "AI-powered messaging",
            "Campaign automation",
            "7-day free trial",
            "Cancel with 30 days notice"
        ],
        "badge": None,
    },
    "annual": {
        "id": "annual",
        "name": "Annual",
        "type": "individual",
        "price": 1000.00,
        "interval": "year",
        "trial_days": 7,
        "description": "Best value - Save $200/year",
        "original_price": 1200.00,
        "discount_percent": 17,
        "features": [
            "Everything in Monthly",
            "Save $200 per year",
            "Priority support",
            "7-day free trial",
            "Annual commitment"
        ],
        "badge": "BEST VALUE",
    },
    "intro": {
        "id": "intro",
        "name": "Introductory Offer",
        "type": "individual",
        "price": 50.00,
        "interval": "month",
        "trial_days": 14,
        "intro_months": 3,
        "regular_price": 100.00,
        "description": "Special offer for new customers",
        "features": [
            "Full MVPLine access",
            "$50/month for first 3 months",
            "Then $100/month",
            "14-day free trial",
            "No commitment"
        ],
        "badge": "LIMITED TIME",
        "terms": "After 3 months, billing continues at $100/month"
    }
}

# Store/Business Plans (per user pricing)
STORE_PLANS = {
    "store_standard": {
        "id": "store_standard",
        "name": "Store Plan",
        "type": "store",
        "price_per_user": 75.00,
        "min_users": 5,
        "interval": "month",
        "trial_days": 7,
        "description": "For dealerships & sales teams",
        "features": [
            "$75/user per month",
            "Minimum 5 users",
            "Team management dashboard",
            "Store-level analytics",
            "Shared contact lists",
            "Campaign templates",
            "7-day free trial",
            "Cancel with 30 days notice"
        ],
        "badge": "TEAMS",
    },
    "store_volume": {
        "id": "store_volume",
        "name": "Store Plan (6+ Users)",
        "type": "store",
        "price_per_user": 65.00,
        "min_users": 6,
        "interval": "month",
        "trial_days": 7,
        "description": "Volume discount for larger teams",
        "original_price_per_user": 75.00,
        "discount_percent": 13,
        "features": [
            "$65/user per month",
            "6+ users",
            "Save $10/user/month",
            "Everything in Store Plan",
            "Priority onboarding",
            "Dedicated support",
            "7-day free trial"
        ],
        "badge": "BEST FOR TEAMS",
    },
}

# Combined pricing
PRICING_PLANS = {**INDIVIDUAL_PLANS, **STORE_PLANS}


def calculate_store_price(num_users: int) -> dict:
    """Calculate store pricing based on number of users"""
    if num_users < 5:
        return {
            "error": True,
            "message": "Minimum 5 users required for store plans",
            "min_users": 5
        }
    
    if num_users >= 6:
        price_per_user = 65.00
        plan_id = "store_volume"
        discount = (75.00 - 65.00) * num_users
    else:
        price_per_user = 75.00
        plan_id = "store_standard"
        discount = 0
    
    total = price_per_user * num_users
    
    return {
        "error": False,
        "plan_id": plan_id,
        "num_users": num_users,
        "price_per_user": price_per_user,
        "total_monthly": total,
        "total_annual": total * 12,
        "discount_monthly": discount,
        "discount_annual": discount * 12,
    }


@router.get("/plans")
async def get_pricing_plans(plan_type: Optional[str] = None):
    """Get all available subscription plans"""
    if plan_type == "individual":
        plans = list(INDIVIDUAL_PLANS.values())
    elif plan_type == "store":
        plans = list(STORE_PLANS.values())
    else:
        plans = list(PRICING_PLANS.values())
    
    return {
        "plans": plans,
        "currency": "usd",
        "terms": {
            "cancellation": "Cancel anytime with 30 days notice",
            "trial": "All plans include a free trial period",
            "refund": "No refunds for partial billing periods"
        }
    }


@router.get("/plans/store/calculate")
async def calculate_store_pricing(num_users: int):
    """Calculate pricing for store plan based on number of users"""
    return calculate_store_price(num_users)


@router.get("/plans/{plan_id}")
async def get_plan_details(plan_id: str):
    """Get details for a specific plan"""
    if plan_id not in PRICING_PLANS:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PRICING_PLANS[plan_id]


# ============= DISCOUNT CODES =============

DISCOUNT_TIERS = [5, 10, 15, 20, 25]  # Available discount percentages

@router.get("/discount-codes")
async def list_discount_codes(active_only: bool = True):
    """List all discount codes"""
    db = get_db()
    
    query = {}
    if active_only:
        query["status"] = "active"
        query["expires_at"] = {"$gt": datetime.utcnow()}
    
    codes = await db.discount_codes.find(query).sort("created_at", -1).to_list(100)
    
    for code in codes:
        code["_id"] = str(code["_id"])
    
    return codes


@router.post("/discount-codes")
async def create_discount_code(data: dict):
    """Create a new discount code"""
    db = get_db()
    
    code = data.get("code", "").upper().strip()
    discount_percent = data.get("discount_percent", 10)
    max_uses = data.get("max_uses")  # None = unlimited
    expires_days = data.get("expires_days", 90)
    description = data.get("description", "")
    plan_types = data.get("plan_types", ["individual", "store"])  # Which plans it applies to
    
    if not code:
        # Generate a random code
        import random
        import string
        code = "MVP" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    if discount_percent not in DISCOUNT_TIERS:
        raise HTTPException(status_code=400, detail=f"Discount must be one of: {DISCOUNT_TIERS}")
    
    # Check for duplicate
    existing = await db.discount_codes.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=400, detail="Code already exists")
    
    discount_code = {
        "code": code,
        "discount_percent": discount_percent,
        "max_uses": max_uses,
        "times_used": 0,
        "plan_types": plan_types,
        "description": description,
        "status": "active",
        "expires_at": datetime.utcnow() + timedelta(days=expires_days),
        "created_at": datetime.utcnow(),
    }
    
    result = await db.discount_codes.insert_one(discount_code)
    discount_code["_id"] = str(result.inserted_id)
    
    logger.info(f"Discount code {code} created with {discount_percent}% off")
    return discount_code


@router.get("/discount-codes/validate/{code}")
async def validate_discount_code(code: str, plan_type: str = "individual"):
    """Validate a discount code"""
    db = get_db()
    
    discount = await db.discount_codes.find_one({
        "code": code.upper(),
        "status": "active",
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not discount:
        return {"valid": False, "message": "Invalid or expired code"}
    
    if discount.get("max_uses") and discount["times_used"] >= discount["max_uses"]:
        return {"valid": False, "message": "Code has reached maximum uses"}
    
    if plan_type not in discount.get("plan_types", ["individual", "store"]):
        return {"valid": False, "message": f"Code not valid for {plan_type} plans"}
    
    return {
        "valid": True,
        "discount_percent": discount["discount_percent"],
        "description": discount.get("description", ""),
    }


@router.delete("/discount-codes/{code_id}")
async def deactivate_discount_code(code_id: str):
    """Deactivate a discount code"""
    db = get_db()
    
    result = await db.discount_codes.update_one(
        {"_id": ObjectId(code_id)},
        {"$set": {"status": "inactive"}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Code not found")
    
    return {"message": "Code deactivated"}


# ============= QUOTES =============

@router.post("/quotes")
async def create_quote(data: dict):
    """Create a new subscription quote with full business details"""
    db = get_db()
    
    # Plan selection
    plan_type = data.get("plan_type", "individual")  # individual or store
    plan_id = data.get("plan_id")
    num_users = data.get("num_users", 1)
    
    # Customer info
    customer_email = data.get("email")
    customer_name = data.get("name")
    customer_phone = data.get("phone")
    customer_title = data.get("title", "")
    
    # Business info (for store plans / 10DLC compliance)
    business_info = {
        "company_name": data.get("company_name", ""),
        "website": data.get("website", ""),
        "address": {
            "street": data.get("street_address", ""),
            "city": data.get("city", ""),
            "state": data.get("state", ""),
            "zip": data.get("zip_code", ""),
            "country": data.get("country", "USA"),
        },
        "ein": data.get("ein", ""),  # Employer Identification Number
        "business_type": data.get("business_type", ""),  # LLC, Corp, etc.
        "w9_required": data.get("w9_required", False),
        "authorized_signer": {
            "name": data.get("signer_name", ""),
            "title": data.get("signer_title", ""),
            "email": data.get("signer_email", ""),
            "phone": data.get("signer_phone", ""),
        },
        # 10DLC fields for Twilio compliance
        "ten_dlc": {
            "brand_name": data.get("brand_name", ""),
            "vertical": data.get("vertical", ""),  # Industry type
            "use_case": data.get("use_case", "MIXED"),  # SMS use case
            "sample_messages": data.get("sample_messages", []),
        }
    }
    
    # Quote preparer info
    prepared_by = {
        "name": data.get("prepared_by_name", ""),
        "email": data.get("prepared_by_email", ""),
        "company": data.get("our_company_name", "MVPLine"),
        "address": data.get("our_company_address", ""),
    }
    
    # Discount handling
    discount_percent = data.get("discount_percent", 0)
    discount_code = data.get("discount_code", "")
    
    # Validate discount
    if discount_code:
        code_validation = await validate_discount_code(discount_code, plan_type)
        if code_validation["valid"]:
            discount_percent = code_validation["discount_percent"]
        else:
            raise HTTPException(status_code=400, detail=code_validation["message"])
    
    if discount_percent > 25:
        raise HTTPException(status_code=400, detail="Maximum discount is 25%")
    
    notes = data.get("notes", "")
    valid_days = data.get("valid_days", 30)
    
    # Determine plan and pricing
    if plan_type == "store":
        if num_users < 5:
            raise HTTPException(status_code=400, detail="Minimum 5 users for store plans")
        
        store_pricing = calculate_store_price(num_users)
        if store_pricing.get("error"):
            raise HTTPException(status_code=400, detail=store_pricing["message"])
        
        base_price = store_pricing["total_monthly"]
        price_per_user = store_pricing["price_per_user"]
        plan_name = f"Store Plan ({num_users} users)"
        interval = "month"
        trial_days = 7
    else:
        if not plan_id or plan_id not in INDIVIDUAL_PLANS:
            plan_id = "monthly"  # Default to monthly
        
        plan = INDIVIDUAL_PLANS[plan_id]
        base_price = plan["price"]
        price_per_user = None
        plan_name = plan["name"]
        interval = plan["interval"]
        trial_days = plan["trial_days"]
    
    # Apply discount
    discount_amount = (base_price * discount_percent / 100) if discount_percent else 0
    final_price = base_price - discount_amount
    
    quote = {
        "quote_number": f"Q-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "plan_type": plan_type,
        "plan_id": plan_id if plan_type == "individual" else "store",
        "plan_name": plan_name,
        
        "customer": {
            "email": customer_email,
            "name": customer_name,
            "phone": customer_phone,
            "title": customer_title,
        },
        
        "business_info": business_info,
        "prepared_by": prepared_by,
        
        "pricing": {
            "base_price": base_price,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "discount_code": discount_code if discount_code else None,
            "final_price": final_price,
            "interval": interval,
            "trial_days": trial_days,
            "currency": "usd",
            "num_users": num_users if plan_type == "store" else 1,
            "price_per_user": price_per_user,
        },
        
        "notes": notes,
        "status": "draft",  # draft, sent, viewed, accepted, expired, cancelled
        "valid_until": datetime.utcnow() + timedelta(days=valid_days),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    result = await db.subscription_quotes.insert_one(quote)
    quote["_id"] = str(result.inserted_id)
    
    # Mark discount code as used if applicable
    if discount_code:
        await db.discount_codes.update_one(
            {"code": discount_code.upper()},
            {"$inc": {"times_used": 1}}
        )
    
    logger.info(f"Quote {quote['quote_number']} created for {customer_email or business_info.get('company_name')}")
    return quote


@router.get("/quotes")
async def list_quotes(status: Optional[str] = None):
    """List all quotes (admin only in future)"""
    db = get_db()
    
    query = {}
    if status:
        query["status"] = status
    
    quotes = await db.subscription_quotes.find(query).sort("created_at", -1).to_list(100)
    
    for quote in quotes:
        quote["_id"] = str(quote["_id"])
    
    return quotes


@router.get("/quotes/{quote_id}")
async def get_quote(quote_id: str):
    """Get a specific quote by ID"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    quote["_id"] = str(quote["_id"])
    
    # Check if expired
    if quote["status"] == "pending" and quote["valid_until"] < datetime.utcnow():
        quote["status"] = "expired"
        await db.subscription_quotes.update_one(
            {"_id": ObjectId(quote_id)},
            {"$set": {"status": "expired"}}
        )
    
    return quote


@router.patch("/quotes/{quote_id}")
async def update_quote(quote_id: str, data: dict):
    """Update a quote (notes, status, etc.)"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    # Only allow updating certain fields
    allowed_fields = ["notes", "status", "valid_until"]
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    await db.subscription_quotes.update_one(
        {"_id": ObjectId(quote_id)},
        {"$set": update_dict}
    )
    
    return {"message": "Quote updated successfully"}


@router.post("/quotes/{quote_id}/send")
async def send_quote(quote_id: str):
    """Send/resend a quote to the customer via email"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    customer_email = quote.get("customer", {}).get("email")
    if not customer_email:
        raise HTTPException(status_code=400, detail="No customer email on this quote")
    
    # Update status to sent
    await db.subscription_quotes.update_one(
        {"_id": ObjectId(quote_id)},
        {"$set": {
            "status": "sent",
            "sent_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    # TODO: Send actual email when Resend is configured
    # For now, just update status
    logger.info(f"Quote {quote['quote_number']} marked as sent to {customer_email}")
    
    return {
        "message": "Quote sent successfully",
        "sent_to": customer_email
    }


@router.delete("/quotes/{quote_id}")
async def delete_quote(quote_id: str):
    """Delete a quote (only drafts can be deleted)"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    # Only allow deleting drafts
    if quote["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft quotes can be deleted")
    
    await db.subscription_quotes.delete_one({"_id": ObjectId(quote_id)})
    return {"message": "Quote deleted successfully"}


@router.put("/quotes/{quote_id}/archive")
async def archive_quote(quote_id: str):
    """Archive a quote"""
    db = get_db()
    
    quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    await db.subscription_quotes.update_one(
        {"_id": ObjectId(quote_id)},
        {"$set": {"status": "archived", "archived_at": datetime.utcnow()}}
    )
    return {"message": "Quote archived successfully"}



# ============= CHECKOUT & PAYMENT =============

@router.post("/checkout")
async def create_checkout_session(request: Request, data: dict):
    """Create a Stripe checkout session for subscription"""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    
    db = get_db()
    
    plan_id = data.get("plan_id")
    quote_id = data.get("quote_id")
    origin_url = data.get("origin_url")
    customer_email = data.get("email")
    
    if not origin_url:
        raise HTTPException(status_code=400, detail="Origin URL is required")
    
    # Get plan - amount comes from server only
    if plan_id not in PRICING_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = PRICING_PLANS[plan_id]
    
    # If quote_id provided, verify and use quote data
    quote = None
    if quote_id:
        quote = await db.subscription_quotes.find_one({"_id": ObjectId(quote_id)})
        if quote:
            customer_email = quote["customer"]["email"]
    
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    host_url = str(request.base_url).rstrip('/')
    webhook_url = f"{host_url}/api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    # Build dynamic URLs
    success_url = f"{origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/subscription/cancel"
    
    # Determine amount - for trial, charge $0 initially (Stripe handles trial)
    # For simplicity, we charge the first payment after trial
    amount = plan["price"]
    
    metadata = {
        "type": "subscription",
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "interval": plan["interval"],
        "trial_days": str(plan["trial_days"]),
        "customer_email": customer_email or "",
    }
    
    if quote_id:
        metadata["quote_id"] = quote_id
    
    try:
        checkout_request = CheckoutSessionRequest(
            amount=amount,
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata
        )
        
        session = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Create payment transaction record
        transaction = {
            "session_id": session.session_id,
            "type": "subscription",
            "plan_id": plan_id,
            "plan_name": plan["name"],
            "amount": amount,
            "currency": "usd",
            "customer_email": customer_email,
            "quote_id": quote_id,
            "status": "initiated",
            "payment_status": "pending",
            "metadata": metadata,
            "created_at": datetime.utcnow(),
        }
        
        await db.payment_transactions.insert_one(transaction)
        
        # Update quote status if applicable
        if quote_id:
            await db.subscription_quotes.update_one(
                {"_id": ObjectId(quote_id)},
                {"$set": {"status": "checkout_started", "updated_at": datetime.utcnow()}}
            )
        
        logger.info(f"Checkout session created for plan {plan_id}")
        
        return {
            "url": session.url,
            "session_id": session.session_id
        }
        
    except Exception as e:
        logger.error(f"Checkout creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout: {str(e)}")


@router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str):
    """Get the status of a checkout session"""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    
    db = get_db()
    
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
    
    try:
        status = await stripe_checkout.get_checkout_status(session_id)
        
        # Update transaction in database
        update_data = {
            "status": status.status,
            "payment_status": status.payment_status,
            "updated_at": datetime.utcnow(),
        }
        
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": update_data}
        )
        
        # If paid, create subscription record
        if status.payment_status == "paid":
            transaction = await db.payment_transactions.find_one({"session_id": session_id})
            if transaction and not await db.subscriptions.find_one({"session_id": session_id}):
                plan_id = transaction.get("plan_id") or status.metadata.get("plan_id")
                plan = PRICING_PLANS.get(plan_id, {})
                
                # Calculate trial end and billing dates
                trial_days = plan.get("trial_days", 7)
                trial_end = datetime.utcnow() + timedelta(days=trial_days)
                
                subscription = {
                    "session_id": session_id,
                    "customer_email": transaction.get("customer_email"),
                    "plan_id": plan_id,
                    "plan_name": plan.get("name", "Unknown"),
                    "amount": transaction.get("amount"),
                    "interval": plan.get("interval", "month"),
                    "status": "trialing",
                    "trial_end": trial_end,
                    "current_period_start": datetime.utcnow(),
                    "current_period_end": trial_end,
                    "cancel_at_period_end": False,
                    "created_at": datetime.utcnow(),
                }
                
                await db.subscriptions.insert_one(subscription)
                
                # Update quote if applicable
                quote_id = transaction.get("quote_id")
                if quote_id:
                    await db.subscription_quotes.update_one(
                        {"_id": ObjectId(quote_id)},
                        {"$set": {"status": "accepted", "updated_at": datetime.utcnow()}}
                    )
                
                logger.info(f"Subscription created for session {session_id}")
        
        return {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount_total": status.amount_total,
            "currency": status.currency,
        }
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")


# ============= SUBSCRIPTION MANAGEMENT =============

@router.get("/my-subscription")
async def get_my_subscription(email: str):
    """Get subscription for a customer by email"""
    db = get_db()
    
    subscription = await db.subscriptions.find_one(
        {"customer_email": email, "status": {"$ne": "cancelled"}},
        sort=[("created_at", -1)]
    )
    
    if not subscription:
        return {"has_subscription": False}
    
    subscription["_id"] = str(subscription["_id"])
    subscription["has_subscription"] = True
    
    # Calculate days remaining in trial
    if subscription["status"] == "trialing":
        trial_end = subscription.get("trial_end")
        if trial_end:
            days_remaining = (trial_end - datetime.utcnow()).days
            subscription["trial_days_remaining"] = max(0, days_remaining)
    
    return subscription


@router.post("/cancel")
async def request_cancellation(data: dict):
    """Request subscription cancellation (30 days notice)"""
    db = get_db()
    
    email = data.get("email")
    reason = data.get("reason", "")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    subscription = await db.subscriptions.find_one(
        {"customer_email": email, "status": {"$in": ["trialing", "active"]}}
    )
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    # Calculate cancellation date (30 days from now)
    cancel_date = datetime.utcnow() + timedelta(days=30)
    
    await db.subscriptions.update_one(
        {"_id": subscription["_id"]},
        {"$set": {
            "cancel_at_period_end": True,
            "cancellation_requested_at": datetime.utcnow(),
            "cancellation_effective_date": cancel_date,
            "cancellation_reason": reason,
            "updated_at": datetime.utcnow(),
        }}
    )
    
    # Create cancellation record
    cancellation = {
        "subscription_id": str(subscription["_id"]),
        "customer_email": email,
        "reason": reason,
        "requested_at": datetime.utcnow(),
        "effective_date": cancel_date,
        "status": "pending",
    }
    await db.subscription_cancellations.insert_one(cancellation)
    
    logger.info(f"Cancellation requested for {email}, effective {cancel_date}")
    
    return {
        "message": "Cancellation request received",
        "effective_date": cancel_date.isoformat(),
        "notice_days": 30,
    }


@router.get("/cancellation-status")
async def get_cancellation_status(email: str):
    """Check if there's a pending cancellation"""
    db = get_db()
    
    cancellation = await db.subscription_cancellations.find_one(
        {"customer_email": email, "status": "pending"},
        sort=[("requested_at", -1)]
    )
    
    if not cancellation:
        return {"has_pending_cancellation": False}
    
    cancellation["_id"] = str(cancellation["_id"])
    cancellation["has_pending_cancellation"] = True
    
    return cancellation
