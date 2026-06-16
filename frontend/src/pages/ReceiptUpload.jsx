import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Sparkles, RefreshCw, BarChart2 } from 'lucide-react';
import { authService } from '../firebase';

function ReceiptUpload({ user }) {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      validateAndSetFile(droppedFile);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    setError('');
    setResult(null);
    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (!validTypes.includes(selectedFile.type)) {
      setError('Invalid file format. Please upload a JPG, PNG, WEBP, or PDF.');
      return;
    }
    // Limit file size to 8MB
    if (selectedFile.size > 8 * 1024 * 1024) {
      setError('File is too large. Limit is 8 MB.');
      return;
    }
    setFile(selectedFile);
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!file || uploading) return;
    setUploading(true);
    setError('');
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = await authService.getAuthToken();
      const res = await fetch('/api/logs/receipt', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!res.ok) {
        throw new Error('Failed to analyze the uploaded bill/receipt.');
      }

      const data = await res.json();
      setResult(data);
      setFile(null); // Reset
    } catch (err) {
      console.error(err);
      setError(err.message || 'Error processing receipt upload.');
    } finally {
      setUploading(false);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current.click();
  };

  const getBadgeColor = (category) => {
    switch (category.toLowerCase()) {
      case 'transit': return 'rgba(59, 130, 246, 0.15)';
      case 'energy': return 'rgba(234, 179, 8, 0.15)';
      case 'food': return 'rgba(239, 68, 68, 0.15)';
      case 'waste': return 'rgba(168, 85, 247, 0.15)';
      default: return 'rgba(255, 255, 255, 0.05)';
    }
  };

  const getTextColor = (category) => {
    switch (category.toLowerCase()) {
      case 'transit': return 'var(--color-transit)';
      case 'energy': return 'var(--color-energy)';
      case 'food': return 'var(--color-food)';
      case 'waste': return 'var(--color-waste)';
      default: return 'var(--text-secondary)';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', width: '100%', maxWidth: '960px', margin: '0 auto' }}>
      
      <div className="user-greeting">
        <h1>Multimodal Receipt & Bill Scanner 📸</h1>
        <p>Upload utility bills (PDF) or grocery store receipts (JPG/PNG). Gemini Flash will perform structured OCR to calculate your carbon impact.</p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: result ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '32px'
      }}>
        
        {/* Upload panel */}
        {!result && (
          <div className="glass-panel" style={{ padding: '32px' }}>
            <form onSubmit={handleUploadSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              
              <div 
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={triggerFileInput}
                style={{
                  border: '2px dashed rgba(16, 185, 129, 0.25)',
                  borderRadius: '16px',
                  background: dragActive ? 'rgba(16, 185, 129, 0.06)' : 'rgba(255, 255, 255, 0.01)',
                  padding: '48px 24px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'var(--transition-smooth)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '16px'
                }}
                className="drop-zone"
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  style={{ display: 'none' }} 
                  onChange={handleFileChange} 
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                />
                
                <div style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  background: 'rgba(16, 185, 129, 0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-mint)'
                }}>
                  <UploadCloud size={32} />
                </div>
                
                <div>
                  <strong style={{ display: 'block', marginBottom: '4px' }}>
                    {file ? file.name : 'Drag & Drop your receipt here'}
                  </strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : 'Supports JPG, PNG, WEBP, and PDF bills (Max 8MB)'}
                  </span>
                </div>
              </div>

              {error && (
                <div style={{
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.2)',
                  color: '#f87171',
                  padding: '12px 16px',
                  borderRadius: '10px',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <AlertCircle size={18} />
                  {error}
                </div>
              )}

              <button 
                type="submit" 
                className="btn-primary" 
                disabled={!file || uploading}
                style={{ width: '100%', height: '48px' }}
              >
                {uploading ? (
                  <>
                    <RefreshCw className="animate-spin" size={18} style={{ animation: 'spin 1.5s linear infinite' }} />
                    Gemini Scanning & Calculating...
                  </>
                ) : (
                  <>
                    <Sparkles size={18} />
                    Analyze with Gemini OCR
                  </>
                )}
              </button>
            </form>
          </div>
        )}

        {/* Info panel */}
        {!result && !uploading && (
          <div className="glass-panel" style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <h3 style={{ fontSize: '1.2rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <FileText size={20} style={{ color: 'var(--accent-mint)' }} />
              How it works
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              <div>
                <strong style={{ color: '#fff', display: 'block', marginBottom: '4px' }}>1. Upload Document</strong>
                Take a photo of your food receipt or utility bill. PDFs are accepted for online statements.
              </div>
              <div>
                <strong style={{ color: '#fff', display: 'block', marginBottom: '4px' }}>2. Multimodal Structured OCR</strong>
                Gemini 1.5 Flash parses the billing details, identifying items, consumption numbers (e.g. 120 kWh), and stores.
              </div>
              <div>
                <strong style={{ color: '#fff', display: 'block', marginBottom: '4px' }}>3. Instant Carbon Calculations</strong>
                The platform matches items to emission factors, saves carbon logs to your profile, and displays the impact analysis.
              </div>
            </div>
            
            {authService.isMock && (
              <div style={{
                background: 'rgba(52, 211, 153, 0.05)',
                border: '1px dashed rgba(52, 211, 153, 0.25)',
                borderRadius: '10px',
                padding: '16px',
                fontSize: '0.82rem',
                color: 'var(--accent-mint)',
                lineHeight: '1.4'
              }}>
                💡 <strong>Mock Mode Tip:</strong> Since local mock mode is active, uploading any file will instantly generate a simulated, structured electricity bill or grocery receipt result for testing! Try it out!
              </div>
            )}
          </div>
        )}

        {/* Uploading Status View */}
        {uploading && (
          <div className="glass-panel" style={{ padding: '60px 40px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
            <RefreshCw size={48} className="animate-spin-slow" style={{ color: 'var(--accent-mint)', animation: 'spin 3s linear infinite' }} />
            <div>
              <h3 style={{ fontSize: '1.3rem', color: '#fff', marginBottom: '8px' }}>Processing Bill Statement</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Gemini is digitizing items and calculating carbon values...</p>
            </div>
            <div style={{ width: '100%', maxWidth: '300px', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: '60%', background: 'linear-gradient(90deg, var(--accent-emerald), var(--accent-cyan))', borderRadius: '2px', animation: 'pulse-glow 1s infinite alternate' }}></div>
            </div>
          </div>
        )}

        {/* Results view */}
        {result && (
          <div className="glass-panel" style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px' }}>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--accent-mint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold' }}>
                  Analysis Complete
                </span>
                <h2 style={{ fontSize: '1.5rem', color: '#fff', marginTop: '4px' }}>{result.merchant}</h2>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Date: {result.date}</span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Bill Total</span>
                <div style={{ fontSize: '1.6rem', fontWeight: '800', color: '#fff', marginTop: '2px' }}>
                  ₹{result.total_amount.toFixed(2)}
                </div>
              </div>
            </div>

            {/* Carbon summary card */}
            <div className="glass-panel glass-card-glow" style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '10px',
                  background: 'rgba(16, 185, 129, 0.1)',
                  color: 'var(--accent-mint)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <BarChart2 size={22} />
                </div>
                <div>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: '700' }}>Estimated Carbon Cost</h4>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Automatically committed to your logs</p>
                </div>
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: '900', color: 'var(--accent-mint)' }}>
                {result.estimated_total_carbon_kg} kg <span style={{ fontSize: '0.9rem', fontWeight: '400', color: 'var(--text-secondary)' }}>CO₂e</span>
              </div>
            </div>

            {/* Extracted items table */}
            <div>
              <h3 style={{ fontSize: '1.1rem', color: '#fff', marginBottom: '16px' }}>Extracted Items & Parameters</h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '12px 8px' }}>Item Name</th>
                      <th style={{ padding: '12px 8px' }}>Quantity</th>
                      <th style={{ padding: '12px 8px' }}>Price</th>
                      <th style={{ padding: '12px 8px' }}>Category</th>
                      <th style={{ padding: '12px 8px', textAlign: 'right' }}>Carbon (CO₂e)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.items.map((item, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                        <td style={{ padding: '14px 8px', color: '#fff', fontWeight: '500' }}>{item.name}</td>
                        <td style={{ padding: '14px 8px', color: 'var(--text-secondary)' }}>
                          {item.quantity} {item.units}
                        </td>
                        <td style={{ padding: '14px 8px', color: 'var(--text-secondary)' }}>₹{item.price.toFixed(2)}</td>
                        <td style={{ padding: '14px 8px' }}>
                          <span style={{
                            padding: '4px 10px',
                            borderRadius: '20px',
                            fontSize: '0.75rem',
                            fontWeight: '600',
                            textTransform: 'uppercase',
                            background: getBadgeColor(item.carbon_category),
                            color: getTextColor(item.carbon_category)
                          }}>
                            {item.carbon_category}
                          </span>
                        </td>
                        <td style={{ padding: '14px 8px', textAlign: 'right', fontWeight: 'bold', color: item.carbon_kg > 0 ? '#fff' : 'var(--text-secondary)' }}>
                          {item.carbon_kg > 0 ? `+${item.carbon_kg.toFixed(1)} kg` : '0.0 kg'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Success banner */}
            <div style={{
              background: 'rgba(16, 185, 129, 0.06)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              borderRadius: '12px',
              padding: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={20} style={{ color: 'var(--accent-mint)' }} />
                <span style={{ fontSize: '0.85rem', color: '#fff' }}>
                  Successfully synced {result.saved_logs.length} carbon log items to your database!
                </span>
              </div>
              <button onClick={() => setResult(null)} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                Scan Another
              </button>
            </div>
            
          </div>
        )}

      </div>
    </div>
  );
}

export default ReceiptUpload;
