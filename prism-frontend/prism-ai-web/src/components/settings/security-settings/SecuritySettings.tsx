import React from 'react';
import * as Ons from 'react-onsenui';
import { useAuthStore } from '../../../store/authStore';
import { SettingsCarousel, CarouselSlide } from '../../ui/SettingsCarousel';
import '../Settings.css';

const SecuritySettings: React.FC = () => {
  const { user, isAuthenticated } = useAuthStore();

  if (!isAuthenticated || !user) {
    return (
      <SettingsCarousel showPagination={false}>
        <CarouselSlide>
          <div className="settings-page">
            <div className="settings-section">
              <p style={{ textAlign: 'center', color: 'var(--text-secondary)', paddingTop: '40px' }}>
                Please log in to access security settings
              </p>
            </div>
          </div>
        </CarouselSlide>
      </SettingsCarousel>
    );
  }

  return (
    <SettingsCarousel showPagination={false}>
      <CarouselSlide>
        <div className="settings-page">
          {/* Password */}
          <div className="settings-section">
            <h3 className="settings-section-title">Password</h3>
            
            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">Change Password</div>
                <div className="settings-label-desc">Update your account password</div>
              </div>
              <div className="settings-control">
                <button className="settings-button settings-button-secondary" disabled>
                  Coming Soon
                </button>
              </div>
            </div>
          </div>

          {/* Two-Factor Authentication */}
          <div className="settings-section">
            <h3 className="settings-section-title">Two-Factor Authentication</h3>
            
            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">2FA Status</div>
                <div className="settings-label-desc">Add an extra layer of security to your account</div>
              </div>
              <div className="settings-control">
                <button className="settings-button settings-button-secondary" disabled>
                  Coming Soon
                </button>
              </div>
            </div>
          </div>

          {/* Sessions */}
          <div className="settings-section">
            <h3 className="settings-section-title">Active Sessions</h3>
            
            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">Manage Sessions</div>
                <div className="settings-label-desc">View and revoke active login sessions</div>
              </div>
              <div className="settings-control">
                <button className="settings-button settings-button-secondary" disabled>
                  Coming Soon
                </button>
              </div>
            </div>
          </div>

          {/* API Keys */}
          <div className="settings-section">
            <h3 className="settings-section-title">API Access</h3>
            
            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">API Keys</div>
                <div className="settings-label-desc">Manage programmatic access to your account</div>
              </div>
              <div className="settings-control">
                <button className="settings-button settings-button-secondary" disabled>
                  Coming Soon
                </button>
              </div>
            </div>
          </div>
        </div>
      </CarouselSlide>
    </SettingsCarousel>
  );
};

export default SecuritySettings;
