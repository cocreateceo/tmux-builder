import React, { useState, useRef, useEffect } from 'react';
import { getThemeList, THEMES, isValidTheme } from '../themes/themeConfig';
import { setTheme } from '../themes/ThemeManager';

/**
 * ThemePicker - Dropdown theme selector for embed mode
 */
export default function ThemePicker({ currentTheme, onThemeChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const dropdownRef = useRef(null);
  const optionRefs = useRef([]);
  const themes = getThemeList();

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setFocusedIndex(-1);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle keyboard navigation
  useEffect(() => {
    function handleKeyDown(event) {
      if (!isOpen) return;

      switch (event.key) {
        case 'Escape':
          setIsOpen(false);
          setFocusedIndex(-1);
          break;
        case 'ArrowDown':
          event.preventDefault();
          setFocusedIndex((prev) => {
            const next = prev < themes.length - 1 ? prev + 1 : 0;
            optionRefs.current[next]?.focus();
            return next;
          });
          break;
        case 'ArrowUp':
          event.preventDefault();
          setFocusedIndex((prev) => {
            const next = prev > 0 ? prev - 1 : themes.length - 1;
            optionRefs.current[next]?.focus();
            return next;
          });
          break;
        case 'Enter':
        case ' ':
          if (focusedIndex >= 0 && focusedIndex < themes.length) {
            event.preventDefault();
            handleThemeSelect(themes[focusedIndex].id);
          }
          break;
        case 'Tab':
          setIsOpen(false);
          setFocusedIndex(-1);
          break;
        default:
          break;
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, focusedIndex, themes]);

  // Focus first option when dropdown opens
  useEffect(() => {
    if (isOpen && themes.length > 0) {
      const currentIndex = themes.findIndex((t) => t.id === currentTheme);
      const initialIndex = currentIndex >= 0 ? currentIndex : 0;
      setFocusedIndex(initialIndex);
      setTimeout(() => optionRefs.current[initialIndex]?.focus(), 0);
    }
  }, [isOpen, currentTheme, themes]);

  const handleThemeSelect = (themeId) => {
    if (!isValidTheme(themeId)) {
      console.warn(`Invalid theme selection: ${themeId}`);
      return;
    }
    setTheme(themeId);
    onThemeChange(themeId);
    setIsOpen(false);
    setFocusedIndex(-1);
  };

  const handleOptionKeyDown = (event, themeId) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleThemeSelect(themeId);
    }
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
          {themes.map((theme, index) => (
            <div
              key={theme.id}
              ref={(el) => (optionRefs.current[index] = el)}
              className={`theme-picker-option ${theme.id === currentTheme ? 'active' : ''}`}
              onClick={() => handleThemeSelect(theme.id)}
              onKeyDown={(e) => handleOptionKeyDown(e, theme.id)}
              role="option"
              aria-selected={theme.id === currentTheme}
              tabIndex={0}
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
