/**
 * Theme Manager for Embed Mode
 * Handles theme persistence, application, and cross-tab sync
 */

import { THEMES, STORAGE_KEY, DEFAULT_THEME, isValidTheme } from './themeConfig';

/**
 * Get stored theme from localStorage
 * @returns {string} Theme ID
 */
export function getStoredTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && isValidTheme(stored)) {
      return stored;
    }
    return DEFAULT_THEME;
  } catch (e) {
    return DEFAULT_THEME;
  }
}

/**
 * Save theme to localStorage
 * @param {string} themeId - Theme ID to save
 */
export function saveTheme(themeId) {
  if (!isValidTheme(themeId)) {
    console.warn(`Invalid theme: ${themeId}`);
    return;
  }
  try {
    localStorage.setItem(STORAGE_KEY, themeId);
  } catch (e) {
    console.warn('Could not save theme to localStorage');
  }
}

/**
 * Apply theme CSS variables to document root
 * @param {string} themeId - Theme ID to apply
 * @returns {object|null} Theme object or null if invalid
 */
export function applyTheme(themeId) {
  const theme = THEMES[themeId] || THEMES[DEFAULT_THEME];
  if (!theme) return null;

  const root = document.documentElement;

  // Set data-theme attribute for CSS selectors
  root.setAttribute('data-theme', themeId);

  // Apply CSS variables
  Object.entries(theme.colors).forEach(([property, value]) => {
    root.style.setProperty(property, value);
  });

  // Dispatch event for other components
  window.dispatchEvent(new CustomEvent('themechange', {
    detail: {
      theme: themeId,
      colors: theme.colors,
      type: theme.type,
      name: theme.name
    }
  }));

  return theme;
}

/**
 * Set theme (save and apply)
 * @param {string} themeId - Theme ID to set
 */
export function setTheme(themeId) {
  if (!isValidTheme(themeId)) {
    console.warn(`Unknown theme: ${themeId}`);
    return;
  }
  saveTheme(themeId);
  applyTheme(themeId);
}

/**
 * Initialize theme from URL param or localStorage
 * @param {string|null} urlTheme - Theme from URL parameter
 * @returns {string} Applied theme ID
 */
export function initTheme(urlTheme = null) {
  // URL param takes priority
  if (urlTheme && isValidTheme(urlTheme)) {
    saveTheme(urlTheme);
    applyTheme(urlTheme);
    return urlTheme;
  }

  // Fall back to stored theme
  const storedTheme = getStoredTheme();
  applyTheme(storedTheme);
  return storedTheme;
}

/**
 * Get current theme info
 * @returns {object} Theme info with id and all properties
 */
export function getCurrentTheme() {
  const themeId = getStoredTheme();
  const theme = THEMES[themeId] || THEMES[DEFAULT_THEME];
  return {
    id: themeId,
    ...theme
  };
}

/**
 * Check if current theme is light mode
 * @returns {boolean}
 */
export function isLightTheme() {
  const theme = getCurrentTheme();
  return theme.type === 'light';
}

/**
 * Subscribe to storage events for cross-tab sync
 * @param {function} callback - Called with new theme ID when theme changes
 * @returns {function} Cleanup function to remove listener
 */
export function subscribeToThemeChanges(callback) {
  const handler = (e) => {
    if (e.key === STORAGE_KEY && e.newValue && isValidTheme(e.newValue)) {
      applyTheme(e.newValue);
      callback(e.newValue);
    }
  };

  window.addEventListener('storage', handler);
  return () => window.removeEventListener('storage', handler);
}
