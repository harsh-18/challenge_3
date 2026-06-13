import React, { useState, useEffect } from 'react';
import { Leaf, Send, Car, Zap, UtensilsCrossed, Trash2, ArrowUpRight, ShieldAlert, Sparkles, TrendingDown } from 'lucide-react';
import { authService } from '../firebase';

function Dashboard({ user }) {
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState({ categories: { transit: 0, energy: 0, food: 0, waste: 0 }, total_carbon_kg: 0 });
  const [inputText, setInputText] = useState('');
  const [tips, setTips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [logging, setLogging] = useState(false);
  const [error, setError] = useState('');

  // Fetch carbon logs and tips on load
  const fetchData = async () => {
    try {
      const token = await authService.getAuthToken();
      const headers = { 'Authorization': `Bearer ${token}` };
      
      // 1. Fetch Logs
      const logsRes = await fetch('/api/logs', { headers });
      if (logsRes.ok) {
        const data = await logsRes.json();
        setLogs(data.logs || []);
        setSummary(data.summary || { categories: { transit: 0, energy: 0, food: 0, waste: 0 }, total_carbon_kg: 0 });
      } else {
        throw new Error('Failed to load carbon logs.');
      }
      
      // 2. Fetch Tips
      const tipsRes = await fetch('/api/tips', { headers });
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
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleNLSubmit = async (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    setLogging(true);
    setError('');

    try {
      const token = await authService.getAuthToken();
      const res = await fetch('/api/logs/text', {
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

      const result = await res.json();
      setInputText('');
      
      // Refresh logs
      await fetchData();
    } catch (err) {
      setError(err.message || 'Logging activity failed.');
    } finally {
      setLogging(false);
    }
  };

  const getCategoryIcon = (category) => {
    switch (category.toLowerCase()) {
      case 'transit': return <Car size={18} style={{ color: 'var(--color-transit)' }} />;
      case 'energy': return <Zap size={18} style={{ color: 'var(--color-energy)' }} />;
      case 'food': return <UtensilsCrossed size={18} style={{ color: 'var(--color-food)' }} />;
      case 'waste': return <Trash2 size={18} style={{ color: 'var(--color-waste)' }} />;
      default: return <Leaf size={18} style={{ color: 'var(--accent-emerald)' }} />;
    }
  };

  // SVG Donut Chart logic
  const total = summary.total_carbon_kg || 1;
  const transitVal = summary.categories.transit || 0;
  const energyVal = summary.categories.energy || 0;
  const foodVal = summary.categories.food || 0;
  const wasteVal = summary.categories.waste || 0;

  // Calculate percentages
  const transitPct = (transitVal / total) * 100;
  const energyPct = (energyVal / total) * 100;
  const foodPct = (foodVal / total) * 100;
  const wastePct = (wasteVal / total) * 100;

  // SVG calculations for a simple stacked percentage bar
  const formatCo2 = (kg) => {
    if (kg >= 1000) return `${(kg / 1000).toFixed(1)} tonnes`;
    return `${kg.toFixed(1)} kg`;
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <Leaf className="animate-spin-slow" size={36} style={{ color: 'var(--accent-emerald)' }} />
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
        <div className="glass-panel" style={{
          padding: '16px',
          background: 'rgba(239, 68, 68, 0.08)',
          borderColor: 'rgba(239, 68, 68, 0.25)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#f87171'
        }}>
          <ShieldAlert size={20} />
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
          }}>
            <TrendingDown size={20} style={{ color: 'var(--accent-mint)' }} />
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: '500' }}>TOTAL CARBON LOGGED</div>
            <div style={{ fontSize: '2rem', fontWeight: '900', color: '#fff', margin: '4px 0' }}>
              {formatCo2(summary.total_carbon_kg)}
            </div>
            <div style={{ color: 'var(--accent-mint)', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={12} />
              Target budget: 100 kg CO2e / week
            </div>
          </div>
        </div>

        {/* Dynamic Category Summary */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyGap: '8px' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: '500', marginBottom: '16px' }}>
            FOOTPRINT BY CATEGORY
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Transit */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                <span>🚗 Travel</span>
                <strong>{formatCo2(transitVal)}</strong>
              </div>
              <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${transitPct}%`, background: 'var(--color-transit)', borderRadius: '3px' }}></div>
              </div>
            </div>
            {/* Energy */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                <span>⚡ Energy</span>
                <strong>{formatCo2(energyVal)}</strong>
              </div>
              <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${energyPct}%`, background: 'var(--color-energy)', borderRadius: '3px' }}></div>
              </div>
            </div>
            {/* Food */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                <span>🥗 Food</span>
                <strong>{formatCo2(foodVal)}</strong>
              </div>
              <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${foodPct}%`, background: 'var(--color-food)', borderRadius: '3px' }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Left (NL Logger & Logs), Right (AI tips RAG) */}
      <div className="dashboard-grid">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          
          {/* Natural Language Ingest Console */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1.15rem', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={18} style={{ color: 'var(--accent-mint)' }} />
              Log Activity in Plain English
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '20px' }}>
              "Ate a beef steak and drove 35 km in a petrol car today."
            </p>

            <form onSubmit={handleNLSubmit} style={{ display: 'flex', gap: '12px' }}>
              <input
                type="text"
                className="input-field"
                placeholder="What did you do today? e.g., flew economy from Delhi to Mumbai..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                disabled={logging}
              />
              <button type="submit" className="btn-primary" disabled={logging || !inputText.trim()} style={{ whiteSpace: 'nowrap' }}>
                {logging ? 'Processing...' : 'Log'}
                <Send size={16} />
              </button>
            </form>
          </div>

          {/* Recent Logs List */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="card-header">
              <h3 style={{ fontSize: '1.1rem' }}>Activity History</h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                {logs.length} logs recorded
              </span>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', maxHeight: '420px', overflowY: 'auto' }}>
              {logs.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                  No activities logged yet. Type something in the input box above or scan a receipt to start!
                </div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} style={{
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
                      }}>
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
                ))
              )}
            </div>
          </div>
          
        </div>

        {/* Right Column: AI Coach Recommendations */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Leaf size={18} style={{ color: 'var(--accent-emerald)' }} />
              Eco Recommendations
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
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
                  }}>
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
