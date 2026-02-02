import { useState, useCallback, useMemo, useEffect } from 'react';
import { useProgressSocket } from '../hooks/useProgressSocket.js';
import apiService from '../services/api.js';
import MessageList from './MessageList.jsx';
import InputArea from './InputArea.jsx';
import McpToolsLog from './McpToolsLog.jsx';
import SessionSidebar from './SessionSidebar.jsx';
import EmbedView from './EmbedView.jsx';

// Admin password (in production, this should be an environment variable or backend auth)
const ADMIN_PASSWORD = 'tmux@admin2026';

function getUrlParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    guid: params.get('guid'),
    embed: params.get('embed') === 'true',
    theme: params.get('theme')
  };
}

function getStoredGuid() {
  const stored = localStorage.getItem('tmux_builder_guid');
  if (!stored || stored === 'null' || stored === 'undefined') {
    return null;
  }
  return stored;
}

function isAdminLoggedIn() {
  return localStorage.getItem('tmux_admin_auth') === 'true';
}

function SplitChatView() {
  const urlParams = getUrlParams();

  // Early return for themed embed mode (/?guid=xxx&embed=true)
  // This renders the dedicated themed EmbedView component
  if (urlParams.embed) {
    return (
      <EmbedView
        initialGuid={urlParams.guid}
        initialTheme={urlParams.theme}
      />
    );
  }

  // Below is the Admin UI - shown when embed=false or not set
  const [isAdmin, setIsAdmin] = useState(isAdminLoggedIn());
  const isEmbedMode = !isAdmin; // Non-admin gets simplified view (no sidebar)

  const [messages, setMessages] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  // Use URL guid if provided, otherwise use stored guid
  const [guid, setGuid] = useState(urlParams.guid || getStoredGuid);

  // MCP WebSocket handlers for progress updates
  // Loading state is controlled by HTTP request lifecycle, not WebSocket events
  const mcpHandlers = useMemo(() => ({
    onSummary: (data) => {
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
      if (data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `Deployed: ${data.message}`,
          timestamp: data.timestamp
        }]);
      }
    },
    onResponse: (data) => {
      const content = data.message || data.content;
      if (content) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content,
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

  // Auto-resume session if GUID exists (from URL or localStorage)
  useEffect(() => {
    if (!guid) return;

    // Store URL guid to localStorage for persistence
    if (urlParams.guid) {
      localStorage.setItem('tmux_builder_guid', guid);
    }

    apiService.getHistory(guid)
      .then(historyResponse => {
        if (historyResponse?.messages) {
          setMessages(historyResponse.messages);
        }
      })
      .catch(() => {
        if (!isEmbedMode) {
          localStorage.removeItem('tmux_builder_guid');
          setGuid(null);
        }
      });
  }, [guid, urlParams.guid, isEmbedMode]);

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

  // Admin login
  const handleAdminLogin = (e) => {
    e.preventDefault();
    if (loginPassword === ADMIN_PASSWORD) {
      localStorage.setItem('tmux_admin_auth', 'true');
      setIsAdmin(true);
      setShowLoginModal(false);
      setLoginPassword('');
      setLoginError('');
    } else {
      setLoginError('Invalid password');
    }
  };

  // Admin logout
  const handleAdminLogout = () => {
    localStorage.removeItem('tmux_admin_auth');
    setIsAdmin(false);
    setSidebarOpen(false);
  };

  // Main split view
  return (
    <div className="h-screen flex flex-col">
      {/* Collapsible Session Sidebar - hidden in embed mode */}
      {!isEmbedMode && (
        <SessionSidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          currentGuid={guid}
          onSelectSession={handleSelectSession}
          onCreateSession={handleSidebarCreateSession}
        />
      )}

      {/* Header */}
      <div className={`bg-gray-800 text-white p-3 flex justify-between items-center transition-all ${!isEmbedMode && sidebarOpen ? 'ml-72' : 'ml-0'}`}>
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
        <div className="flex items-center gap-4">
          {isAdmin ? (
            <>
              <span className="text-xs text-green-400">Admin</span>
              <button onClick={handleClearChat} className="text-sm text-red-400 hover:text-red-300">
                Clear Session
              </button>
              <button onClick={handleAdminLogout} className="text-sm text-gray-400 hover:text-white">
                Logout
              </button>
            </>
          ) : (
            <button
              onClick={() => setShowLoginModal(true)}
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              Admin Login
            </button>
          )}
        </div>
      </div>

      {/* Admin Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-80 shadow-xl">
            <h2 className="text-lg font-bold text-gray-800 mb-4">Admin Login</h2>
            <form onSubmit={handleAdminLogin}>
              <input
                type="password"
                placeholder="Enter admin password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 mb-3 focus:outline-none focus:border-blue-500"
                autoFocus
              />
              {loginError && (
                <div className="text-red-500 text-sm mb-3">{loginError}</div>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowLoginModal(false);
                    setLoginPassword('');
                    setLoginError('');
                  }}
                  className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded"
                >
                  Login
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className={`bg-red-100 text-red-700 p-2 text-center text-sm transition-all ${!isEmbedMode && sidebarOpen ? 'ml-72' : 'ml-0'}`}>
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {/* Split panels */}
      <div className={`flex-1 flex overflow-hidden transition-all ${!isEmbedMode && sidebarOpen ? 'ml-72' : 'ml-0'}`}>
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
