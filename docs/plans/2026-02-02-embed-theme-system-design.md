# Embed Mode Theme System Design

**Date:** 2026-02-02
**Status:** Approved
**Scope:** Add full theme system to embed mode only (`/?guid=xxx&embed=true`)

---

## Overview

Port the AI Product Studio's 8-theme system to the tmux-builder embed mode, enabling visual consistency when the embed is used within the AI Product Studio website.

## Requirements

1. **Full theme system** - All 8 themes from reference project (Ember, Coral, Sunset, Aurora, Sandstone, Champagne, Zoom, Legacy)
2. **Embed mode only** - Admin UI and Client UI remain unchanged
3. **Same localStorage key** - Use `cocreate-theme` for cross-site sync
4. **URL parameter support** - `?theme=xxx` sets initial theme
5. **Theme picker UI** - Dropdown with color previews (same as reference)
6. **Animated gradients** - Per-theme background animations
7. **Default theme** - Ember (dark)

## Non-Requirements

- No changes to Admin UI (`/`)
- No changes to Client UI (`/client`)
- No backend changes
- Keep existing system fonts (no Google Fonts import)

---

## File Structure

### New Files

```
frontend/src/
├── themes/
│   ├── themeConfig.js      # Theme definitions (8 themes, colors, metadata)
│   ├── ThemeManager.js     # Theme logic (get, set, apply, localStorage)
│   └── themeStyles.css     # CSS variables, gradients, animations
├── components/
│   ├── EmbedView.jsx       # New component for themed embed mode
│   └── ThemePicker.jsx     # Dropdown theme selector
```

### Modified Files

```
frontend/src/components/SplitChatView.jsx
  - Add conditional render: if embed=true, render EmbedView
```

---

## Theme Configuration

### Themes

| Theme | Type | Primary | Background |
|-------|------|---------|------------|
| Ember | Dark | `#FC2A0D` | `#1A0A00` |
| Coral | Light | `#FC2A0D` | `#FFF8F0` |
| Sunset | Dark | `#FF6B9D` | `#2D1B3D` |
| Aurora | Light | `#E6A4FF` | `#FFF5F8` |
| Sandstone | Light | `#FC2A0D` | `#FAF6F1` |
| Champagne | Light | `#FC2A0D` | `#FFFDF8` |
| Zoom | Light | `#0B5CFF` | `#FFFFFF` |
| Legacy | Dark | `#6366f1` | `#020617` |

### CSS Variables Per Theme

```
--bg-primary, --bg-secondary, --bg-card
--text-primary, --text-secondary, --text-muted
--primary, --secondary, --accent
--border-color, --glow-color
```

### localStorage

- Key: `cocreate-theme` (same as reference project)
- Also writes to `theme` for backwards compatibility
- Default: `ember`

---

## Component Design

### EmbedView.jsx

Main container for themed embed mode.

**Props:**
- `initialGuid` - Session GUID from URL
- `initialTheme` - Theme from URL param (optional)

**State:**
- `currentTheme` - Active theme name
- `messages` - Chat messages
- `loading` - Loading state
- `guid` - Session GUID

**Features:**
- Applies theme on mount via `applyTheme()`
- Listens for `storage` event for cross-tab sync
- URL `?theme=xxx` takes priority over localStorage
- Reuses existing `MessageList`, `InputArea`, `useProgressSocket`

### ThemePicker.jsx

Dropdown theme selector.

**Props:**
- `currentTheme` - Current theme name
- `onThemeChange` - Callback when theme selected

**UI:**
- Button showing current theme icon + name
- Dropdown with 8 theme options
- Each option has color preview circle (gradient)
- Active theme highlighted

---

## Theme Sync Mechanism

1. **On page load:** Read from `localStorage.getItem('cocreate-theme')`
2. **On theme change:** Save to localStorage, apply CSS variables
3. **Cross-tab sync:** Listen for `storage` event, update when changed
4. **URL override:** `?theme=xxx` param takes priority over localStorage

```javascript
// Real-time sync listener
window.addEventListener('storage', (e) => {
  if (e.key === 'cocreate-theme' && e.newValue) {
    applyTheme(e.newValue);
  }
});
```

---

## CSS Architecture

### Scoping

All theme styles scoped to `[data-theme]` selector to avoid affecting non-embed pages.

```css
[data-theme] { /* only applies when data-theme attribute exists */ }
[data-theme="ember"] .embed-container { /* theme-specific */ }
```

### Animated Gradients

Each theme has unique gradient animation:
- Ember: 20s cycle
- Coral: 25s cycle
- Sunset: 18s cycle
- etc.

### Glass-morphism

Cards use:
- `backdrop-filter: blur(20px)`
- Semi-transparent backgrounds
- Subtle borders with theme color

---

## Integration Point

### SplitChatView.jsx Change

```jsx
function SplitChatView() {
  const urlParams = getUrlParams();

  // Early return for embed mode
  if (urlParams.embed) {
    return (
      <EmbedView
        initialGuid={urlParams.guid}
        initialTheme={urlParams.theme}
      />
    );
  }

  // Existing admin UI code unchanged...
}
```

---

## URL Examples

| URL | Result |
|-----|--------|
| `/?guid=abc&embed=true` | Embed with Ember (default) |
| `/?guid=abc&embed=true&theme=coral` | Embed with Coral theme |
| `/?guid=abc&embed=true&theme=sunset` | Embed with Sunset theme |
| `/?guid=abc` | Admin UI (unchanged) |
| `/` | Admin UI (unchanged) |
| `/client?guid=abc` | Client UI (unchanged) |

---

## Impact Analysis

| Component | Affected | Reason |
|-----------|----------|--------|
| Admin UI | No | Only renders EmbedView when embed=true |
| Client UI | No | Separate route, not touched |
| Backend | No | No backend changes |
| WebSocket | No | Same underlying logic |
| Chat logic | No | Only visual changes |

---

## Implementation Order

1. Create `themes/themeConfig.js` - Theme definitions
2. Create `themes/ThemeManager.js` - Theme logic
3. Create `themes/themeStyles.css` - CSS with animations
4. Create `components/ThemePicker.jsx` - Dropdown UI
5. Create `components/EmbedView.jsx` - Main embed container
6. Modify `SplitChatView.jsx` - Conditional render
7. Test all 8 themes
8. Test cross-tab sync
9. Test URL param override
