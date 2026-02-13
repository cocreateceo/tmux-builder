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
    description: 'Ocean coral vibes',
    type: 'dark',
    colors: {
      '--bg-primary': '#1A0A0A',
      '--bg-secondary': '#2D1414',
      '--bg-card': 'rgba(45, 20, 20, 0.85)',
      '--text-primary': '#FFF0F0',
      '--text-secondary': '#FFB4B4',
      '--text-muted': '#C47070',
      '--border-color': 'rgba(255, 127, 80, 0.25)',
      '--primary': '#FF7F50',
      '--secondary': '#FF6B6B',
      '--accent': '#FFD93D',
      '--glow-color': 'rgba(255, 127, 80, 0.35)'
    }
  },
  sunset: {
    name: 'Sunset',
    icon: '🌅',
    description: 'Warm sunset tones',
    type: 'dark',
    colors: {
      '--bg-primary': '#1A0F0A',
      '--bg-secondary': '#2D1F14',
      '--bg-card': 'rgba(45, 31, 20, 0.85)',
      '--text-primary': '#FFF8F0',
      '--text-secondary': '#FFD4A4',
      '--text-muted': '#C49B6C',
      '--border-color': 'rgba(255, 165, 0, 0.25)',
      '--primary': '#FFA500',
      '--secondary': '#FF8C00',
      '--accent': '#FFD700',
      '--glow-color': 'rgba(255, 165, 0, 0.35)'
    }
  },
  aurora: {
    name: 'Aurora',
    icon: '✨',
    description: 'Northern lights magic',
    type: 'dark',
    colors: {
      '--bg-primary': '#0A1A1A',
      '--bg-secondary': '#142D2D',
      '--bg-card': 'rgba(20, 45, 45, 0.85)',
      '--text-primary': '#F0FFFF',
      '--text-secondary': '#A4FFCB',
      '--text-muted': '#6CC491',
      '--border-color': 'rgba(0, 255, 127, 0.25)',
      '--primary': '#00FF7F',
      '--secondary': '#00CED1',
      '--accent': '#7FFFD4',
      '--glow-color': 'rgba(0, 255, 127, 0.35)'
    }
  },
  legacy: {
    name: 'Legacy',
    icon: '💎',
    description: 'Classic elegance',
    type: 'dark',
    colors: {
      '--bg-primary': '#0A0A1A',
      '--bg-secondary': '#14142D',
      '--bg-card': 'rgba(20, 20, 45, 0.85)',
      '--text-primary': '#F0F0FF',
      '--text-secondary': '#B4B4FF',
      '--text-muted': '#7070C4',
      '--border-color': 'rgba(99, 102, 241, 0.25)',
      '--primary': '#6366F1',
      '--secondary': '#818CF8',
      '--accent': '#A5B4FC',
      '--glow-color': 'rgba(99, 102, 241, 0.35)'
    }
  },
  sandstone: {
    name: 'Sandstone',
    icon: '🏜️',
    description: 'Desert warmth',
    type: 'dark',
    colors: {
      '--bg-primary': '#1A1408',
      '--bg-secondary': '#2D2414',
      '--bg-card': 'rgba(45, 36, 20, 0.85)',
      '--text-primary': '#FFF8E8',
      '--text-secondary': '#E8D4A4',
      '--text-muted': '#B4A070',
      '--border-color': 'rgba(210, 180, 140, 0.25)',
      '--primary': '#D2B48C',
      '--secondary': '#C4A06C',
      '--accent': '#DEB887',
      '--glow-color': 'rgba(210, 180, 140, 0.35)'
    }
  },
  champagne: {
    name: 'Champagne',
    icon: '🥂',
    description: 'Celebration sparkle',
    type: 'dark',
    colors: {
      '--bg-primary': '#1A1810',
      '--bg-secondary': '#2D2820',
      '--bg-card': 'rgba(45, 40, 32, 0.85)',
      '--text-primary': '#FFFEF8',
      '--text-secondary': '#F5E6C8',
      '--text-muted': '#C4B090',
      '--border-color': 'rgba(247, 231, 206, 0.25)',
      '--primary': '#F7E7CE',
      '--secondary': '#E8D4A8',
      '--accent': '#FFD700',
      '--glow-color': 'rgba(247, 231, 206, 0.35)'
    }
  },
  zoom: {
    name: 'Zoom',
    icon: '💙',
    description: 'Professional blue',
    type: 'dark',
    colors: {
      '--bg-primary': '#0A0F1A',
      '--bg-secondary': '#141F2D',
      '--bg-card': 'rgba(20, 31, 45, 0.85)',
      '--text-primary': '#F0F8FF',
      '--text-secondary': '#A4C8FF',
      '--text-muted': '#6C91C4',
      '--border-color': 'rgba(45, 140, 255, 0.25)',
      '--primary': '#2D8CFF',
      '--secondary': '#0066CC',
      '--accent': '#00BFFF',
      '--glow-color': 'rgba(45, 140, 255, 0.35)'
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
