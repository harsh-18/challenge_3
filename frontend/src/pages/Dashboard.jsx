import React, { useState, useEffect, useCallback, memo } from 'react';
import { Leaf, Send, Car, Zap, UtensilsCrossed, Trash2, Recycle, ArrowUpRight, ShieldAlert, Sparkles, TrendingDown } from 'lucide-react';
import { authService } from '../firebase';
import { API_PATHS, CATEGORY_CONFIG } from '../constants';

/**
 * Memoized log list item component to prevent unnecessary re-renders
 * when the parent re-renders (e.g., on new input text changes).
 */
const LogListItem = memo(function LogListItem({ log, getCategoryIcon }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 24px',
      borderBottom: '1px solid var(--border-color)',
      transition: 'var(--transition-smooth)'
    }} className="log-list-item">
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{
          width: '40px',
          height: '40px',
          borderRadius: '10px',
          background: 'rgba(255,255,255,0.03)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid var(--border-color)'
        }} aria-hidden="true">
          {getCategoryIcon(log.category)}
        </div>
        <div>
          <div style={{ fontWeight: '600', fontSize: '0.95rem' }}>{log.description}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {new Date(log.timestamp * 1000).toLocaleString(undefined, {
              month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            })}
          </div>
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontWeight: '800', fontSize: '1.05rem', color: '#fff' }}>
          +{log.carbon_kg} kg
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
          CO₂e
        </div>
      </div>
    </div>
  );
});

/**
 * Category progress bar component.
 */
const CategoryBar = memo(function CategoryBar({ emoji, label, value, percentage, color, formatCo2 }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
        <span>{emoji} {label}</span>
        <strong>{formatCo2(value)}</strong>
      </div>
      <div className="category-bar-track" role="progressbar" aria-valuenow={Math.round(percentage)} aria-valuemin={0} aria-valuemax={100} aria-label={`${label} carbon footprint`}>
        <div className="category-bar-fill" style={{ width: `${percentage}%`, background: color }}></div>
      </div>
    </div>
  );
});

