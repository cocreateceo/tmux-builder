import { useState, useEffect } from 'react';
import apiService from '../services/api';
import MessageList from './MessageList';
import InputArea from './InputArea';

function ChatInterface() {
  const [messages, setMessages] = useState([]);
  const [sessionReady, setSessionReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Check session status on mount
  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const status = await apiService.getStatus();
      setSessionReady(status.ready);

      if (status.ready) {
        // Load chat history
        loadHistory();
      }
    } catch (err) {
      console.error('Error checking status:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const history = await apiService.getHistory();
      setMessages(history.messages || []);
    } catch (err) {
      console.error('Error loading history:', err);
    }
  };

  const handleCreateSession = async () => {
    setLoading(true);
    setError(null);

    try {
      await apiService.createSession();

      // Poll for session ready
      let attempts = 0;
      const maxAttempts = 20;

      const pollStatus = async () => {
        const status = await apiService.getStatus();

        if (status.ready) {
          setSessionReady(true);
          setLoading(false);
          loadHistory();
        } else if (attempts < maxAttempts) {
          attempts++;
          setTimeout(pollStatus, 2000);
        } else {
          setLoading(false);
          setError('Session initialization timeout');
        }
      };

      pollStatus();
    } catch (err) {
      setLoading(false);
      setError(err.response?.data?.detail || 'Failed to create session');
    }
  };

  const handleSendMessage = async (messageData) => {
    const { message } = messageData;

    // Add user message to UI immediately
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    setLoading(true);

    try {
      const response = await apiService.sendMessage(message);

      if (response.success) {
        // Add assistant response
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
    }
  };

  const handleClearChat = async () => {
    if (!window.confirm('Are you sure you want to clear the chat?')) {
      return;
    }

    try {
      await apiService.clearSession();
      setMessages([]);
      setSessionReady(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to clear session');
    }
  };

  if (!sessionReady) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-8 text-center h-full flex flex-col items-center justify-center">
        <h2 className="text-2xl font-bold mb-4 text-gray-800">Welcome to Tmux Builder</h2>
        <p className="text-gray-600 mb-6">
          Create a new session to start chatting with Claude via tmux.
        </p>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
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
            <p className="mt-2 text-sm">Initializing tmux session with Claude...</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-lg h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 p-4 flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Chat Session</h2>
          <p className="text-xs text-gray-500">Connected via tmux</p>
        </div>
        <button
          onClick={handleClearChat}
          className="text-sm text-red-600 hover:text-red-800 font-medium"
        >
          Clear Chat
        </button>
      </div>

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
