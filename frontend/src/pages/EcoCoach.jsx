import React, { useState, useEffect, useRef } from 'react';
import { Leaf, Send, Sparkles, User, Info } from 'lucide-react';
import { authService } from '../firebase';

function EcoCoach({ user }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I am your **Eco-Coach** 🌿. I'm here to help you log activities, estimate carbon impact, and discover practical lifestyle changes to live more sustainably.\n\nWhat would you like to log or ask about today?"
    }
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sessionId] = useState(() => `session-${user.uid}-${Math.random().toString(36).substr(2, 9)}`);
  
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (textToSend) => {
    const text = textToSend || input;
    if (!text.trim() || sending) return;

    if (!textToSend) setInput('');
    setSending(true);

    // Append user message
    setMessages((prev) => [...prev, { role: 'user', content: text }]);

    try {
      const token = await authService.getAuthToken();
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: text,
          session_id: sessionId
        })
      });

      if (!res.ok) {
        throw new Error('Failed to get coach reply.');
      }

      const data = await res.json();
      
      // Append assistant reply
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: "I'm sorry, I'm having trouble connecting to my environment. Please make sure the backend server is running."
      }]);
    } finally {
      setSending(false);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    handleSendMessage(suggestion);
  };

  const parseMarkdown = (text) => {
    // Basic helper to convert markdown double-asterisk to bold tags and linebreaks
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index} style={{ color: '#fff' }}>{part.slice(2, -2)}</strong>;
      }
      // Replace bullet points
      if (part.startsWith('•')) {
        return <span key={index} style={{ display: 'block', margin: '4px 0' }}>{part}</span>;
      }
      return part;
    });
  };

  const suggestions = [
    "How can I reduce food emissions?",
    "Tips to lower my electricity bill?",
    "Is driving an EV actually eco-friendly?",
    "Recommend a green lifestyle habit."
  ];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: 'calc(100vh - 80px)',
      width: '100%',
      gap: '24px'
    }}>
      {/* Coach Header */}
      <div className="glass-panel" style={{
        padding: '16px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            background: 'rgba(16, 185, 129, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-mint)'
          }}>
            <Leaf size={22} className="animate-spin-slow" />
          </div>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '700' }}>Eco-Coach</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <span className="pulse-glow" style={{
                width: '6px',
                height: '6px',
                background: 'var(--accent-mint)',
                borderRadius: '50%'
              }}></span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Gemini AI Consultant</span>
            </div>
          </div>
        </div>
      </div>

      {/* Messages Window */}
      <div className="glass-panel" style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative'
      }}>
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px'
        }}>
          {messages.map((msg, index) => {
            const isAssistant = msg.role === 'assistant';
            return (
              <div key={index} style={{
                display: 'flex',
                justifyContent: isAssistant ? 'flex-start' : 'flex-end',
                alignItems: 'flex-start',
                gap: '12px',
                width: '100%'
              }}>
                {isAssistant && (
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: 'rgba(16, 185, 129, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-mint)',
                    flexShrink: 0
                  }}>
                    <Leaf size={16} />
                  </div>
                )}
                
                <div style={{
                  maxWidth: '75%',
                  padding: '16px',
                  borderRadius: '16px',
                  fontSize: '0.92rem',
                  lineHeight: '1.5',
                  whiteSpace: 'pre-line',
                  background: isAssistant ? 'rgba(255, 255, 255, 0.02)' : 'linear-gradient(135deg, var(--accent-emerald), var(--accent-cyan))',
                  color: isAssistant ? 'var(--text-primary)' : '#fff',
                  border: isAssistant ? '1px solid var(--border-color)' : 'none',
                  borderTopLeftRadius: isAssistant ? '4px' : '16px',
                  borderTopRightRadius: isAssistant ? '16px' : '4px',
                  boxShadow: isAssistant ? 'none' : '0 4px 12px rgba(16, 185, 129, 0.2)'
                }}>
                  {parseMarkdown(msg.content)}
                </div>
                
                {!isAssistant && (
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, var(--accent-emerald), var(--accent-cyan))',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    fontWeight: 'bold',
                    fontSize: '0.8rem',
                    flexShrink: 0
                  }}>
                    {user.displayName ? user.displayName[0].toUpperCase() : 'U'}
                  </div>
                )}
              </div>
            );
          })}
          
          {sending && (
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'rgba(16, 185, 129, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-mint)'
              }}>
                <Leaf size={16} />
              </div>
              <div className="typing-indicator glass-panel" style={{ padding: '12px 18px', borderTopLeftRadius: '4px' }}>
                <span className="typing-dot"></span>
                <span className="typing-dot"></span>
                <span className="typing-dot"></span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        {messages.length === 1 && (
          <div style={{
            padding: '0 24px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '10px',
            marginBottom: '16px'
          }}>
            {suggestions.map((sug, i) => (
              <button
                key={i}
                onClick={() => handleSuggestionClick(sug)}
                className="btn-secondary"
                style={{
                  padding: '8px 14px',
                  fontSize: '0.8rem',
                  borderRadius: '30px',
                  cursor: 'pointer',
                  borderColor: 'rgba(16, 185, 129, 0.15)'
                }}
              >
                {sug}
              </button>
            ))}
          </div>
        )}

        {/* Bottom Input Area */}
        <div style={{
          padding: '20px 24px',
          borderTop: '1px solid var(--border-color)',
          background: 'rgba(11, 15, 23, 0.4)'
        }}>
          <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} style={{ display: 'flex', gap: '12px' }}>
            <input
              type="text"
              className="input-field"
              placeholder="Ask a question or log a new action..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={sending}
            />
            <button
              type="submit"
              className="btn-primary"
              disabled={sending || !input.trim()}
              style={{ width: '48px', height: '48px', padding: 0, flexShrink: 0 }}
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default EcoCoach;