function Dashboard({ user }) {
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState({ categories: { transit: 0, energy: 0, food: 0, waste: 0 }, total_carbon_kg: 0 });
  const [inputText, setInputText] = useState('');
  const [tips, setTips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [logging, setLogging] = useState(false);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    try {
      const token = await authService.getAuthToken();
      const headers = { 'Authorization': `Bearer ${token}` };
      
      const [logsRes, tipsRes] = await Promise.all([
        fetch(API_PATHS.LOGS, { headers }),
        fetch(API_PATHS.TIPS, { headers })
      ]);
      
      if (logsRes.ok) {
        const data = await logsRes.json();
        setLogs(data.logs || []);
        setSummary(data.summary || { categories: { transit: 0, energy: 0, food: 0, waste: 0 }, total_carbon_kg: 0 });
      } else {
        throw new Error('Failed to load carbon logs.');
      }
      
      if (tipsRes.ok) {
        const data = await tipsRes.json();
        setTips(data.tips || []);
      }
    } catch (err) {
      console.error(err);
      setError('Could not establish connection to the backend service. Check if backend is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleNLSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    setLogging(true);
    setError('');

    try {
      const token = await authService.getAuthToken();
      const res = await fetch(API_PATHS.LOGS_TEXT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text: inputText })
      });

      if (!res.ok) {
        throw new Error('Failed to parse and save activity.');
      }

      setInputText('');
      await fetchData();
    } catch (err) {
      setError(err.message || 'Logging activity failed.');
    } finally {
      setLogging(false);
    }
  }, [inputText, fetchData]);

  const getCategoryIcon = useCallback((category) => {
    switch (category.toLowerCase()) {
      case 'transit': return <Car size={18} style={{ color: 'var(--color-transit)' }} aria-hidden="true" />;
      case 'energy': return <Zap size={18} style={{ color: 'var(--color-energy)' }} aria-hidden="true" />;
      case 'food': return <UtensilsCrossed size={18} style={{ color: 'var(--color-food)' }} aria-hidden="true" />;
      case 'waste': return <Recycle size={18} style={{ color: 'var(--color-waste)' }} aria-hidden="true" />;
      default: return <Leaf size={18} style={{ color: 'var(--accent-emerald)' }} aria-hidden="true" />;
    }
  }, []);

  const formatCo2 = useCallback((kg) => {
    if (kg >= 1000) return `${(kg / 1000).toFixed(1)} tonnes`;
    return `${kg.toFixed(1)} kg`;
  }, []);

  // Calculate percentages
  const total = summary.total_carbon_kg || 1;
  const transitVal = summary.categories.transit || 0;
  const energyVal = summary.categories.energy || 0;
  const foodVal = summary.categories.food || 0;
  const wasteVal = summary.categories.waste || 0;

  const transitPct = (transitVal / total) * 100;
  const energyPct = (energyVal / total) * 100;
  const foodPct = (foodVal / total) * 100;
  const wastePct = (wasteVal / total) * 100;

  if (loading) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center' }} role="progressbar" aria-label="Loading dashboard data">
        <Leaf className="animate-spin-slow" size={36} style={{ color: 'var(--accent-emerald)' }} aria-hidden="true" />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', width: '100%' }}>
      {/* Header Bar */}
      <div className="user-profile-header">
        <div className="user-greeting">
          <h1>Welcome back, Eco-Warrior! 🌿</h1>
          <p>Let's make today cleaner than yesterday.</p>
        </div>
        <div className="avatar-badge">
          <span style={{ fontSize: '0.85rem', fontWeight: '500', color: 'var(--accent-mint)' }}>
            Level 3 Green Guard
          </span>
        </div>
      </div>

      {error && (
        <div className="glass-panel" role="alert" aria-live="assertive" style={{
          padding: '16px',
          background: 'rgba(239, 68, 68, 0.08)',
          borderColor: 'rgba(239, 68, 68, 0.25)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#f87171'
        }}>
          <ShieldAlert size={20} aria-hidden="true" />
          <span style={{ fontSize: '0.9rem' }}>{error}</span>
        </div>
      )}

      {/* Top Level Summary cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '24px'
      }}>
        {/* Total Carbon Card */}
        <div className="glass-panel glass-card-glow" style={{ padding: '28px', display: 'flex', gap: '20px', alignItems: 'center' }}>
          <div style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            border: '4px solid rgba(16, 185, 129, 0.1)',
            borderTopColor: 'var(--accent-emerald)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--shadow-glow)'
          }} aria-hidden="true">
            <TrendingDown size={20} style={{ color: 'var(--accent-mint)' }} />
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: '500' }}>TOTAL CARBON LOGGED</div>
            <div style={{ fontSize: '2rem', fontWeight: '900', color: '#fff', margin: '4px 0' }} aria-live="polite">
              {formatCo2(summary.total_carbon_kg)}
            </div>
            <div style={{ color: 'var(--accent-mint)', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={12} aria-hidden="true" />
              Target budget: 100 kg CO2e / week
            </div>
          </div>
        </div>

        {/* Dynamic Category Summary */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: '500', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Footprint by Category
          </h2>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }} aria-live="polite">
            <CategoryBar emoji="🚗" label="Travel" value={transitVal} percentage={transitPct} color="var(--color-transit)" formatCo2={formatCo2} />
            <CategoryBar emoji="⚡" label="Energy" value={energyVal} percentage={energyPct} color="var(--color-energy)" formatCo2={formatCo2} />
            <CategoryBar emoji="🥗" label="Food" value={foodVal} percentage={foodPct} color="var(--color-food)" formatCo2={formatCo2} />
            <CategoryBar emoji="♻️" label="Waste" value={wasteVal} percentage={wastePct} color="var(--color-waste)" formatCo2={formatCo2} />
          </div>
        </div>
      </div>

      {/* Main Grid: Left (NL Logger & Logs), Right (AI tips RAG) */}
      <div className="dashboard-grid">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          
          {/* Natural Language Ingest Console */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={18} style={{ color: 'var(--accent-mint)' }} aria-hidden="true" />
              Log Activity in Plain English
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '20px' }}>
              "Ate a beef steak and drove 35 km in a petrol car today."
            </p>

            <form onSubmit={handleNLSubmit} style={{ display: 'flex', gap: '12px' }}>
              <label htmlFor="nl-activity-input" className="sr-only">Log Activity in Plain English</label>
              <input
                id="nl-activity-input"
                type="text"
                className="input-field"
                placeholder="What did you do today? e.g., flew economy from Delhi to Mumbai..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                disabled={logging}
              />
              <button 
                type="submit" 
                className="btn-primary" 
                disabled={logging || !inputText.trim()} 
                style={{ whiteSpace: 'nowrap' }}
                aria-label="Submit activity log"
              >
                {logging ? 'Processing...' : 'Log'}
                <Send size={16} aria-hidden="true" />
              </button>
            </form>
          </div>

          {/* Recent Logs List */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="card-header">
              <h2 style={{ fontSize: '1.1rem' }}>Activity History</h2>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }} aria-live="polite">
                {logs.length} logs recorded
              </span>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', maxHeight: '420px', overflowY: 'auto' }} role="list" aria-label="Carbon activity log history">
              {logs.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                  No activities logged yet. Type something in the input box above or scan a receipt to start!
                </div>
              ) : (
                logs.map((log, index) => (
                  <div role="listitem" key={log.id || index}>
                    <LogListItem log={log} getCategoryIcon={getCategoryIcon} />
                  </div>
                ))
              )}
            </div>
          </div>
          
        </div>

        {/* Right Column: AI Coach Recommendations */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h2 style={{ fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Leaf size={18} style={{ color: 'var(--accent-emerald)' }} aria-hidden="true" />
              Eco Recommendations
            </h2>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} aria-live="polite">
              {tips.map((tip, index) => (
                <div key={index} className="glass-panel" style={{
                  padding: '16px',
                  background: 'rgba(255, 255, 255, 0.02)',
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start'
                }}>
                  <div style={{
                    color: 'var(--accent-mint)',
                    marginTop: '2px',
                    background: 'rgba(52, 211, 153, 0.1)',
                    padding: '4px',
                    borderRadius: '50%',
                    display: 'flex'
                  }} aria-hidden="true">
                    <ArrowUpRight size={14} />
                  </div>
                  <span style={{ fontSize: '0.85rem', lineHeight: '1.4', color: 'var(--text-primary)' }}>
                    {tip}
                  </span>
                </div>
              ))}
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
