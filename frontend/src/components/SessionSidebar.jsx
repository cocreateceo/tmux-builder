import { useState, useEffect } from 'react';
import apiService from '../services/api';

function SessionSidebar({ isOpen, onToggle, currentGuid, onSelectSession, onCreateSession }) {
  const [sessions, setSessions] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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

  // Handle create new session
  const handleCreateNew = async () => {
    try {
      const result = await apiService.createSession();
      if (result.success && result.guid) {
        onCreateSession(result.guid);
        fetchSessions();
      }
    } catch (err) {
      setError('Failed to create session');
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
            </select>
            <button
              onClick={fetchSessions}
              className="text-blue-400 hover:text-blue-300 text-sm"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* New Session Button */}
        <div className="p-3 border-b border-gray-700">
          <button
            onClick={handleCreateNew}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded text-sm font-semibold"
          >
            + New Session
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="p-2 bg-red-900 text-red-200 text-xs">
            {error}
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
                  className={`p-3 cursor-pointer hover:bg-gray-800 ${
                    currentGuid === session.guid ? 'bg-blue-900 border-l-4 border-blue-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-gray-400 truncate max-w-[140px]">
                      {session.guid_short}
                    </span>
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        session.tmux_active
                          ? 'bg-green-900 text-green-300'
                          : 'bg-gray-700 text-gray-400'
                      }`}
                    >
                      {session.tmux_active ? 'Active' : 'Done'}
                    </span>
                  </div>
                  <div className="text-sm text-gray-300 mt-1 truncate">
                    {session.email || 'No email'}
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
