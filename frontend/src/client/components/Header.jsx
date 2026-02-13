import { useState, useEffect, useRef } from 'react';
import { Bell, ChevronDown } from 'lucide-react';
import { THEMES, STORAGE_KEY, DEFAULT_THEME } from '../../themes/themeConfig';
import { setTheme, getStoredTheme, applyTheme, saveTheme } from '../../themes/ThemeManager';

export function Header({ client, connected, guid }) {
  const [currentTheme, setCurrentTheme] = useState(DEFAULT_THEME);
  const [showThemeDropdown, setShowThemeDropdown] = useState(false);
  const dropdownRef = useRef(null);

  // Load saved theme on mount
  useEffect(() => {
    setCurrentTheme(getStoredTheme());
  }, []);

  // Apply theme from backend when client data loads
  useEffect(() => {
    if (client?.theme && THEMES[client.theme]) {
      saveTheme(client.theme); // Save to localStorage
      applyTheme(client.theme);
      setCurrentTheme(client.theme);
    }
  }, [client?.theme]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowThemeDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleThemeChange = async (themeId) => {
    setTheme(themeId);
    setCurrentTheme(themeId);
    setShowThemeDropdown(false);

    // Save to backend
    if (guid) {
      try {
        const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
          ? 'http://localhost:8000'
          : `${window.location.protocol}//${window.location.host}`;

        await fetch(`${API_BASE}/api/client/save-theme`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ guid, theme: themeId })
        });
      } catch (e) {
        console.warn('Could not save theme to backend:', e);
      }
    }
  };

  const theme = THEMES[currentTheme] || THEMES[DEFAULT_THEME];

  return (
    <header
      className="h-14 px-4 flex items-center justify-between border-b"
      style={{
        background: 'var(--bg-card)',
        borderColor: 'var(--border-color)',
        backdropFilter: 'blur(20px)'
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        {/* CoCreate Logo */}
        <img
          src="/assets/logo.png"
          alt="CoCreate"
          className="w-10 h-10"
        />
        <span className="font-semibold text-lg">
          <span style={{ color: 'var(--text-primary)' }}>CO</span>
          <span style={{ color: 'var(--primary)' }}>CREATE</span>
          <span style={{ color: 'var(--text-muted)' }} className="ml-1 font-normal">Agent</span>
        </span>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 ml-4">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Theme Selector */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setShowThemeDropdown(!showThemeDropdown)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors hover:opacity-80"
            style={{
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)'
            }}
          >
            <span>{theme.icon}</span>
            <span className="text-sm">{theme.name}</span>
            <ChevronDown className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
          </button>

          {/* Dropdown */}
          {showThemeDropdown && (
            <div
              className="absolute right-0 top-full mt-2 py-2 rounded-lg shadow-lg z-50 min-w-[160px]"
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)'
              }}
            >
              {Object.entries(THEMES).map(([id, t]) => (
                <button
                  key={id}
                  onClick={() => handleThemeChange(id)}
                  className={`w-full flex items-center gap-3 px-4 py-2 text-left transition-colors hover:opacity-80 ${
                    id === currentTheme ? 'opacity-100' : 'opacity-70'
                  }`}
                  style={{
                    background: id === currentTheme ? 'var(--bg-secondary)' : 'transparent',
                    color: 'var(--text-primary)'
                  }}
                >
                  <span>{t.icon}</span>
                  <span className="text-sm">{t.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Notifications */}
        <button
          className="p-2 rounded-lg transition-colors relative hover:opacity-80"
          style={{ color: 'var(--text-muted)' }}
        >
          <Bell className="w-5 h-5" />
        </button>

        {/* User */}
        {client && (
          <div
            className="flex items-center gap-2 pl-3 border-l"
            style={{ borderColor: 'var(--border-color)' }}
          >
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center overflow-hidden"
              style={{ background: 'var(--primary)' }}
            >
              {client.avatarUrl ? (
                <img
                  src={client.avatarUrl}
                  alt="Profile"
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-white text-sm font-medium">
                  {client.name?.[0]?.toUpperCase() || client.email?.[0]?.toUpperCase() || '?'}
                </span>
              )}
            </div>
            <span
              className="text-sm max-w-[120px] truncate"
              style={{ color: 'var(--text-secondary)' }}
            >
              {client.name || client.email}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
