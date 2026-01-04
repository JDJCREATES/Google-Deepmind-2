/**
 * Subscription status display for account settings.
 *
 * Shows current tier, usage stats, and upgrade/manage buttons.
 */

import React, { useEffect, useState } from 'react';
import './SubscriptionStatus.css';

interface SubscriptionStatusProps {
  onUpgradeClick: () => void;
}

interface UserData {
  user: {
    tier: string;
    subscription_status: string;
  };
  limits: {
    prompts_per_day: number;
    tokens_per_month: number;
  };
  usage: {
    prompts_used_today: number;
    tokens_used_month: number;
  };
}

export default function SubscriptionStatus({ onUpgradeClick }: SubscriptionStatusProps) {
  const [data, setData] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUserData();
  }, []);

  const fetchUserData = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/auth/user`, {
        credentials: 'include'
      });
      const result = await response.json();
      if (result.authenticated) {
        setData(result);
      }
    } catch (err) {
      console.error('Failed to fetch user data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleManageBilling = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/billing/portal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          return_url: `${window.location.origin}/settings`
        })
      });

      if (response.ok) {
        const result = await response.json();
        window.location.href = result.url;
      }
    } catch (err) {
      console.error('Failed to open billing portal:', err);
    }
  };

  if (loading) {
    return <div className="subscription-status loading">Loading...</div>;
  }

  if (!data) {
    return <div className="subscription-status">Not authenticated</div>;
  }

  const { user, limits, usage } = data;
  const promptsPercent = limits.prompts_per_day === -1 ? 0 : (usage.prompts_used_today / limits.prompts_per_day) * 100;
  const tokensPercent = (usage.tokens_used_month / limits.tokens_per_month) * 100;

  return (
    <div className="subscription-status">
      <div className="tier-header">
        <div>
          <div className="tier-name">{user.tier.charAt(0).toUpperCase() + user.tier.slice(1)} Plan</div>
          <div className="tier-status">{user.subscription_status}</div>
        </div>
        <div className="tier-badge">{user.tier}</div>
      </div>

      <div className="usage-section">
        <h4>Usage This Period</h4>

        <div className="usage-item">
          <div className="usage-label">
            <span>Prompts</span>
            <span className="usage-numbers">
              {usage.prompts_used_today} / {limits.prompts_per_day === -1 ? 'Unlimited' : limits.prompts_per_day}
            </span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${Math.min(promptsPercent, 100)}%` }} />
          </div>
        </div>

        <div className="usage-item">
          <div className="usage-label">
            <span>Tokens</span>
            <span className="usage-numbers">
              {(usage.tokens_used_month / 1000).toFixed(0)}k / {(limits.tokens_per_month / 1000).toFixed(0)}k
            </span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${Math.min(tokensPercent, 100)}%` }} />
          </div>
        </div>
      </div>

      <div className="actions">
        {user.tier !== 'enterprise' && (
          <button className="btn-upgrade" onClick={onUpgradeClick}>
            Upgrade Plan
          </button>
        )}
        {user.tier !== 'free' && (
          <button className="btn-manage" onClick={handleManageBilling}>
            Manage Billing
          </button>
        )}
      </div>
    </div>
  );
}
