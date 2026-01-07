/**
 * Subscription modal for upgrading/purchasing plans.
 *
 * Displays all subscription tiers with pricing and features.
 * Handles checkout flow via Stripe.
 */

import React, { useState } from 'react';
import './SubscriptionModal.css';

interface SubscriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTier?: string;
}

interface TierInfo {
  name: string;
  monthlyPrice: number;
  yearlyPrice: number;
  features: string[];
  priceIds: {
    monthly: string;
    yearly: string;
  };
}

const TIERS: Record<string, TierInfo> = {
  free: {
    name: 'Free',
    monthlyPrice: 0,
    yearlyPrice: 0,
    features: [
      '5 prompts per day',
      '1 project',
      '25k tokens/month',
      'Community support'
    ],
    priceIds: { monthly: '', yearly: '' }
  },
  starter: {
    name: 'Starter',
    monthlyPrice: 9,
    yearlyPrice: 90,
    features: [
      '100 prompts per day',
      '3 projects',
      '500k tokens/month',
      'Email support'
    ],
    priceIds: {
      monthly: import.meta.env.VITE_STRIPE_PRICE_STARTER_MONTHLY || '',
      yearly: import.meta.env.VITE_STRIPE_PRICE_STARTER_YEARLY || ''
    }
  },
  pro: {
    name: 'Pro',
    monthlyPrice: 29,
    yearlyPrice: 290,
    features: [
      '500 prompts per day',
      '10 projects',
      '2M tokens/month',
      'Priority support',
      'Priority queue'
    ],
    priceIds: {
      monthly: import.meta.env.VITE_STRIPE_PRICE_PRO_MONTHLY || '',
      yearly: import.meta.env.VITE_STRIPE_PRICE_PRO_YEARLY || ''
    }
  },
  enterprise: {
    name: 'Enterprise',
    monthlyPrice: 99,
    yearlyPrice: 990,
    features: [
      'Unlimited prompts',
      'Unlimited projects',
      '10M tokens/month',
      'Priority support + Discord',
      'Advanced analytics',
      'Early access features'
    ],
    priceIds: {
      monthly: import.meta.env.VITE_STRIPE_PRICE_ENTERPRISE_MONTHLY || '',
      yearly: import.meta.env.VITE_STRIPE_PRICE_ENTERPRISE_YEARLY || ''
    }
  }
};

export default function SubscriptionModal({
  isOpen,
  onClose,
  currentTier = 'free'
}: SubscriptionModalProps) {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleUpgrade = async (tier: string) => {
    const tierInfo = TIERS[tier];
    const priceId = billingCycle === 'monthly' ? tierInfo.priceIds.monthly : tierInfo.priceIds.yearly;

    if (!priceId) {
      setError('Price configuration missing. Please contact support.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/billing/create-checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          price_id: priceId,
          success_url: `${window.location.origin}/settings?checkout=success`,
          cancel_url: `${window.location.origin}/settings?checkout=canceled`
        })
      });

      if (!response.ok) {
        throw new Error('Failed to create checkout session');
      }

      const data = await response.json();
      // Redirect to Stripe checkout
      window.location.href = data.url;
    } catch (err) {
      setError('Failed to start checkout. Please try again.');
      setIsLoading(false);
    }
  };

  return (
    <div className="subscription-modal-overlay" onClick={onClose}>
      <div className="subscription-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Choose Your Plan</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="billing-toggle">
          <button
            className={billingCycle === 'monthly' ? 'active' : ''}
            onClick={() => setBillingCycle('monthly')}
          >
            Monthly
          </button>
          <button
            className={billingCycle === 'yearly' ? 'active' : ''}
            onClick={() => setBillingCycle('yearly')}
          >
            Yearly
            <span className="save-badge">Save up to $198</span>
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}

        <div className="tiers-grid">
          {Object.entries(TIERS).map(([key, tier]) => {
            const isCurrent = key === currentTier;
            const price = billingCycle === 'monthly' ? tier.monthlyPrice : tier.yearlyPrice;
            const savings = billingCycle === 'yearly' ? (tier.monthlyPrice * 12 - tier.yearlyPrice) : 0;

            return (
              <div key={key} className={`tier-card ${isCurrent ? 'current' : ''}`}>
                <h3>{tier.name}</h3>
                <div className="price">
                  <span className="amount">${price}</span>
                  {price > 0 && <span className="period">/{billingCycle === 'monthly' ? 'mo' : 'yr'}</span>}
                </div>
                {savings > 0 && <div className="savings">Save ${savings}</div>}

                <ul className="features">
                  {tier.features.map((feature, i) => (
                    <li key={i}>{feature}</li>
                  ))}
                </ul>

                {isCurrent ? (
                  <button className="tier-btn current" disabled>Current Plan</button>
                ) : key === 'free' ? (
                  <button className="tier-btn" disabled>Free Forever</button>
                ) : (
                  <button
                    className="tier-btn upgrade"
                    onClick={() => handleUpgrade(key)}
                    disabled={isLoading}
                  >
                    {isLoading ? 'Loading...' : 'Upgrade'}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
