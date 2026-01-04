"""
Billing API routes - Stripe checkout, portal, and webhooks.

Handles subscription lifecycle:
1. Checkout: Create subscription payment
2. Webhooks: Process subscription events
3. Portal: Manage existing subscription
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
import logging

from app.database import get_session
from app.models import User
from app.services.billing import stripe_service, StripeError
from sqlalchemy import select

logger = logging.getLogger("ships.billing")

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    """Request to create checkout session."""
    price_id: str = Field(..., description="Stripe price ID for the plan")
    success_url: str = Field(..., description="URL to redirect after success")
    cancel_url: str = Field(..., description="URL to redirect if canceled")


class PortalRequest(BaseModel):
    """Request to access customer portal."""
    return_url: str = Field(..., description="URL to return to from portal")


@router.post("/create-checkout")
async def create_checkout_session(
    request: Request,
    checkout_req: CheckoutRequest,
    db: AsyncSession = Depends(get_session)
):
    """
    Create Stripe checkout session for subscription.
    
    Requires: Authenticated user (from session)
    
    Args:
        checkout_req: Checkout parameters
        db: Database session
        
    Returns:
        Checkout session with redirect URL
        
    Raises:
        HTTPException: If user not authenticated or Stripe error
    """
    try:
        # Get user from session
        session_user = request.session.get('user')
        if not session_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Fetch user from database
        result = await db.execute(
            select(User).where(User.email == session_user['email'])
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create checkout session
        session_data = await stripe_service.create_checkout_session(
            user_email=user.email,
            price_id=checkout_req.price_id,
            customer_id=user.stripe_customer_id,
            success_url=checkout_req.success_url,
            cancel_url=checkout_req.cancel_url
        )
        
        # Update user with customer ID if new
        if not user.stripe_customer_id and session_data.get('customer_id'):
            user.stripe_customer_id = session_data['customer_id']
            await db.commit()
        
        logger.info(f"Created checkout for user {user.email}")
        
        return JSONResponse(content={
            "session_id": session_data['session_id'],
            "url": session_data['url']
        })
        
    except StripeError as e:
        logger.error(f"Stripe error: {e.message}")
        raise HTTPException(status_code=400, detail={
            "error": e.code,
            "message": e.message
        })
    except Exception as e:
        logger.error(f"Unexpected error creating checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/portal")
async def create_portal_session(
    request: Request,
    portal_req: PortalRequest,
    db: AsyncSession = Depends(get_session)
):
    """
    Create Stripe customer portal session.
    
    Allows users to manage their subscription, payment methods, and billing history.
    
    Args:
        portal_req: Portal parameters
        db: Database session
        
    Returns:
        Portal URL
        
    Raises:
        HTTPException: If user not authenticated or no subscription
    """
    try:
        # Get user from session
        session_user = request.session.get('user')
        if not session_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Fetch user from database
        result = await db.execute(
            select(User).where(User.email == session_user['email'])
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.stripe_customer_id:
            raise HTTPException(status_code=400, detail="No subscription found")
        
        # Create portal session
        portal_data = await stripe_service.create_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=portal_req.return_url
        )
        
        logger.info(f"Created portal session for user {user.email}")
        
        return JSONResponse(content={"url": portal_data['url']})
        
    except StripeError as e:
        logger.error(f"Stripe error: {e.message}")
        raise HTTPException(status_code=400, detail={
            "error": e.code,
            "message": e.message
        })
    except Exception as e:
        logger.error(f"Unexpected error creating portal: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
    db: AsyncSession = Depends(get_session)
):
    """
    Handle Stripe webhook events.
    
    Processes subscription lifecycle events:
    - checkout.session.completed: New subscription created
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription canceled
    - invoice.payment_failed: Payment failed
    
    Args:
        request: FastAPI request with raw body
        stripe_signature: Stripe signature header
        db: Database session
        
    Returns:
        Success response
    """
    try:
        # Get raw body
        payload = await request.body()
        
        # Verify webhook signature
        event = stripe_service.verify_webhook_signature(payload, stripe_signature)
        
        if not event:
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Handle different event types
        if event.type == 'checkout.session.completed':
            await handle_checkout_completed(event.data.object, db)
        
        elif event.type == 'customer.subscription.updated':
            await handle_subscription_updated(event.data.object, db)
        
        elif event.type == 'customer.subscription.deleted':
            await handle_subscription_deleted(event.data.object, db)
        
        elif event.type == 'invoice.payment_failed':
            await handle_payment_failed(event.data.object, db)
        
        else:
            logger.info(f"Unhandled event type: {event.type}")
        
        return JSONResponse(content={"status": "success"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


async def handle_checkout_completed(session, db: AsyncSession):
    """Handle successful checkout - activate subscription."""
    customer_id = session.customer
    subscription_id = session.subscription
    
    # Find user by stripe_customer_id
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Get subscription details to determine tier
        subscription_data = await stripe_service.get_subscription(subscription_id)
        
        if subscription_data:
            tier = stripe_service.get_tier_from_price_id(subscription_data['price_id']) or 'pro'
            
            user.stripe_subscription_id = subscription_id
            user.subscription_status = 'active'
            user.tier = tier
            user.current_period_start = subscription_data['current_period_start']
            user.current_period_end = subscription_data['current_period_end']
            
            await db.commit()
            logger.info(f"✓ Activated {tier} subscription for {user.email}")


async def handle_subscription_updated(subscription, db: AsyncSession):
    """Handle subscription update - update tier or status."""
    subscription_id = subscription.id
    
    result = await db.execute(
        select(User).where(User.stripe_subscription_id == subscription_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        tier = stripe_service.get_tier_from_price_id(subscription['items'].data[0].price.id) or user.tier
        
        user.subscription_status = subscription.status
        user.tier = tier
        user.current_period_end = subscription.current_period_end
        
        await db.commit()
        logger.info(f"✓ Updated subscription for {user.email}: {subscription.status}")


async def handle_subscription_deleted(subscription, db: AsyncSession):
    """Handle subscription cancellation - downgrade to free."""
    subscription_id = subscription.id
    
    result = await db.execute(
        select(User).where(User.stripe_subscription_id == subscription_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        user.subscription_status = 'canceled'
        user.tier = 'free'
        user.stripe_subscription_id = None
        
        await db.commit()
        logger.info(f"✓ Downgraded {user.email} to free tier")


async def handle_payment_failed(invoice, db: AsyncSession):
    """Handle failed payment - mark subscription as past_due."""
    customer_id = invoice.customer
    
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        user.subscription_status = 'past_due'
        await db.commit()
        logger.warning(f"⚠ Payment failed for {user.email}")
