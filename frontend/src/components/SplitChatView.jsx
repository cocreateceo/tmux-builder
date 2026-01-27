import { useState, useCallback, useMemo, useEffect } from 'react';
import { useProgressSocket } from '../hooks/useProgressSocket';
import apiService from '../services/api';
import MessageList from './MessageList';
import InputArea from './InputArea';
import McpToolsLog from './McpToolsLog';
import SessionSidebar from './SessionSidebar';

function SplitChatView() {
  const [messages, setMessages] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [guid, setGuid] = useState(() => {
    const stored = localStorage.getItem('tmux_builder_guid');
    // Handle edge cases where "null" or "undefined" might be stored as strings
    if (!stored || stored === 'null' || stored === 'undefined') {
      return null;
    }
    return stored;
  });

  // Channel 2: MCP WebSocket (progress/tools log)
  // NOTE: Loading state is controlled by HTTP request lifecycle in handleSendMessage,
  // NOT by WebSocket events. This prevents init acks from blocking the UI.
  const mcpHandlers = useMemo(() => ({
    // Generic message handler - called for ALL messages
    onMessage: (data) => {
      console.log('[SplitChatView] Message received:', data.type, data.message);
    },
    onAck: () => {
      // Don't set loading here - ack is informational only
      // Loading state is managed by handleSendMessage HTTP lifecycle
      console.log('[SplitChatView] Ack received (informational)');
    },
    onComplete: () => {
      // Don't set loading here either - HTTP response handles it
      console.log('[SplitChatView] Complete received');
    },
    onSummary: (data) => {
      // Add summary as assistant message - this is the main completion response
      if (data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message,
          timestamp: data.timestamp
        }]);
      }
      setLoading(false);
    },
    onDeployed: (data) => {
      // Add deployed URL as assistant message
      if (data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `🚀 Deployed: ${data.message}`,
          timestamp: data.timestamp
        }]);
      }
    },
    onResponse: (data) => {
      if (data.message || data.content) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message || data.content,
          timestamp: data.timestamp
        }]);
      }
      setLoading(false);
    },
    onError: (data) => {
      setError(data.message || 'An error occurred');
      setLoading(false);
    }
  }), []);

  const {
    connected: mcpConnected,
    progress,
    statusMessage,
    activityLog,
    clearActivityLog
  } = useProgressSocket(guid, mcpHandlers);

  // Auto-resume session if GUID exists in localStorage
  useEffect(() => {
    const resumeSession = async () => {
      if (guid) {
        try {
          // Check if session is still valid by fetching history
          const historyResponse = await apiService.getHistory(guid);
          if (historyResponse && historyResponse.messages) {
            setMessages(historyResponse.messages);
            console.log('[SplitChatView] Restored', historyResponse.messages.length, 'messages');
          }
          console.log('[SplitChatView] Resumed session:', guid);
        } catch (err) {
          // Session doesn't exist or is invalid, clear stored GUID
          console.log('[SplitChatView] Failed to resume session, clearing GUID');
          localStorage.removeItem('tmux_builder_guid');
          setGuid(null);
        }
      }
    };
    resumeSession();
  }, [guid]);

  // Create session
  const handleCreateSession = async () => {
    setLoading(true);
    setError(null);
    clearActivityLog();

    try {
      const result = await apiService.createSession();
      if (result.success && result.guid) {
        localStorage.setItem('tmux_builder_guid', result.guid);
        setGuid(result.guid);
        setSessionReady(true);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  // Send message
  const handleSendMessage = useCallback(async (messageData) => {
    const { message } = messageData;
    // NOTE: Don't clear activity log - let it accumulate across messages
    setMessages(prev => [...prev, { role: 'user', content: message, timestamp: new Date().toISOString() }]);
    setLoading(true);
    setError(null);

    try {
      const response = await apiService.sendMessage(message, guid);
      if (response.success && response.response) {
        // Store GUID if returned (auto-created session)
        if (response.guid && response.guid !== guid) {
          localStorage.setItem('tmux_builder_guid', response.guid);
          setGuid(response.guid);
          console.log('[SplitChatView] Stored new GUID:', response.guid);
        }
        setMessages(prev => [...prev, {
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
  }, [guid]);

  // Clear chat
  const handleClearChat = async () => {
    if (!window.confirm('Clear chat and activity log?')) return;
    try {
      await apiService.clearSession();
      setMessages([]);
      clearActivityLog();
      setSessionReady(false);
      setGuid(null);
      localStorage.removeItem('tmux_builder_guid');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to clear session');
    }
  };

  // Handle session selection from sidebar
  const handleSelectSession = useCallback(async (selectedGuid) => {
    setLoading(true);
    setError(null);
    try {
      localStorage.setItem('tmux_builder_guid', selectedGuid);
      setGuid(selectedGuid);

      const historyResponse = await apiService.getHistory(selectedGuid);
      if (historyResponse && historyResponse.messages) {
        setMessages(historyResponse.messages);
        console.log('[SplitChatView] Loaded', historyResponse.messages.length, 'messages');
      } else {
        setMessages([]);
      }
      clearActivityLog();
      setSidebarOpen(false);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load session');
    } finally {
      setLoading(false);
    }
  }, [clearActivityLog]);

  // Handle new session creation from sidebar
  const handleSidebarCreateSession = useCallback((newGuid) => {
    localStorage.setItem('tmux_builder_guid', newGuid);
    setGuid(newGuid);
    setMessages([]);
    clearActivityLog();
    setSidebarOpen(false);
  }, [clearActivityLog]);

  // Main split view
  return (
    <div className="h-screen flex flex-col">
      {/* Collapsible Session Sidebar */}
      <SessionSidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        currentGuid={guid}
        onSelectSession={handleSelectSession}
        onCreateSession={handleSidebarCreateSession}
      />

      {/* Header */}
      <div className={`bg-gray-800 text-white p-3 flex justify-between items-center transition-all ${sidebarOpen ? 'ml-72' : 'ml-0'}`}>
        <div className="flex items-center gap-4">
          <h1 className="font-bold">Tmux Builder</h1>
          <div className="flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-full ${mcpConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-gray-400">MCP</span>
          </div>
          {guid && (
            <span className="text-xs text-gray-500 font-mono">
              {guid.substring(0, 12)}...
            </span>
          )}
          {statusMessage && (
            <span className="text-sm text-gray-400 truncate max-w-xs">
              {statusMessage}
            </span>
          )}
        </div>
        <button onClick={handleClearChat} className="text-sm text-red-400 hover:text-red-300">
          Clear Session
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className={`bg-red-100 text-red-700 p-2 text-center text-sm transition-all ${sidebarOpen ? 'ml-72' : 'ml-0'}`}>
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {/* Split panels */}
      <div className={`flex-1 flex overflow-hidden transition-all ${sidebarOpen ? 'ml-72' : 'ml-0'}`}>
        {/* Left: Chat */}
        <div className="w-1/2 flex flex-col border-r border-gray-300">
          <div className="flex-1 overflow-y-auto p-4 bg-white">
            <MessageList messages={messages} loading={loading} />
          </div>
          <div className="border-t border-gray-200 p-4 bg-white">
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

export default SplitChatView;
