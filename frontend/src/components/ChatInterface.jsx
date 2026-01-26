import { useState, useEffect, useCallback, useMemo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import apiService from '../services/api';
import MessageList from './MessageList';
import InputArea from './InputArea';

function ChatInterface() {
  const [messages, setMessages] = useState([]);
  const [sessionReady, setSessionReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [progress, setProgress] = useState(0);

  // GUID is set after session creation (from backend response)
  const [guid, setGuid] = useState(() => localStorage.getItem('tmux_builder_guid') || null);

  // WebSocket handlers
  const wsHandlers = useMemo(() => ({
    onConnect: () => {
      console.log('WebSocket connected');
      setError(null);
    },

    onDisconnect: () => {
      console.log('WebSocket disconnected');
    },

    onStatus: (status) => {
      console.log('Status update:', status);
      setStatusMessage(status.message || '');
      setProgress(status.progress || 0);

      // Check if session is ready
      if (status.state === 'ready' && status.first_message_sent !== undefined) {
        setSessionReady(true);
        setLoading(false);
      }
    },

    onMessage: (data) => {
      console.log('Message received:', data);
      // Add assistant response
      const assistantMessage = {
        role: 'assistant',
        content: data.content,
        timestamp: data.timestamp || new Date().toISOString(),
      };
      setMessages(prev => [...prev, assistantMessage]);
      setLoading(false);
    },

    onHistory: (history) => {
      console.log('History received:', history?.length, 'messages');
      if (history && history.length > 0) {
        setMessages(history);
        setSessionReady(true);
      }
    },

    onSessionCreated: (data) => {
      console.log('Session created:', data);
      if (data.success) {
        setSessionReady(true);
        setLoading(false);
        setError(null);
      }
    },

    onError: (message) => {
      console.error('WebSocket error:', message);
      setError(message);
      setLoading(false);
    }
  }), []);

  // WebSocket connection
  const {
    connected,
    status,
    sendMessage: wsSendMessage,
    createSession: wsCreateSession,
    reconnect
  } = useWebSocket(guid, wsHandlers);

  // Check if session already exists on mount (via HTTP for initial check)
  useEffect(() => {
    const checkExistingSession = async () => {
      // Only check if we have a stored GUID
      if (!guid) {
        console.log('No stored GUID, waiting for session creation');
        return;
      }

      try {
        const status = await apiService.getStatus();
        if (status.ready) {
          console.log('Existing session found, marking ready');
          setSessionReady(true);
          // History will come via WebSocket
        }
      } catch (err) {
        console.log('No existing session or error:', err.message);
        // Clear invalid GUID
        localStorage.removeItem('tmux_builder_guid');
        setGuid(null);
      }
    };

    checkExistingSession();
  }, [guid]);

  // Handle create session
  const handleCreateSession = async () => {
    setLoading(true);
    setError(null);
    setStatusMessage('Creating session...');

    try {
      // Create session via HTTP first (to ensure tmux is started)
      const result = await apiService.createSession();

      if (result.success) {
        // Store the GUID from the backend response
        const newGuid = result.guid;
        if (newGuid) {
          console.log('Session created with GUID:', newGuid);
          localStorage.setItem('tmux_builder_guid', newGuid);
          setGuid(newGuid);  // This will trigger WebSocket reconnect with correct GUID
        }

        setSessionReady(true);
        setStatusMessage('Session ready');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  // Handle send message
  const handleSendMessage = useCallback((messageData) => {
    const { message } = messageData;

    // Add user message to UI immediately (optimistic update)
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    setStatusMessage('Processing...');

    // Send via WebSocket
    if (connected) {
      const sent = wsSendMessage(message);
      if (!sent) {
        setError('Failed to send message - WebSocket not connected');
        setLoading(false);
      }
    } else {
      // Fallback to HTTP if WebSocket not connected
      sendMessageHttp(message);
    }
  }, [connected, wsSendMessage]);

  // Fallback HTTP send
  const sendMessageHttp = async (message) => {
    try {
      const response = await apiService.sendMessage(message);

      if (response.success) {
        const assistantMessage = {
          role: 'assistant',
          content: response.response,
          timestamp: response.timestamp,
        };
        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (err) {
      const errorMessage = {
        role: 'assistant',
        content: `Error: ${err.response?.data?.detail || 'Failed to send message'}`,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
      setStatusMessage('');
    }
  };

  // Handle clear chat
  const handleClearChat = async () => {
    if (!window.confirm('Are you sure you want to clear the chat?')) {
      return;
    }

    try {
      await apiService.clearSession();
      setMessages([]);
      setSessionReady(false);
      setGuid(null);
      localStorage.removeItem('tmux_builder_guid');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to clear session');
    }
  };

  // Render session creation screen
  if (!sessionReady) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-8 text-center h-full flex flex-col items-center justify-center">
        <h2 className="text-2xl font-bold mb-4 text-gray-800">Welcome to Tmux Builder</h2>
        <p className="text-gray-600 mb-6">
          Create a new session to start chatting with Claude via tmux.
        </p>

        {/* Connection status - only show if we have a guid */}
        {guid && (
          <div className="mb-4 flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-gray-600">
              {connected ? 'WebSocket Connected' : 'WebSocket Disconnected'}
            </span>
            {!connected && (
              <button
                onClick={reconnect}
                className="text-blue-600 hover:text-blue-800 text-xs underline"
              >
                Reconnect
              </button>
            )}
          </div>
        )}

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4 max-w-md">
            {error}
          </div>
        )}

        <button
          onClick={handleCreateSession}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {loading ? 'Creating Session...' : 'Create Session'}
        </button>

        {loading && (
          <div className="mt-4 text-gray-600">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-sm">{statusMessage || 'Initializing tmux session with Claude...'}</p>
            {progress > 0 && (
              <div className="w-64 bg-gray-200 rounded-full h-2 mt-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Render chat interface
  return (
    <div className="bg-white rounded-lg shadow-lg h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 p-4 flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Chat Session</h2>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
            <span>{connected ? 'Connected via WebSocket' : 'Reconnecting...'}</span>
            {statusMessage && loading && (
              <span className="text-blue-600">• {statusMessage}</span>
            )}
          </div>
        </div>
        <button
          onClick={handleClearChat}
          className="text-sm text-red-600 hover:text-red-800 font-medium"
        >
          Clear Chat
        </button>
      </div>

      {/* Status bar when processing */}
      {loading && statusMessage && (
        <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 flex items-center gap-3">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          <span className="text-sm text-blue-700">{statusMessage}</span>
          {progress > 0 && progress < 100 && (
            <div className="flex-1 max-w-xs bg-blue-200 rounded-full h-1.5">
              <div
                className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          )}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 flex items-center justify-between">
          <span className="text-sm text-red-700">{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-700"
          >
            ✕
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        <MessageList messages={messages} loading={loading} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <InputArea onSendMessage={handleSendMessage} disabled={loading} />
      </div>
    </div>
  );
}

export default ChatInterface;
