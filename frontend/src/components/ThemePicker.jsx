import React, { useState, useRef, useEffect } from 'react';
import { getThemeList, THEMES } from '../themes/themeConfig';
import { setTheme } from '../themes/ThemeManager';

/**
 * ThemePicker - Dropdown theme selector for embed mode
 */
export default function ThemePicker({ currentTheme, onThemeChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const themes = getThemeList();

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close on escape key
  useEffect(() => {
    function handleEscape(event) {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen]);

  const handleThemeSelect = (themeId) => {
    setTheme(themeId);
    onThemeChange(themeId);
    setIsOpen(false);
  };

  const currentThemeData = THEMES[currentTheme] || THEMES.ember;

  return (
    <div className="theme-picker" ref={dropdownRef}>
      <button
        className="theme-picker-button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span>{currentThemeData.icon}</span>
        <span>{currentThemeData.name}</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease'
          }}
        >
          <path
            d="M2.5 4.5L6 8L9.5 4.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="theme-picker-dropdown" role="listbox">
          {themes.map((theme) => (
            <div
              key={theme.id}
              className={`theme-picker-option ${theme.id === currentTheme ? 'active' : ''}`}
              onClick={() => handleThemeSelect(theme.id)}
              role="option"
              aria-selected={theme.id === currentTheme}
            >
              <div
                className="theme-color-preview"
                style={{
                  background: `linear-gradient(135deg, ${THEMES[theme.id].colors['--primary']} 0%, ${THEMES[theme.id].colors['--secondary']} 100%)`
                }}
              />
              <div>
                <div className="theme-picker-name">
                  {theme.icon} {theme.name}
                </div>
                <div className="theme-picker-desc">{theme.description}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
