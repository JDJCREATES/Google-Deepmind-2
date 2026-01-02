import React from 'react';
import { useAuthStore } from '../../../store/authStore';
import { SettingsCarousel, CarouselSlide } from '../../ui/SettingsCarousel';
import '../Settings.css';

const AccountSettings: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuthStore();

  if (!isAuthenticated || !user) {
    return (
      <div className="settings-page">
        <div className="settings-section">
          <p style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
            Please log in to view account settings.
          </p>
        </div>
      </div>
    );
  }

  const getUserInitials = (name: string) => {
    return name
      .split(' ')
      .map(word => word[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const isValidAvatarUrl = (url: string | undefined): boolean => {
    if (!url) return false;
    try {
      const parsed = new URL(url);
      // Only allow https URLs from exact known safe domains
      const safeDomains = [
        'api.dicebear.com',
        'avatars.githubusercontent.com',
        'secure.gravatar.com',
        'www.gravatar.com'
      ];
      return parsed.protocol === 'https:' && safeDomains.includes(parsed.hostname);
    } catch {
      return false;
    }
  };

  return (
    <SettingsCarousel showPagination={false}>
      <CarouselSlide>
        <div className="settings-page">
          {/* User Info Card */}
          <div className="user-info-card">
            <div className="user-avatar">
              {isValidAvatarUrl(user.avatarUrl) ? (
                <img src={user.avatarUrl} alt={user.name} style={{ width: '100%', height: '100%', borderRadius: '8px' }} />
              ) : (
                getUserInitials(user.name)
              )}
            </div>
            <div className="user-details">
              <div className="user-name">{user.name}</div>
              <div className="user-email">{user.email}</div>
            </div>
          </div>

          {/* Account Information */}
          <div className="settings-section">
            <h3 className="settings-section-title">Account Information</h3>
            
            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">Username</div>
                <div className="settings-label-desc">Your display name</div>
              </div>
              <div className="settings-control">
                <input
                  type="text"
                  className="settings-input"
                  value={user.name}
                  disabled
                />
              </div>
            </div>

            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">Email</div>
                <div className="settings-label-desc">Your email address</div>
              </div>
              <div className="settings-control">
                <input
                  type="email"
                  className="settings-input"
                  value={user.email}
                  disabled
                />
              </div>
            </div>

            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">User ID</div>
                <div className="settings-label-desc">Unique identifier</div>
              </div>
              <div className="settings-control">
                <input
                  type="text"
                  className="settings-input"
                  value={user.id}
                  disabled
                />
              </div>
            </div>
          </div>

          {/* Account Actions */}
          <div className="settings-section">
            <h3 className="settings-section-title">Account Actions</h3>
            
            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">Sign Out</div>
                <div className="settings-label-desc">Sign out of your account</div>
              </div>
              <div className="settings-control">
                <button 
                  className="settings-button settings-button-secondary"
                  onClick={logout}
                >
                  Sign Out
                </button>
              </div>
            </div>
          </div>
        </div>
      </CarouselSlide>
    </SettingsCarousel>
  );
};

export default AccountSettings;
