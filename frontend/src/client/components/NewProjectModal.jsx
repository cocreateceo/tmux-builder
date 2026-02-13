import { useState } from 'react';
import { X, Sparkles, User, Mail, Phone, AlertCircle } from 'lucide-react';

const QUICK_STARTS = [
  { label: 'Landing Page', icon: '🎨', prompt: 'Build me a beautiful landing page with hero, features, pricing, and testimonials sections' },
  { label: 'Dashboard', icon: '📊', prompt: 'Create an admin dashboard with charts, tables, and sidebar navigation' },
  { label: 'API Backend', icon: '⚡', prompt: 'Build a REST API backend with authentication, CRUD operations, and database integration' },
  { label: 'Mobile App', icon: '📱', prompt: 'Create a mobile-responsive web app with native-like navigation and gestures' },
];

export function NewProjectModal({ isOpen, onClose, onCreate, client }) {
  const [request, setRequest] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!request.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await onCreate(request.trim());
      setRequest('');
      setError(null);
      onClose();
    } catch (err) {
      console.error('Failed to create project:', err);
      setError(err.message || 'Failed to create project. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickStart = (prompt) => {
    setRequest(prompt);
    setError(null);
  };

  const handleClose = () => {
    setError(null);
    setRequest('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg rounded-xl shadow-2xl border"
        style={{ background: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between p-4 border-b"
          style={{ borderColor: 'var(--border-color)' }}
        >
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            Start New Project
          </h2>
          <button
            onClick={handleClose}
            className="p-1 rounded-lg hover:opacity-80"
          >
            <X className="w-5 h-5" style={{ color: 'var(--text-muted)' }} />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Client info (read-only) */}
          {client && (
            <div
              className="grid grid-cols-1 gap-3 p-3 rounded-lg border"
              style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-color)' }}
            >
              <div className="flex items-center gap-2">
                <User className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Name:</span>
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {client.name || 'N/A'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Email:</span>
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {client.email || 'N/A'}
                </span>
              </div>
              {client.phone && (
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                  <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Phone:</span>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {client.phone}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-500">{error}</p>
            </div>
          )}

          {/* Text input */}
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
              What do you want to build?
            </label>
            <textarea
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="Describe your project in detail..."
              rows={4}
              className="w-full px-3 py-2 text-sm rounded-lg border resize-none focus:outline-none"
              style={{
                background: 'var(--bg-primary)',
                borderColor: 'var(--border-color)',
                color: 'var(--text-primary)'
              }}
              autoFocus
            />
          </div>

          {/* Quick starts */}
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
              Quick starts
            </label>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_STARTS.map((qs) => (
                <button
                  key={qs.label}
                  type="button"
                  onClick={() => handleQuickStart(qs.prompt)}
                  className="p-3 text-left rounded-lg border transition-colors hover:opacity-80"
                  style={{ borderColor: 'var(--border-color)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{qs.icon}</span>
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {qs.label}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium rounded-lg hover:opacity-80"
              style={{ color: 'var(--text-secondary)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!request.trim() || loading}
              className="px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: 'var(--primary)' }}
            >
              <Sparkles className="w-4 h-4" />
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
