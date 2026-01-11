import React from 'react';
import { useAuthStore } from '../../store/authStore';
import { FaGithub } from 'react-icons/fa';
import './GoogleSignInButton.css'; // Re-use same styles for consistency

interface GitHubSignInButtonProps {
  text?: string;
  className?: string;
}

/**
 * GitHub Sign-In Button
 */
export const GitHubSignInButton: React.FC<GitHubSignInButtonProps> = ({ 
  text = 'Sign in with GitHub',
  className = ''
}) => {
  const { loginWithGitHub, isLoading } = useAuthStore();

  return (
    <button
      className={`google-signin-button github-signin-button ${className}`}
      onClick={loginWithGitHub}
      disabled={isLoading}
      style={{ backgroundColor: '#24292e', color: 'white', border: 'none' }}
    >
      <FaGithub size={20} style={{ marginRight: '12px' }} />
      <span className="google-button-text">{text}</span>
    </button>
  );
};
