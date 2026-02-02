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
  },
  coral: {
    name: 'Coral',
    icon: '🪸',
    description: 'Soft warm light',
    type: 'light',
    colors: {
      '--bg-primary': '#FFF8F0',
      '--bg-secondary': '#FFEEE0',
      '--bg-card': 'rgba(255, 255, 255, 0.85)',
      '--text-primary': '#1A0A00',
      '--text-secondary': '#5C3D2E',
      '--text-muted': '#8B6B5A',
      '--border-color': 'rgba(232, 90, 79, 0.2)',
      '--primary': '#FC2A0D',
      '--secondary': '#FD6C71',
      '--accent': '#E85A4F',
      '--glow-color': 'rgba(253, 108, 113, 0.25)'
    }
  },
  sunset: {
    name: 'Sunset',
    icon: '🌅',
    description: 'Vibrant pink-orange',
    type: 'dark',
    colors: {
      '--bg-primary': '#2D1B3D',
      '--bg-secondary': '#3D2650',
      '--bg-card': 'rgba(61, 38, 80, 0.85)',
      '--text-primary': '#FFF5F8',
      '--text-secondary': '#E6C4D4',
      '--text-muted': '#B8919F',
      '--border-color': 'rgba(255, 107, 157, 0.25)',
      '--primary': '#FF6B9D',
      '--secondary': '#FFC36A',
      '--accent': '#C084FC',
      '--glow-color': 'rgba(255, 107, 157, 0.35)'
    }
  },
  aurora: {
    name: 'Aurora',
    icon: '✨',
    description: 'Soft dreamy pastels',
    type: 'light',
    colors: {
      '--bg-primary': '#FFF5F8',
      '--bg-secondary': '#FFEEF4',
      '--bg-card': 'rgba(255, 255, 255, 0.8)',
      '--text-primary': '#2D1B3D',
      '--text-secondary': '#5C4268',
      '--text-muted': '#8B7196',
      '--border-color': 'rgba(230, 164, 255, 0.25)',
      '--primary': '#E6A4FF',
      '--secondary': '#FFB6C1',
      '--accent': '#FFC36A',
      '--glow-color': 'rgba(230, 164, 255, 0.3)'
    }
  },
  sandstone: {
    name: 'Sandstone',
    icon: '🏜️',
    description: 'Warm desert beige',
    type: 'light',
    colors: {
      '--bg-primary': '#FAF6F1',
      '--bg-secondary': '#F0E8DC',
      '--bg-card': 'rgba(255, 255, 255, 0.85)',
      '--text-primary': '#3D2B1F',
      '--text-secondary': '#6B5344',
      '--text-muted': '#9C8575',
      '--border-color': 'rgba(156, 133, 117, 0.25)',
      '--primary': '#FC2A0D',
      '--secondary': '#FD6C71',
      '--accent': '#E07B39',
      '--glow-color': 'rgba(224, 123, 57, 0.25)'
    }
  },
  champagne: {
    name: 'Champagne',
    icon: '🥂',
    description: 'Soft golden cream',
    type: 'light',
    colors: {
      '--bg-primary': '#FFFDF8',
      '--bg-secondary': '#FFF8E7',
      '--bg-card': 'rgba(255, 255, 255, 0.88)',
      '--text-primary': '#2D1F0E',
      '--text-secondary': '#5C4A2E',
      '--text-muted': '#8B7355',
      '--border-color': 'rgba(212, 165, 53, 0.2)',
      '--primary': '#FC2A0D',
      '--secondary': '#FD6C71',
      '--accent': '#D4A535',
      '--glow-color': 'rgba(212, 165, 53, 0.25)'
    }
  },
  zoom: {
    name: 'Zoom',
    icon: '💼',
    description: 'Clean professional blue',
    type: 'light',
    colors: {
      '--bg-primary': '#FFFFFF',
      '--bg-secondary': '#F3F8FF',
      '--bg-card': 'rgba(255, 255, 255, 0.92)',
      '--text-primary': '#00053D',
      '--text-secondary': '#696B6E',
      '--text-muted': '#8B8D91',
      '--border-color': 'rgba(11, 92, 255, 0.15)',
      '--primary': '#0B5CFF',
      '--secondary': '#6CB0FF',
      '--accent': '#8D5DF7',
      '--glow-color': 'rgba(11, 92, 255, 0.25)'
    }
  },
  legacy: {
    name: 'Legacy',
    icon: '💎',
    description: 'Classic dark mode',
    type: 'dark',
    colors: {
      '--bg-primary': '#020617',
      '--bg-secondary': '#0f172a',
      '--bg-card': 'rgba(15, 23, 42, 0.7)',
      '--text-primary': '#f1f5f9',
      '--text-secondary': '#94a3b8',
      '--text-muted': '#64748b',
      '--border-color': 'rgba(99, 102, 241, 0.2)',
      '--primary': '#6366f1',
      '--secondary': '#8b5cf6',
      '--accent': '#06b6d4',
      '--glow-color': 'rgba(99, 102, 241, 0.3)'
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
