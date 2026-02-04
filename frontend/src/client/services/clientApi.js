import axios from 'axios';

// Auto-detect production vs development
// Production: any non-localhost hostname (CloudFront, custom domain, etc.)
const isLocalhost = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const API_BASE = isLocalhost
  ? (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  : `${window.location.protocol}//${window.location.host}`;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const clientApi = {
  // Get all projects for a client
  async getProjects(email = null, guid = null) {
    const params = new URLSearchParams();
    if (email) params.append('email', email);
    if (guid) params.append('guid', guid);
    const response = await api.get(`/api/client/projects?${params}`);
    return response.data;
  },

  // Create a new project
  async createProject(email, initialRequest, name = null) {
    const response = await api.post('/api/client/projects', {
      email,
      initial_request: initialRequest,
      name,
    });
    return response.data;
  },

  // Update project (rename, archive)
  async updateProject(guid, updates) {
    const response = await api.patch(`/api/client/projects/${guid}`, updates);
    return response.data;
  },

  // Duplicate a project
  async duplicateProject(guid) {
    const response = await api.post(`/api/client/projects/${guid}/duplicate`);
    return response.data;
  },

  // Get chat history for a project
  async getChatHistory(guid) {
    const response = await api.get(`/api/history?guid=${guid}`);
    return response.data;
  },

  // Send a message
  async sendMessage(guid, message) {
    const response = await api.post('/api/chat', { guid, message });
    return response.data;
  },
};

export default clientApi;
