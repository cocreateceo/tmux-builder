import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import MessageList from './MessageList';
import InputArea from './InputArea';
import ThemePicker from './ThemePicker';
import { initTheme, subscribeToThemeChanges, getStoredTheme } from '../themes/ThemeManager';
import useProgressSocket from '../hooks/useProgressSocket';
import apiService from '../services/api.js';
import '../themes/themeStyles.css';

// Helper to validate GUID format
function isValidGuid(guid) {
  if (!guid || typeof guid !== 'string') return false;
  if (guid === 'null' || guid === 'undefined') return false;
  return guid.length >= 8;
}

// Generate unique message ID
let messageIdCounter = 0;
function generateMessageId() {
  return `msg_${Date.now()}_${++messageIdCounter}`;
}

/**
 * EmbedView - Themed embed mode container for tmux-builder
 *
 * Features:
 * - Glass-morphism card styling
 * - Animated gradient background
 * - Theme picker with persistence
 * - Full chat functionality via WebSocket
 * - Reuses existing MessageList and InputArea components
 */
export default function EmbedView({ initialGuid, initialTheme }) {
  // State
  const [currentTheme, setCurrentTheme] = useState(() => getStoredTheme());
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Validate initialGuid before using
  const [guid, setGuid] = useState(() => isValidGuid(initialGuid) ? initialGuid : null);

  // Use ref for guid in callbacks to avoid stale closure issues
  const guidRef = useRef(guid);
  useEffect(() => {
    guidRef.current = guid;
  }, [guid]);

  // Initialize theme on mount
  useEffect(() => {
    const appliedTheme = initTheme(initialTheme);
    setCurrentTheme(appliedTheme);
  }, [initialTheme]);

  // Subscribe to cross-tab theme changes
  useEffect(() => {
    const unsubscribe = subscribeToThemeChanges((newTheme) => {
      setCurrentTheme(newTheme);
    });
    return unsubscribe;
  }, []);

  // WebSocket handlers for real-time updates
  const mcpHandlers = useMemo(() => ({
    onSummary: (data) => {
      if (data.message) {
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          role: 'assistant',
          content: data.message,
          timestamp: data.timestamp || new Date().toISOString()
        }]);
      }
      setLoading(false);
    },
    onDeployed: (data) => {
      if (data.message) {
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          role: 'assistant',
          content: `Deployed: ${data.message}`,
          timestamp: data.timestamp || new Date().toISOString()
        }]);
      }
    },
    onResponse: (data) => {
      const content = data.message || data.content;
      if (content) {
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          role: 'assistant',
          content,
          timestamp: data.timestamp || new Date().toISOString()
        }]);
      }
      setLoading(false);
    },
    onError: (data) => {
      setError(data.message || 'An error occurred');
      setLoading(false);
    }
  }), []);

  // Connect to WebSocket for real-time progress
  const {
    connected: mcpConnected,
    statusMessage
  } = useProgressSocket(guid, mcpHandlers);

  // Load chat history when guid changes
  useEffect(() => {
    if (!guid) return;

    apiService.getHistory(guid)
      .then(historyResponse => {
        if (historyResponse?.messages) {
          // Add stable IDs to history messages
          const messagesWithIds = historyResponse.messages.map((msg, index) => ({
            ...msg,
            id: msg.id || `history_${index}_${Date.now()}`
          }));
          setMessages(messagesWithIds);
        }
      })
      .catch((err) => {
        console.error('[EmbedView] Failed to load history:', err);
      });
  }, [guid]);

  // Send message handler - uses guidRef to avoid stale closure
  const handleSendMessage = useCallback(async (messageData) => {
    const { message } = messageData;
    const currentGuid = guidRef.current;

    setMessages(prev => [...prev, {
      id: generateMessageId(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }]);
    setLoading(true);
    setError(null);

    try {
      const response = await apiService.sendMessage(message, currentGuid);
      if (response.success && response.response) {
        // Store GUID if returned (auto-created session)
        if (response.guid && response.guid !== currentGuid) {
          setGuid(response.guid);
          console.log('[EmbedView] Stored new GUID:', response.guid);
        }
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          role: 'assistant',
          content: response.response,
          timestamp: response.timestamp || new Date().toISOString()
        }]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to send message');
    } finally {
      setLoading(false);
    }
  }, []); // No guid dependency - uses ref instead

  // Theme change handler
  const handleThemeChange = useCallback((newTheme) => {
    setCurrentTheme(newTheme);
  }, []);

  return (
    <div className="embed-container">
      {/* Animated gradient background */}
      <div className="embed-background" />

      {/* Main content */}
      <div className="min-h-screen flex flex-col p-4 md:p-6">
        {/* Header */}
        <header className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-3">
            <h1 className="embed-text-primary text-xl font-bold">Tmux Builder</h1>
            <div className="flex items-center gap-2 text-sm">
              <span
                className={`w-2 h-2 rounded-full ${
                  mcpConnected ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
              <span className="embed-text-muted text-xs">
                {mcpConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            {guid && (
              <span className="embed-text-muted text-xs font-mono">
                {guid.substring(0, 8)}...
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {statusMessage && (
              <span className="embed-text-secondary text-sm truncate max-w-[200px]">
                {statusMessage}
              </span>
            )}
            <ThemePicker
              currentTheme={currentTheme}
              onThemeChange={handleThemeChange}
            />
          </div>
        </header>

        {/* Error banner */}
        {error && (
          <div className="embed-card bg-red-500/20 border-red-500/50 text-red-200 p-3 mb-4 flex justify-between items-center">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="embed-text-muted hover:text-white underline text-sm"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Chat card - glass morphism style */}
        <main className="flex-1 flex flex-col embed-card embed-card-glow overflow-hidden">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6">
            <MessageList messages={messages} loading={loading} />
          </div>

          {/* Input area */}
          <div className="border-t border-[var(--border-color)] p-4">
            <InputArea onSendMessage={handleSendMessage} disabled={loading} />
          </div>
        </main>

        {/* Footer */}
        <footer className="mt-4 text-center">
          <p className="embed-text-muted text-xs">
            Powered by Claude CLI
          </p>
        </footer>
      </div>
    </div>
  );
}
