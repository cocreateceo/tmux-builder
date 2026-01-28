import { useState, useEffect } from 'react';
import apiService from '../services/api';

function SessionSidebar({ isOpen, onToggle, currentGuid, onSelectSession, onCreateSession }) {
  const [sessions, setSessions] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [openMenuGuid, setOpenMenuGuid] = useState(null);

  // New Session Form State
  const [showNewForm, setShowNewForm] = useState(false);
  const [newSessionData, setNewSessionData] = useState({
    name: '',
    email: '',
    phone: '',
    initial_request: ''
  });
  const [creating, setCreating] = useState(false);

  // Fetch sessions
  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiService.listSessions(filter);
      setSessions(result.sessions || []);
    } catch (err) {
      setError('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchSessions();
    }
  }, [isOpen, filter]);

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString();
    } catch {
      return '';
    }
  };

  // Handle create new session with form
  const handleCreateNew = async (e) => {
    e.preventDefault();

    if (!newSessionData.name.trim() || !newSessionData.email.trim()) {
      setError('Name and Email are required');
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const result = await apiService.createSessionWithDetails(newSessionData);
      if (result.success && result.guid) {
        onCreateSession(result.guid);
        fetchSessions();
        setShowNewForm(false);
        setNewSessionData({ name: '', email: '', phone: '', initial_request: '' });
      } else {
        setError(result.error || 'Failed to create session');
      }
    } catch (err) {
      setError('Failed to create session');
    } finally {
      setCreating(false);
    }
  };

  // Toggle menu for a session
  const toggleMenu = (e, guid) => {
    e.stopPropagation();
    setOpenMenuGuid(openMenuGuid === guid ? null : guid);
  };

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setOpenMenuGuid(null);
    if (openMenuGuid) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [openMenuGuid]);

  // Handle complete session (kill tmux)
  const handleCompleteSession = async (e, guid) => {
    e.stopPropagation();
    setOpenMenuGuid(null);
    try {
      await apiService.completeSession(guid);
      fetchSessions();
    } catch (err) {
      setError('Failed to complete session');
    }
  };

  // Handle delete session
  const handleDeleteSession = async (e, guid) => {
    e.stopPropagation();
    setOpenMenuGuid(null);
    if (!confirm(`Delete session ${guid.substring(0, 12)}...?`)) {
      return;
    }
    try {
      await apiService.deleteSession(guid);
      fetchSessions();
      if (currentGuid === guid) {
        onSelectSession(null);
      }
    } catch (err) {
      setError('Failed to delete session');
    }
  };

  // Handle restore session
  const handleRestoreSession = async (e, guid) => {
    e.stopPropagation();
    setOpenMenuGuid(null);
    try {
      await apiService.restoreSession(guid);
      fetchSessions();
    } catch (err) {
      setError('Failed to restore session');
    }
  };

  return (
    <>
      {/* Toggle button - always visible */}
      <button
        onClick={onToggle}
        className="fixed left-0 top-1/2 -translate-y-1/2 z-50 bg-gray-800 text-white p-2 rounded-r-lg shadow-lg hover:bg-gray-700 transition-all"
        style={{ left: isOpen ? '280px' : '0' }}
      >
        {isOpen ? (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        )}
      </button>

      {/* Sidebar */}
      <div
        className={`fixed left-0 top-0 h-full bg-gray-900 text-white z-40 transition-all duration-300 flex flex-col ${
          isOpen ? 'w-72' : 'w-0'
        } overflow-hidden`}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-700">
          <h2 className="font-bold text-lg">Sessions</h2>
          <div className="flex items-center gap-2 mt-2">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm"
            >
              <option value="all">All</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="deleted">Deleted</option>
            </select>
            <button
              onClick={fetchSessions}
              className="text-blue-400 hover:text-blue-300 text-sm"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* New Session Button / Form */}
        <div className="p-3 border-b border-gray-700">
          {!showNewForm ? (
            <button
              onClick={() => setShowNewForm(true)}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded text-sm font-semibold"
            >
              + New Session
            </button>
          ) : (
            <form onSubmit={handleCreateNew} className="space-y-2">
              <div className="text-sm font-semibold text-gray-300 mb-2">Create New Session</div>

              <input
                type="text"
                placeholder="Name *"
                value={newSessionData.name}
                onChange={(e) => setNewSessionData({ ...newSessionData, name: e.target.value })}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                required
              />

              <input
                type="email"
                placeholder="Email *"
                value={newSessionData.email}
                onChange={(e) => setNewSessionData({ ...newSessionData, email: e.target.value })}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                required
              />

              <input
                type="tel"
                placeholder="Phone (optional)"
                value={newSessionData.phone}
                onChange={(e) => setNewSessionData({ ...newSessionData, phone: e.target.value })}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none"
              />

              <textarea
                placeholder="Initial Request (optional)"
                value={newSessionData.initial_request}
                onChange={(e) => setNewSessionData({ ...newSessionData, initial_request: e.target.value })}
                rows={3}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none resize-none"
              />

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowNewForm(false);
                    setNewSessionData({ name: '', email: '', phone: '', initial_request: '' });
                  }}
                  className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded text-sm"
                  disabled={creating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded text-sm font-semibold disabled:opacity-50"
                  disabled={creating}
                >
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="p-2 bg-red-900 text-red-200 text-xs">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">×</button>
          </div>
        )}

        {/* Session List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-gray-500">Loading...</div>
          ) : sessions.length === 0 ? (
            <div className="p-4 text-center text-gray-500">No sessions</div>
          ) : (
            <div className="divide-y divide-gray-700">
              {sessions.map((session) => (
                <div
                  key={session.guid}
                  onClick={() => onSelectSession(session.guid)}
                  className={`p-3 cursor-pointer hover:bg-gray-800 group relative ${
                    currentGuid === session.guid ? 'bg-blue-900 border-l-4 border-blue-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-gray-400 truncate max-w-[120px]">
                      {session.guid_short}
                    </span>
                    <div className="flex items-center gap-1">
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          session.tmux_active
                            ? 'bg-green-900 text-green-300'
                            : filter === 'deleted'
                              ? 'bg-red-900 text-red-300'
                              : 'bg-gray-700 text-gray-400'
                        }`}
                      >
                        {filter === 'deleted' ? 'Deleted' : session.tmux_active ? 'Active' : 'Done'}
                      </span>
                      {/* Menu button */}
                      <button
                        onClick={(e) => toggleMenu(e, session.guid)}
                        className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-white p-0.5 transition-opacity"
                        title="Session actions"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Dropdown menu */}
                  {openMenuGuid === session.guid && (
                    <div className="absolute right-2 top-8 bg-gray-800 border border-gray-600 rounded shadow-lg z-50 min-w-[120px]">
                      {filter === 'deleted' ? (
                        // Deleted session options
                        <button
                          onClick={(e) => handleRestoreSession(e, session.guid)}
                          className="w-full px-3 py-2 text-left text-sm text-green-400 hover:bg-gray-700 flex items-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                          </svg>
                          Restore
                        </button>
                      ) : (
                        // Active/Completed session options
                        <>
                          {session.tmux_active && (
                            <button
                              onClick={(e) => handleCompleteSession(e, session.guid)}
                              className="w-full px-3 py-2 text-left text-sm text-yellow-400 hover:bg-gray-700 flex items-center gap-2"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              Complete
                            </button>
                          )}
                          <button
                            onClick={(e) => handleDeleteSession(e, session.guid)}
                            className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-gray-700 flex items-center gap-2"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  )}

                  <div className="text-sm text-gray-300 mt-1 truncate">
                    {session.client_name || session.email || 'No email'}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                    <span>{session.chat_message_count} msgs</span>
                    <span>{formatDate(session.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Current Session Info */}
        {currentGuid && (
          <div className="p-3 border-t border-gray-700 bg-gray-800">
            <div className="text-xs text-gray-400">Current:</div>
            <div className="font-mono text-xs text-blue-400 truncate">
              {currentGuid.substring(0, 16)}...
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default SessionSidebar;
