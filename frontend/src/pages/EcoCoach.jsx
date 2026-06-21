import React, { useState, useEffect, useRef, useCallback, memo } from 'react';
import { Leaf, Send } from 'lucide-react';
import { authService } from '../firebase';
import { API_PATHS, CHAT_SUGGESTIONS } from '../constants';

/**
 * Memoized chat message bubble component.
 * Prevents re-rendering the entire message list when a new message arrives.
 */
const ChatMessage = memo(function ChatMessage({ msg, user }) {
  const isAssistant = msg.role === 'assistant';

  return (
    <div style={{
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
        }} aria-hidden="true">
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
        }} aria-hidden="true">
          {user.displayName ? user.displayName[0].toUpperCase() : 'U'}
        </div>
      )}
    </div>
  );
});

/**
 * Parse basic markdown formatting into React elements.
 * Handles **bold**, bullet points (•), and line breaks.
 */
function parseMarkdown(text) {
  if (!text) return text;

  // Split by lines first to handle bullet points and line breaks
  const lines = text.split('\n');
  const elements = [];

  lines.forEach((line, lineIdx) => {
    if (lineIdx > 0) {
      elements.push(<br key={`br-${lineIdx}`} />);
    }

    // Process bold markers within each line
    const parts = line.split(/(\*\*.*?\*\*)/g);
    parts.forEach((part, partIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        elements.push(
          <strong key={`${lineIdx}-${partIdx}`} style={{ color: '#fff' }}>
            {part.slice(2, -2)}
          </strong>
        );
      } else if (part.startsWith('• ') || part.startsWith('- ')) {
        elements.push(
          <span key={`${lineIdx}-${partIdx}`} style={{ display: 'block', margin: '4px 0', paddingLeft: '8px' }}>
            {part}
          </span>
        );
      } else {
        elements.push(part);
      }
    });
  });

  return elements;
}

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

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSendMessage = useCallback(async (textToSend) => {
    const text = textToSend || input;
    if (!text.trim() || sending) return;

    if (!textToSend) setInput('');
    setSending(true);

    setMessages((prev) => [...prev, { role: 'user', content: text }]);

    try {
      const token = await authService.getAuthToken();
      const res = await fetch(API_PATHS.CHAT, {
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
  }, [input, sending, sessionId]);

  const handleFormSubmit = useCallback((e) => {
    e.preventDefault();
    handleSendMessage();
  }, [handleSendMessage]);

  const handleSuggestionClick = useCallback((suggestion) => {
    handleSendMessage(suggestion);
  }, [handleSendMessage]);

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
          }} aria-hidden="true">
            <Leaf size={22} className="animate-spin-slow" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.05rem', fontWeight: '700' }}>Eco-Coach</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <span className="pulse-glow" style={{
                width: '6px',
                height: '6px',
                background: 'var(--accent-mint)',
                borderRadius: '50%',
                display: 'inline-block'
              }} aria-hidden="true"></span>
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
        <div 
          role="log" 
          aria-live="polite" 
          aria-label="Eco-Coach Chat History"
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}
        >
          {messages.map((msg, index) => (
            <ChatMessage key={index} msg={msg} user={user} />
          ))}
          
          {sending && (
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }} role="status" aria-label="Eco-Coach is typing">
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'rgba(16, 185, 129, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-mint)'
              }} aria-hidden="true">
                <Leaf size={16} />
              </div>
              <div className="typing-indicator glass-panel" style={{ padding: '12px 18px', borderTopLeftRadius: '4px' }}>
                <span className="typing-dot" aria-hidden="true"></span>
                <span className="typing-dot" aria-hidden="true"></span>
                <span className="typing-dot" aria-hidden="true"></span>
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
          }} role="group" aria-label="Suggested questions">
            {CHAT_SUGGESTIONS.map((sug, i) => (
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
                aria-label={`Ask: ${sug}`}
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
          <form onSubmit={handleFormSubmit} style={{ display: 'flex', gap: '12px' }}>
            <label htmlFor="chat-message-input" className="sr-only">Ask a question or log a new action</label>
            <input
              id="chat-message-input"
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
              aria-label="Send message"
            >
              <Send size={18} aria-hidden="true" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default EcoCoach;
