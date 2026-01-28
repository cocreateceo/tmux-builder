import { useState } from 'react';
import { X, Sparkles } from 'lucide-react';

const QUICK_STARTS = [
  { label: 'Landing Page', icon: '🎨', prompt: 'Build me a beautiful landing page with hero, features, pricing, and testimonials sections' },
  { label: 'Dashboard', icon: '📊', prompt: 'Create an admin dashboard with charts, tables, and sidebar navigation' },
  { label: 'API Backend', icon: '⚡', prompt: 'Build a REST API backend with authentication, CRUD operations, and database integration' },
  { label: 'Mobile App', icon: '📱', prompt: 'Create a mobile-responsive web app with native-like navigation and gestures' },
];

export function NewProjectModal({ isOpen, onClose, onCreate }) {
  const [request, setRequest] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!request.trim()) return;

    setLoading(true);
    try {
      await onCreate(request.trim());
      setRequest('');
      onClose();
    } catch (err) {
      console.error('Failed to create project:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickStart = (prompt) => {
    setRequest(prompt);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg rounded-xl shadow-2xl border
        dark:bg-[#1a1a24] dark:border-gray-700 bg-white border-gray-200">

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b
          dark:border-gray-700 border-gray-200">
          <h2 className="text-lg font-semibold dark:text-white text-gray-900">
            Start New Project
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg dark:hover:bg-gray-700 hover:bg-gray-100"
          >
            <X className="w-5 h-5 dark:text-gray-400 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Text input */}
          <div>
            <label className="block text-sm font-medium mb-2 dark:text-gray-300 text-gray-700">
              What do you want to build?
            </label>
            <textarea
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="Describe your project in detail..."
              rows={4}
              className="w-full px-3 py-2 text-sm rounded-lg border resize-none
                dark:bg-[#12121a] dark:border-gray-700 dark:text-white dark:placeholder-gray-500
                bg-gray-50 border-gray-200 text-gray-900 placeholder-gray-400
                focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              autoFocus
            />
          </div>

          {/* Quick starts */}
          <div>
            <label className="block text-sm font-medium mb-2 dark:text-gray-300 text-gray-700">
              Quick starts
            </label>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_STARTS.map((qs) => (
                <button
                  key={qs.label}
                  type="button"
                  onClick={() => handleQuickStart(qs.prompt)}
                  className="p-3 text-left rounded-lg border transition-colors
                    dark:border-gray-700 dark:hover:border-indigo-500/50 dark:hover:bg-indigo-500/10
                    border-gray-200 hover:border-indigo-300 hover:bg-indigo-50"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{qs.icon}</span>
                    <span className="text-sm font-medium dark:text-white text-gray-900">
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
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium rounded-lg
                dark:text-gray-300 dark:hover:bg-gray-700
                text-gray-700 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!request.trim() || loading}
              className="px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2
                bg-indigo-500 hover:bg-indigo-600 text-white
                disabled:opacity-50 disabled:cursor-not-allowed"
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
