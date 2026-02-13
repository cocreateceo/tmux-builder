import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import MessageList from './MessageList';
import InputArea from './InputArea';
import McpToolsLog from './McpToolsLog';
import { initTheme } from '../themes/ThemeManager';
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
export default function EmbedView({ initialGuid }) {
  // State
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

  // Initialize ember theme on mount
  useEffect(() => {
    initTheme('ember');
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
    statusMessage,
    activityLog,
    progress
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

  return (
    <div className="embed-container h-screen flex flex-col">
      {/* Animated gradient background */}
      <div className="embed-background" />

      {/* Header - glass effect matching reference project */}
      <div className="p-3 flex justify-between items-center embed-card" style={{ borderRadius: 0, borderLeft: 'none', borderRight: 'none', borderTop: 'none' }}>
        <div className="flex items-center gap-4">
          <h1 className="font-bold embed-text-primary">Tmux Builder</h1>
          <div className="flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-full ${mcpConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="embed-text-muted">MCP</span>
          </div>
          {guid && (
            <span className="text-xs embed-text-muted font-mono">
              {guid.substring(0, 12)}...
            </span>
          )}
          {statusMessage && (
            <span className="text-sm embed-text-secondary truncate max-w-xs">
              {statusMessage}
            </span>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="p-2 text-center text-sm" style={{ background: 'rgba(239, 68, 68, 0.2)', color: 'var(--text-primary)' }}>
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {/* Split panels - exact same structure as SplitChatView */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat */}
        <div className="w-1/2 flex flex-col" style={{ borderRight: '1px solid var(--border-color)' }}>
          <div className="flex-1 overflow-y-auto p-4" style={{ background: 'var(--bg-card)' }}>
            <MessageList messages={messages} loading={loading} />
          </div>
          <div className="p-4" style={{ borderTop: '1px solid var(--border-color)', background: 'var(--bg-card)' }}>
            <InputArea onSendMessage={handleSendMessage} disabled={loading} />
          </div>
        </div>

        {/* Right: Activity Log */}
        <div className="w-1/2">
          <McpToolsLog logs={activityLog} connected={mcpConnected} progress={progress} />
        </div>
      </div>
    </div>
  );
}
