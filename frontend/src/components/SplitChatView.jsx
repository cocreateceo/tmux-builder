import { useState, useCallback, useMemo } from 'react';
import { useProgressSocket } from '../hooks/useProgressSocket';
import apiService from '../services/api';
import MessageList from './MessageList';
import InputArea from './InputArea';
import McpToolsLog from './McpToolsLog';

function SplitChatView() {
  const [messages, setMessages] = useState([]);
  const [sessionReady, setSessionReady] = useState(false);
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
  const mcpHandlers = useMemo(() => ({
    // Generic message handler - called for ALL messages
    onMessage: (data) => {
      console.log('[SplitChatView] Message received:', data.type, data.message);
    },
    onAck: () => {
      setLoading(true);
    },
    onComplete: () => {
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
    clearActivityLog(); // Clear logs for new message
    setMessages(prev => [...prev, { role: 'user', content: message, timestamp: new Date().toISOString() }]);
    setLoading(true);
    setError(null);

    try {
      const response = await apiService.sendMessage(message);
      if (response.success && response.response) {
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
  }, [clearActivityLog]);

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

  // Session creation screen
  if (!sessionReady) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center max-w-md">
          <h2 className="text-2xl font-bold mb-4">Tmux Builder</h2>
          <p className="text-gray-600 mb-6">Dual-channel chat with real-time activity log</p>
          {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}
          <button
            onClick={handleCreateSession}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg disabled:bg-gray-400"
          >
            {loading ? 'Creating...' : 'Create Session'}
          </button>
        </div>
      </div>
    );
  }

  // Main split view
  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-gray-800 text-white p-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h1 className="font-bold">Tmux Builder</h1>
          <div className="flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-full ${mcpConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-gray-400">MCP</span>
          </div>
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
        <div className="bg-red-100 text-red-700 p-2 text-center text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {/* Split panels */}
      <div className="flex-1 flex overflow-hidden">
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
