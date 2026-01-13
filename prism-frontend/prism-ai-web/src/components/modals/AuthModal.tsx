import { useState } from 'react';
import { useAuthStore } from '../../store/authStore';
import { RiShip2Fill } from 'react-icons/ri';
import { AiOutlineLoading3Quarters } from 'react-icons/ai';
import { GoogleSignInButton } from '../auth/GoogleSignInButton';
import { GitHubSignInButton } from '../auth/GitHubSignInButton';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

import './AuthModal.css';

export default function AuthModal({ isOpen, onClose, onSuccess }: AuthModalProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const { login, register, isLoading } = useAuthStore();

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLogin) {
      await login(email, password);
    } else {
      await register(email, password, name);
    }
    onSuccess();
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
           <RiShip2Fill className="modal-icon" size={32} color="var(--primary-color)" />
           <h2>{isLogin ? 'Welcome Back' : 'Create Account'}</h2>
           <p className="modal-subtitle">
             {isLogin ? 'Sign in to continue building' : 'Join ShipS* to start shipping'}
           </p>
        </div>

        <div className="auth-divider">
          <span>Or continue with</span>
        </div>

        <div className="oauth-buttons" style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
          <GoogleSignInButton text={isLogin ? "Sign in with Google" : "Sign up with Google"} />
          <GitHubSignInButton text={isLogin ? "Sign in with GitHub" : "Sign up with GitHub"} />
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {!isLogin && (
            <input
              type="text"
              placeholder="Name"
              className="auth-input"
              value={name}
              onChange={e => setName(e.target.value)}
              required
            />
          )}
          <input
            type="email"
            placeholder="Email"
            className="auth-input"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            className="auth-input"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
          />
          
          <button type="submit" className="auth-submit-btn" disabled={isLoading}>
            {isLoading ? <AiOutlineLoading3Quarters className="spin" /> : (isLogin ? 'Sign In' : 'Sign Up')}
          </button>
        </form>

        <div className="auth-footer">
          <span>{isLogin ? "Don't have an account?" : "Already have an account?"}</span>
          <button className="text-link-btn" onClick={() => setIsLogin(!isLogin)}>
            {isLogin ? 'Sign Up' : 'Sign In'}
          </button>
        </div>
      </div>
    </div>
  );
}
