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
  const [fieldErrors, setFieldErrors] = useState({});

  // Validation functions
  const validateName = (name) => {
    if (!name.trim()) return 'Name is required';
    if (!/^[a-zA-Z\s]+$/.test(name)) return 'Name should only contain letters and spaces';
    if (name.trim().length < 2) return 'Name must be at least 2 characters';
    return null;
  };

  const validateEmail = (email) => {
    if (!email.trim()) return 'Email is required';
    // Full email validation: user@domain.extension
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(email)) return 'Please enter a valid email (e.g., name@example.com)';
    return null;
  };

  const validatePhone = (phone) => {
    if (!phone.trim()) return 'Phone number is required';
    // Remove non-digits for counting
    const digitsOnly = phone.replace(/\D/g, '');
    if (digitsOnly.length < 7) return 'Phone number must have at least 7 digits';
    if (digitsOnly.length > 15) return 'Phone number is too long';
    return null;
  };

  const validateField = (name, value) => {
    switch (name) {
      case 'name': return validateName(value);
      case 'email': return validateEmail(value);
      case 'phone': return validatePhone(value);
      default: return null;
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));

    // Clear field error when user starts typing
    if (fieldErrors[name]) {
      setFieldErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const handleBlur = (e) => {
    const { name, value } = e.target;
    const error = validateField(name, value);
    if (error) {
      setFieldErrors(prev => ({ ...prev, [name]: error }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate all fields
    const errors = {
      name: validateName(formData.name),
      email: validateEmail(formData.email),
      phone: validatePhone(formData.phone),
    };

    // Check if any errors exist
    const hasErrors = Object.values(errors).some(err => err !== null);
    if (hasErrors) {
      setFieldErrors(errors);
      return;
    }

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
                      onBlur={handleBlur}
                      required
                      placeholder="John Doe"
                      className={`w-full pl-10 pr-4 py-3 rounded-xl border
                        dark:bg-[#0a0a0f] dark:text-white
                        bg-gray-50 text-gray-900
                        focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                        placeholder:dark:text-gray-600 placeholder:text-gray-400
                        ${fieldErrors.name
                          ? 'border-red-500 dark:border-red-500'
                          : 'dark:border-gray-700 border-gray-200'}`}
                    />
                  </div>
                  {fieldErrors.name && (
                    <p className="mt-1 text-sm text-red-500">{fieldErrors.name}</p>
                  )}
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
                      onBlur={handleBlur}
                      required
                      placeholder="john@example.com"
                      className={`w-full pl-10 pr-4 py-3 rounded-xl border
                        dark:bg-[#0a0a0f] dark:text-white
                        bg-gray-50 text-gray-900
                        focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                        placeholder:dark:text-gray-600 placeholder:text-gray-400
                        ${fieldErrors.email
                          ? 'border-red-500 dark:border-red-500'
                          : 'dark:border-gray-700 border-gray-200'}`}
                    />
                  </div>
                  {fieldErrors.email && (
                    <p className="mt-1 text-sm text-red-500">{fieldErrors.email}</p>
                  )}
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
                      onBlur={handleBlur}
                      required
                      placeholder="+1-555-123-4567"
                      className={`w-full pl-10 pr-4 py-3 rounded-xl border
                        dark:bg-[#0a0a0f] dark:text-white
                        bg-gray-50 text-gray-900
                        focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                        placeholder:dark:text-gray-600 placeholder:text-gray-400
                        ${fieldErrors.phone
                          ? 'border-red-500 dark:border-red-500'
                          : 'dark:border-gray-700 border-gray-200'}`}
                    />
                  </div>
                  {fieldErrors.phone && (
                    <p className="mt-1 text-sm text-red-500">{fieldErrors.phone}</p>
                  )}
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
