/**
 * Theme Configuration for Embed Mode
 * Matches AI Product Studio theme system for cross-site consistency
 */

export const THEMES = {
  ember: {
    name: 'Ember',
    icon: '🔥',
    description: 'Deep amber warmth',
    type: 'dark',
    colors: {
      '--bg-primary': '#1A0A00',
      '--bg-secondary': '#2D1408',
      '--bg-card': 'rgba(45, 20, 8, 0.85)',
      '--text-primary': '#FFF8F0',
      '--text-secondary': '#FFCBA4',
      '--text-muted': '#C4916C',
      '--border-color': 'rgba(252, 42, 13, 0.25)',
      '--primary': '#FC2A0D',
      '--secondary': '#FD6C71',
      '--accent': '#FFC36A',
      '--glow-color': 'rgba(252, 42, 13, 0.35)'
    }
  }
};

export const STORAGE_KEY = 'cocreate-theme';
export const DEFAULT_THEME = 'ember';

/**
 * Get list of all available themes
 */
export function getThemeList() {
  return Object.entries(THEMES).map(([id, theme]) => ({
    id,
    name: theme.name,
    icon: theme.icon,
    description: theme.description,
    type: theme.type
  }));
}

/**
 * Check if a theme ID is valid
 */
export function isValidTheme(themeId) {
  return themeId && Object.hasOwn(THEMES, themeId);
}
