import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

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
  sendMessage: async (message, screenshot = null, filePath = null) => {
    const response = await api.post('/api/chat', {
      message,
      screenshot,
      filePath,
    });
    return response.data;
  },

  // Get chat history
  getHistory: async () => {
    const response = await api.get('/api/history');
    return response.data;
  },

  // Clear session
  clearSession: async () => {
    const response = await api.post('/api/clear');
    return response.data;
  },
};

export default apiService;
