"""
Stripe service for subscription management.

Production-grade Stripe integration with:
- Checkout session creation
- Subscription management
- Webhook signature validation
- Customer portal access
- Comprehensive error handling
"""

import stripe
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger("ships.stripe")

# Stripe configuration from environment
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Price IDs for each tier
PRICE_IDS = {
    'starter_monthly': os.getenv("STRIPE_PRICE_STARTER_MONTHLY"),
    'starter_yearly': os.getenv("STRIPE_PRICE_STARTER_YEARLY"),
    'pro_monthly': os.getenv("STRIPE_PRICE_PRO_MONTHLY"),
    'pro_yearly': os.getenv("STRIPE_PRICE_PRO_YEARLY"),
    'enterprise_monthly': os.getenv("STRIPE_PRICE_ENTERPRISE_MONTHLY"),
    'enterprise_yearly': os.getenv("STRIPE_PRICE_ENTERPRISE_YEARLY"),
}

# Initialize Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info("✓ Stripe initialized")
else:
    logger.warning("⚠ STRIPE_SECRET_KEY not set - Stripe features disabled")


class StripeError(Exception):
    """Custom Stripe error with user-friendly message."""
    def __init__(self, message: str, code: str = "stripe_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class StripeService:
    """
    Stripe subscription service.
    
    Handles all Stripe interactions including checkout, subscriptions,
    webhooks, and customer portal access.
    """
    
    @staticmethod
    def is_configured() -> bool:
        """
        Check if Stripe is properly configured.
        
        Returns:
            bool: True if Stripe credentials are set
        """
        return bool(STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET)
    
    @staticmethod
    async def create_checkout_session(
        user_email: str,
        price_id: str,
        customer_id: Optional[str] = None,
        success_url: str = "",
        cancel_url: str = ""
    ) -> Dict[str, Any]:
        """
        Create Stripe checkout session for subscription.
        
        Args:
            user_email: User's email address
            price_id: Stripe price ID for the plan
            customer_id: Existing Stripe customer ID (optional)
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if user cancels
            
        Returns:
            dict: Checkout session data with url and session_id
            
        Raises:
            StripeError: If checkout session creation fails
        """
        try:
            # Build session parameters
            session_params = {
                'payment_method_types': ['card'],
                'mode': 'subscription',
                'line_items': [{
                    'price': price_id,
                    'quantity': 1,
                }],
                'success_url': success_url,
                'cancel_url': cancel_url,
                'allow_promotion_codes': True,  # Enable promo codes
            }
            
            # Use existing customer or create new
            if customer_id:
                session_params['customer'] = customer_id
            else:
                session_params['customer_email'] = user_email
                session_params['customer_creation'] = 'always'
            
            # Create checkout session
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Created checkout session for {user_email}: {session.id}")
            
            return {
                'session_id': session.id,
                'url': session.url,
                'customer_id': session.customer,
            }
            
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid Stripe request: {e}")
            raise StripeError("Invalid payment configuration", "invalid_request")
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout: {e}")
            raise StripeError("Payment system error. Please try again.", "stripe_error")
        except Exception as e:
            logger.error(f"Unexpected error creating checkout: {e}")
            raise StripeError("Failed to initiate checkout", "unknown_error")
    
    @staticmethod
    async def create_portal_session(
        customer_id: str,
        return_url: str
    ) -> Dict[str, str]:
        """
        Create Stripe customer portal session for managing subscription.
        
        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal session
            
        Returns:
            dict: Portal session with url
            
        Raises:
            StripeError: If portal session creation fails
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            
            logger.info(f"Created portal session for customer {customer_id}")
            
            return {'url': session.url}
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating portal session: {e}")
            raise StripeError("Failed to access billing portal", "portal_error")
    
    @staticmethod
    async def get_subscription(subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve subscription details from Stripe.
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            dict: Subscription data or None if not found
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            return {
                'id': subscription.id,
                'status': subscription.status,
                'current_period_start': datetime.fromtimestamp(subscription.current_period_start),
                'current_period_end': datetime.fromtimestamp(subscription.current_period_end),
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'price_id': subscription['items'].data[0].price.id,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving subscription {subscription_id}: {e}")
            return None
    
    @staticmethod
    async def cancel_subscription(subscription_id: str, immediately: bool = False) -> bool:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            immediately: If True, cancel immediately. If False, cancel at period end.
            
        Returns:
            bool: True if successful
        """
        try:
            if immediately:
                stripe.Subscription.delete(subscription_id)
            else:
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            
            logger.info(f"Canceled subscription {subscription_id} (immediate={immediately})")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Error canceling subscription {subscription_id}: {e}")
            return False
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> Optional[stripe.Event]:
        """
        Verify and construct Stripe webhook event.
        
        Args:
            payload: Raw webhook payload
            signature: Stripe signature header
            
        Returns:
            stripe.Event: Verified event or None if verification fails
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                STRIPE_WEBHOOK_SECRET
            )
            
            logger.info(f"✓ Verified webhook event: {event.type}")
            return event
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return None
    
    @staticmethod
    def get_tier_from_price_id(price_id: str) -> Optional[str]:
        """
        Map Stripe price ID to subscription tier.
        
        Args:
            price_id: Stripe price ID
            
        Returns:
            str: Tier name (starter, pro, enterprise) or None
        """
        for key, value in PRICE_IDS.items():
            if value == price_id:
                # Extract tier from key (e.g., "starter_monthly" -> "starter")
                return key.split('_')[0]
        return None


# Export singleton instance
stripe_service = StripeService()
