import { useState, useEffect } from 'react';
import apiService from '../services/api';

function AdminSessionList({ onSelectSession, onCreateSession, onBackToSession, currentGuid }) {
  const [sessions, setSessions] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedSession, setSelectedSession] = useState(null);

  // Create form state
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [initialRequest, setInitialRequest] = useState('');
  const [creating, setCreating] = useState(false);

  // Fetch sessions
  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiService.listSessions(filter);
      setSessions(result.sessions || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [filter]);

  // Handle session selection
  const handleSelectSession = (session) => {
    setSelectedSession(session);
  };

  // Handle resume session
  const handleResumeSession = () => {
    if (selectedSession) {
      onSelectSession(selectedSession.guid);
    }
  };

  // Handle create session
  const handleCreateSession = async (e) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Email is required');
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const result = await apiService.createAdminSession(email, phone, initialRequest);
      if (result.success && result.guid) {
        onCreateSession(result.guid);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create session');
    } finally {
      setCreating(false);
    }
  };

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Header */}
      <div className="bg-gray-800 text-white p-4 flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold">Tmux Builder - Admin</h1>
          <p className="text-gray-400 text-sm">Session Management</p>
        </div>
        {currentGuid && onBackToSession && (
          <button
            onClick={onBackToSession}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            Back to Session
          </button>
        )}
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Session List */}
        <div className="w-1/2 flex flex-col border-r border-gray-300 bg-white">
          {/* Filter & Actions */}
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Filter:</label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 text-sm"
              >
                <option value="all">All Sessions</option>
                <option value="active">Active (tmux running)</option>
                <option value="completed">Completed</option>
              </select>
              <button
                onClick={fetchSessions}
                className="text-blue-600 hover:text-blue-800 text-sm ml-2"
              >
                Refresh
              </button>
            </div>
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-1 rounded text-sm"
            >
              {showCreateForm ? 'Cancel' : '+ New Session'}
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="bg-red-100 text-red-700 p-2 text-sm">
              {error}
              <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
            </div>
          )}

          {/* Create Form */}
          {showCreateForm && (
            <div className="p-4 bg-blue-50 border-b border-blue-200">
              <h3 className="font-semibold mb-2">Create New Session</h3>
              <form onSubmit={handleCreateSession} className="space-y-2">
                <div>
                  <label className="block text-sm text-gray-600">Email *</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="user@example.com"
                    className="w-full border border-gray-300 rounded px-3 py-1 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600">Phone</label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="0000000000"
                    className="w-full border border-gray-300 rounded px-3 py-1 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600">Initial Request</label>
                  <textarea
                    value={initialRequest}
                    onChange={(e) => setInitialRequest(e.target.value)}
                    placeholder="Optional: What should Claude do?"
                    className="w-full border border-gray-300 rounded px-3 py-1 text-sm"
                    rows={2}
                  />
                </div>
                <button
                  type="submit"
                  disabled={creating}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded text-sm disabled:bg-gray-400"
                >
                  {creating ? 'Creating...' : 'Create Session'}
                </button>
              </form>
            </div>
          )}

          {/* Session List */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-gray-500">Loading sessions...</div>
            ) : sessions.length === 0 ? (
              <div className="p-4 text-center text-gray-500">No sessions found</div>
            ) : (
              <div className="divide-y divide-gray-200">
                {sessions.map((session) => (
                  <div
                    key={session.guid}
                    onClick={() => handleSelectSession(session)}
                    className={`p-3 cursor-pointer hover:bg-gray-50 ${
                      selectedSession?.guid === session.guid ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm text-gray-600">{session.guid_short}</span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          session.tmux_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {session.tmux_active ? 'Active' : 'Completed'}
                      </span>
                    </div>
                    <div className="text-sm text-gray-700 mt-1">{session.email || 'No email'}</div>
                    <div className="flex items-center gap-4 text-xs text-gray-500 mt-1">
                      <span>State: {session.state || 'N/A'}</span>
                      <span>Msgs: {session.chat_message_count}</span>
                      <span>Logs: {session.activity_log_count}</span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {formatDate(session.created_at)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Selected Session Actions */}
          {selectedSession && (
            <div className="p-4 border-t border-gray-200 bg-gray-50">
              <button
                onClick={handleResumeSession}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded font-semibold"
              >
                Resume Session
              </button>
            </div>
          )}
        </div>

        {/* Right Panel - Session Details */}
        <div className="w-1/2 bg-white p-4 overflow-y-auto">
          {selectedSession ? (
            <div>
              <h2 className="text-lg font-bold mb-4">Session Details</h2>

              <div className="space-y-3">
                <div>
                  <label className="text-sm text-gray-500">GUID</label>
                  <div className="font-mono text-xs bg-gray-100 p-2 rounded break-all">
                    {selectedSession.guid}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-gray-500">Email</label>
                    <div className="text-sm">{selectedSession.email || 'N/A'}</div>
                  </div>
                  <div>
                    <label className="text-sm text-gray-500">Phone</label>
                    <div className="text-sm">{selectedSession.phone || 'N/A'}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-gray-500">State</label>
                    <div className="text-sm">{selectedSession.state || 'N/A'}</div>
                  </div>
                  <div>
                    <label className="text-sm text-gray-500">Progress</label>
                    <div className="text-sm">{selectedSession.progress}%</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-gray-500">Tmux Status</label>
                    <div className={`text-sm font-semibold ${
                      selectedSession.tmux_active ? 'text-green-600' : 'text-gray-500'
                    }`}>
                      {selectedSession.tmux_active ? 'Running' : 'Not Running'}
                    </div>
                  </div>
                  <div>
                    <label className="text-sm text-gray-500">Chat Messages</label>
                    <div className="text-sm">{selectedSession.chat_message_count}</div>
                  </div>
                </div>

                <div>
                  <label className="text-sm text-gray-500">Created</label>
                  <div className="text-sm">{formatDate(selectedSession.created_at)}</div>
                </div>

                <div>
                  <label className="text-sm text-gray-500">Last Updated</label>
                  <div className="text-sm">{formatDate(selectedSession.updated_at)}</div>
                </div>

                {selectedSession.user_request && (
                  <div>
                    <label className="text-sm text-gray-500">Initial Request</label>
                    <div className="text-sm bg-gray-50 p-2 rounded">
                      {selectedSession.user_request}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400">
              Select a session to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminSessionList;
