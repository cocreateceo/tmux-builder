import { useState } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { useTheme } from './hooks/useTheme';
import { Sun, Moon, Rocket, Mail, Phone, User, MessageSquare } from 'lucide-react';

function OnboardingForm() {
  const { theme, toggleTheme } = useTheme();
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    initial_request: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/admin/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      // Check if response is ok before parsing JSON
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.error || `Server error: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.guid) {
        // Redirect to client dashboard with the new guid
        window.location.href = `/client?guid=${data.guid}`;
      } else {
        setError(data.error || data.detail || 'Failed to create session');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`min-h-screen flex flex-col ${theme === 'dark' ? 'dark' : ''}`}>
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100
        dark:from-[#0a0a0f] dark:to-[#12121a] transition-colors">

        {/* Header */}
        <header className="h-16 px-6 flex items-center justify-between border-b
          dark:border-gray-800 border-gray-200 bg-white/50 dark:bg-[#0a0a0f]/50 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600
              flex items-center justify-center">
              <Rocket className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold dark:text-white text-gray-900">
              AI Builder
            </span>
          </div>
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg dark:hover:bg-gray-800 hover:bg-gray-100
              dark:text-gray-400 text-gray-500 transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </header>

        {/* Main Content */}
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-md">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold dark:text-white text-gray-900 mb-2">
                Start Your Project
              </h1>
              <p className="dark:text-gray-400 text-gray-600">
                Tell us about yourself and what you want to build
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="bg-white dark:bg-[#12121a] rounded-2xl p-6 shadow-xl
                dark:shadow-black/20 border dark:border-gray-800 border-gray-200">

                {/* Name */}
                <div className="mb-4">
                  <label className="block text-sm font-medium dark:text-gray-300 text-gray-700 mb-2">
                    Your Name
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5
                      dark:text-gray-500 text-gray-400" />
                    <input
                      type="text"
                      name="name"
                      value={formData.name}
                      onChange={handleChange}
                      required
                      placeholder="John Doe"
                      className="w-full pl-10 pr-4 py-3 rounded-xl border
                        dark:bg-[#0a0a0f] dark:border-gray-700 dark:text-white
                        bg-gray-50 border-gray-200 text-gray-900
                        focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                        placeholder:dark:text-gray-600 placeholder:text-gray-400"
                    />
                  </div>
                </div>

                {/* Email */}
                <div className="mb-4">
                  <label className="block text-sm font-medium dark:text-gray-300 text-gray-700 mb-2">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5
                      dark:text-gray-500 text-gray-400" />
                    <input
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleChange}
                      required
                      placeholder="john@example.com"
                      className="w-full pl-10 pr-4 py-3 rounded-xl border
                        dark:bg-[#0a0a0f] dark:border-gray-700 dark:text-white
                        bg-gray-50 border-gray-200 text-gray-900
                        focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                        placeholder:dark:text-gray-600 placeholder:text-gray-400"
                    />
                  </div>
                </div>

                {/* Phone */}
                <div className="mb-4">
                  <label className="block text-sm font-medium dark:text-gray-300 text-gray-700 mb-2">
                    Phone Number
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5
                      dark:text-gray-500 text-gray-400" />
                    <input
                      type="tel"
                      name="phone"
                      value={formData.phone}
                      onChange={handleChange}
                      required
                      placeholder="+1-555-123-4567"
                      className="w-full pl-10 pr-4 py-3 rounded-xl border
                        dark:bg-[#0a0a0f] dark:border-gray-700 dark:text-white
                        bg-gray-50 border-gray-200 text-gray-900
                        focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                        placeholder:dark:text-gray-600 placeholder:text-gray-400"
                    />
                  </div>
                </div>

                {/* Initial Request */}
                <div>
                  <label className="block text-sm font-medium dark:text-gray-300 text-gray-700 mb-2">
                    What do you want to build?
                  </label>
                  <div className="relative">
                    <MessageSquare className="absolute left-3 top-3 w-5 h-5
                      dark:text-gray-500 text-gray-400" />
                    <textarea
                      name="initial_request"
                      value={formData.initial_request}
                      onChange={handleChange}
                      required
                      rows={4}
                      placeholder="I need help building a landing page for my SaaS product..."
                      className="w-full pl-10 pr-4 py-3 rounded-xl border resize-none
                        dark:bg-[#0a0a0f] dark:border-gray-700 dark:text-white
                        bg-gray-50 border-gray-200 text-gray-900
                        focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                        placeholder:dark:text-gray-600 placeholder:text-gray-400"
                    />
                  </div>
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                  {error}
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 rounded-xl font-semibold text-white
                  bg-gradient-to-r from-indigo-500 to-purple-600
                  hover:from-indigo-600 hover:to-purple-700
                  disabled:opacity-50 disabled:cursor-not-allowed
                  transition-all duration-200 shadow-lg shadow-indigo-500/25
                  flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white border-t-transparent
                      rounded-full animate-spin" />
                    Creating your project...
                  </>
                ) : (
                  <>
                    <Rocket className="w-5 h-5" />
                    Start Building
                  </>
                )}
              </button>
            </form>

            <p className="text-center mt-6 text-sm dark:text-gray-500 text-gray-400">
              Your project will be created and you'll be redirected to the dashboard
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function ClientOnboarding() {
  return (
    <ThemeProvider>
      <OnboardingForm />
    </ThemeProvider>
  );
}
