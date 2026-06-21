import React, { useState, useEffect, useCallback } from 'react';
import { Leaf, LogOut, LayoutDashboard, MessageSquareText, FileCheck } from 'lucide-react';
import { authService } from './firebase';
import Dashboard from './pages/Dashboard';
import EcoCoach from './pages/EcoCoach';
import ReceiptUpload from './pages/ReceiptUpload';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [authMode, setAuthMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    const unsubscribe = authService.onAuthStateChanged((currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const handleEmailAuth = useCallback(async (e) => {
    e.preventDefault();
    setAuthError('');
    if (!email || !password) {
      setAuthError('Please fill in all fields.');
      return;
    }

    try {
      if (authMode === 'login') {
        await authService.signInWithEmail(email, password);
      } else {
        await authService.signUpWithEmail(email, password);
      }
    } catch (err) {
      setAuthError(err.message || 'Authentication failed.');
    }
  }, [email, password, authMode]);

  const handleGoogleAuth = useCallback(async () => {
    setAuthError('');
    try {
      await authService.signInWithGoogle();
    } catch (err) {
      setAuthError(err.message || 'Google Sign-in failed.');
    }
  }, []);

  const handleLogout = useCallback(async () => {
    await authService.signOut();
    setActiveTab('dashboard');
  }, []);

  const handleTabChange = useCallback((tab) => {
    setActiveTab(tab);
  }, []);

  if (loading) {
    return (
      <div 
        role="progressbar" 
        aria-label="Loading EcoSphere AI"
        style={{
          display: 'flex', 
          height: '100vh', 
          width: '100vw', 
          alignItems: 'center', 
          justifyContent: 'center',
          background: '#0b0f17',
          color: '#10b981'
        }}
      >
        <Leaf className="animate-spin-slow" size={48} aria-hidden="true" />
      </div>
    );
  }

  // --- UNAUTHENTICATED LOGIN VIEW ---
  if (!user) {
    return (
      <div style={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px'
      }}>
        <div className="glass-panel glass-card-glow" style={{
          width: '100%',
          maxWidth: '420px',
          padding: '40px 32px',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px'
        }}>
          <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '16px',
              background: 'rgba(16, 185, 129, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#34d399',
              marginBottom: '12px'
            }}>
              <Leaf size={32} aria-hidden="true" />
            </div>
            <h1 style={{ fontSize: '1.8rem', fontWeight: '800' }}>EcoSphere AI</h1>
            <p style={{ color: '#9ca3af', fontSize: '0.9rem' }}>
              Track & reduce your Carbon Footprint with AI
            </p>
          </div>

          {authError && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444',
              padding: '12px',
              borderRadius: '8px',
              fontSize: '0.85rem',
              textAlign: 'center'
            }} role="alert" aria-live="assertive">
              {authError}
            </div>
          )}

          <form onSubmit={handleEmailAuth} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label htmlFor="email-input" style={{ fontSize: '0.85rem', color: '#9ca3af', fontWeight: '500' }}>Email Address</label>
              <input 
                id="email-input"
                type="email" 
                className="input-field" 
                placeholder="you@domain.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label htmlFor="password-input" style={{ fontSize: '0.85rem', color: '#9ca3af', fontWeight: '500' }}>Password</label>
              <input 
                id="password-input"
                type="password" 
                className="input-field" 
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '8px' }}>
              {authMode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <div style={{ position: 'relative', textAlign: 'center', margin: '8px 0' }}>
            <hr style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.08)' }} />
            <span style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              background: '#0d131f',
              padding: '0 12px',
              fontSize: '0.75rem',
              color: '#6b7280'
            }}>OR</span>
          </div>

          <button onClick={handleGoogleAuth} className="btn-secondary" style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px'
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
              <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v3.92h6.69c-.29 1.5-.1.88-1.5 2.11v2.53h2.42c1.42-1.3 2.23-3.2 2.23-5.49z"/>
              <path fill="#34A853" d="M12 24c3.24 0 5.97-1.08 7.96-2.91l-2.42-2.53c-.78.52-1.8.83-2.92.83-3.22 0-5.95-2.18-6.93-5.1H5.16v2.62C7.14 20.89 9.38 24 12 24z"/>
              <path fill="#FBBC05" d="M5.07 14.29c-.25-.76-.39-1.57-.39-2.41s.14-1.65.39-2.41V6.85H5.16a11.96 11.96 0 000 9.87l-.09-.25z"/>
              <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.43-3.43C17.96 1.07 15.24 0 12 0 9.38 0 7.14 3.11 5.16 7.12l2.42 2.53c.98-2.92 3.71-5.1 6.93-5.1z"/>
            </svg>
            Continue with Google
          </button>

          {authService.isMock && (
            <div style={{
              fontSize: '0.8rem',
              color: '#34d399',
              textAlign: 'center',
              background: 'rgba(52, 211, 153, 0.05)',
              padding: '8px',
              borderRadius: '6px',
              border: '1px dashed rgba(52, 211, 153, 0.2)'
            }} role="note">
              💡 <strong>Local Mock Mode Enabled</strong>. Enter any credentials to log in instantly!
            </div>
          )}

          <div style={{ textAlign: 'center', fontSize: '0.85rem', color: '#9ca3af', marginTop: '8px' }}>
            {authMode === 'login' ? (
              <>
                New to EcoSphere?{' '}
                <button
                  type="button"
                  onClick={() => setAuthMode('signup')}
                  style={{
                    color: '#34d399',
                    cursor: 'pointer',
                    fontWeight: '600',
                    background: 'none',
                    border: 'none',
                    fontSize: 'inherit',
                    fontFamily: 'inherit',
                    padding: 0
                  }}
                >
                  Create an account
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => setAuthMode('login')}
                  style={{
                    color: '#34d399',
                    cursor: 'pointer',
                    fontWeight: '600',
                    background: 'none',
                    border: 'none',
                    fontSize: 'inherit',
                    fontFamily: 'inherit',
                    padding: 0
                  }}
                >
                  Sign In
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  // --- MAIN APPLICATION VIEW ---
  return (
    <div className="app-container">
      {/* Skip to Content Link for keyboard users */}
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>

      {/* Sidebar Navigation */}
      <aside className="sidebar" aria-label="Application Navigation">
        <div className="logo">
          <Leaf className="logo-icon" size={28} aria-hidden="true" />
          <span className="logo-text">EcoSphere AI</span>
        </div>

        <nav style={{ flex: 1 }} aria-label="Main Application Menu">
          <ul className="nav-menu">
            <li>
              <button 
                onClick={() => handleTabChange('dashboard')} 
                className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
                style={{ width: '100%', border: 'none', background: 'none', textAlign: 'left' }}
                aria-current={activeTab === 'dashboard' ? 'page' : undefined}
              >
                <LayoutDashboard size={20} aria-hidden="true" />
                <span className="nav-label">Dashboard</span>
              </button>
            </li>
            <li>
              <button 
                onClick={() => handleTabChange('coach')} 
                className={`nav-item ${activeTab === 'coach' ? 'active' : ''}`}
                style={{ width: '100%', border: 'none', background: 'none', textAlign: 'left' }}
                aria-current={activeTab === 'coach' ? 'page' : undefined}
              >
                <MessageSquareText size={20} aria-hidden="true" />
                <span className="nav-label">Eco-Coach</span>
              </button>
            </li>
            <li>
              <button 
                onClick={() => handleTabChange('receipt')} 
                className={`nav-item ${activeTab === 'receipt' ? 'active' : ''}`}
                style={{ width: '100%', border: 'none', background: 'none', textAlign: 'left' }}
                aria-current={activeTab === 'receipt' ? 'page' : undefined}
              >
                <FileCheck size={20} aria-hidden="true" />
                <span className="nav-label">Receipt Scanner</span>
              </button>
            </li>
          </ul>
        </nav>

        {/* Sidebar Footer User Profile */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="avatar-badge" style={{ justifyContent: 'flex-start', width: '100%' }}>
            <div className="avatar-circle" aria-hidden="true">
              {user.displayName ? user.displayName[0].toUpperCase() : 'U'}
            </div>
            <div className="nav-label" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <div style={{ fontWeight: '600', fontSize: '0.85rem' }}>{user.displayName || 'Warrior'}</div>
              <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{user.email}</div>
            </div>
          </div>

          <button onClick={handleLogout} className="btn-secondary" style={{
            width: '100%',
            padding: '10px',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}>
            <LogOut size={16} aria-hidden="true" />
            <span className="nav-label">Log Out</span>
          </button>
        </div>
      </aside>

      {/* Main Page Panel Router */}
      <main id="main-content" className="main-content" role="main">
        {activeTab === 'dashboard' && <Dashboard user={user} />}
        {activeTab === 'coach' && <EcoCoach user={user} />}
        {activeTab === 'receipt' && <ReceiptUpload user={user} />}
      </main>
    </div>
  );
}

export default App;
