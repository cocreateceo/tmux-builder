import axios from 'axios';

// Auto-detect production vs development
const isProduction = window.location.hostname.includes('cloudfront.net');
const API_BASE_URL = isProduction
  ? `${window.location.protocol}//${window.location.host}`
  : 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiService = {
  // Create a new session
  createSession: async () => {
    const response = await api.post('/api/session/create');
    return response.data;
  },

  // Get session status
  getStatus: async () => {
    const response = await api.get('/api/status');
    return response.data;
  },

  // Send a message
  sendMessage: async (message, guid = null, screenshot = null, filePath = null) => {
    const response = await api.post('/api/chat', {
      message,
      guid,  // For session re-attachment after server restart
      screenshot,
      filePath,
    });
    return response.data;
  },

  // Get chat history
  getHistory: async (guid = null) => {
    const params = guid ? { guid } : {};
    const response = await api.get('/api/history', { params });
    return response.data;
  },

  // Clear session
  clearSession: async () => {
    const response = await api.post('/api/clear');
    return response.data;
  },

  // ========== ADMIN API ==========

  // List all sessions with metadata
  listSessions: async (filter = 'all') => {
    const response = await api.get('/api/admin/sessions', { params: { filter } });
    return response.data;
  },

  // Create session with custom metadata (legacy)
  createAdminSession: async (email, phone = '', initialRequest = '') => {
    const response = await api.post('/api/admin/sessions', {
      name: 'Admin User',
      email,
      phone: phone || '',
      initial_request: initialRequest,
    });
    return response.data;
  },

  // Create session with full details (name, email, phone, initial_request)
  createSessionWithDetails: async ({ name, email, phone = '', initial_request = '' }) => {
    const response = await api.post('/api/admin/sessions', {
      name,
      email,
      phone: phone || '',
      initial_request: initial_request || '',
    });
    return response.data;
  },

  // Get detailed session info
  getSessionDetails: async (guid) => {
    const response = await api.get(`/api/admin/sessions/${guid}`);
    return response.data;
  },

  // Delete a session (moves to deleted folder)
  deleteSession: async (guid) => {
    const response = await api.delete(`/api/admin/sessions/${guid}`);
    return response.data;
  },

  // Complete a session (kill tmux but keep in active)
  completeSession: async (guid) => {
    const response = await api.post(`/api/admin/sessions/${guid}/complete`);
    return response.data;
  },

  // Restore a deleted session
  restoreSession: async (guid) => {
    const response = await api.post(`/api/admin/sessions/${guid}/restore`);
    return response.data;
  },
};

export default apiService;
