# Beautiful Design Skill

## Purpose

Ensure all generated websites have distinctive, polished, production-grade UI that avoids generic "AI-generated" aesthetics. Create visually appealing, modern designs that users are proud to show.

## Core Principles

1. **Distinctive, Not Generic** - Avoid cookie-cutter Bootstrap/Tailwind defaults
2. **Cohesive Theme** - Consistent colors, typography, spacing throughout
3. **Modern Aesthetics** - Current design trends, not dated patterns
4. **Attention to Detail** - Micro-interactions, hover states, transitions
5. **Professional Polish** - Looks like a paid designer created it

## Design Checklist

### Color Palette
- [ ] Primary color chosen (not default blue #007bff)
- [ ] Secondary/accent color complements primary
- [ ] Neutral colors for text/backgrounds (not pure black/white)
- [ ] Consistent color usage throughout
- [ ] Sufficient contrast for accessibility (WCAG AA minimum)

### Typography
- [ ] Custom font pairing (Google Fonts or similar)
- [ ] Heading font differs from body font
- [ ] Proper font sizes (16px+ base for readability)
- [ ] Line height 1.5-1.7 for body text
- [ ] Letter spacing adjusted for headings
- [ ] No more than 2-3 font families total

### Spacing & Layout
- [ ] Consistent spacing scale (8px base recommended)
- [ ] Generous whitespace (don't cram content)
- [ ] Visual hierarchy clear
- [ ] Content width limited (max 1200px for readability)
- [ ] Proper padding on mobile (16px+ sides)

### Visual Elements
- [ ] Custom icons (not default browser/system icons)
- [ ] Quality images (not stretched/pixelated)
- [ ] Subtle shadows for depth (not harsh drop shadows)
- [ ] Rounded corners consistent throughout
- [ ] Border usage intentional and consistent

### Interactions
- [ ] Hover states on all clickable elements
- [ ] Smooth transitions (0.2-0.3s ease)
- [ ] Focus states for accessibility
- [ ] Loading states for async actions
- [ ] Feedback on user actions (buttons, forms)

### Polish Details
- [ ] Favicon present
- [ ] Page title descriptive
- [ ] Smooth scroll behavior
- [ ] No layout shifts on load
- [ ] Consistent button styles
- [ ] Form inputs styled (not browser defaults)

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| Default Bootstrap blue | Looks generic | Choose unique brand color |
| Pure black text (#000) | Too harsh | Use dark gray (#1a1a1a or similar) |
| Pure white background (#fff) | Can strain eyes | Use off-white (#fafafa or similar) |
| System fonts only | Looks cheap | Add 1-2 Google Fonts |
| No hover states | Feels broken | Add transitions on interactive elements |
| Harsh drop shadows | Dated look | Use subtle, diffused shadows |
| Too many colors | Chaotic | Stick to 2-3 colors max |
| Tiny text (<14px) | Hard to read | 16px minimum for body |
| No whitespace | Cramped, overwhelming | Generous padding/margins |
| Stock photo overload | Inauthentic | Use sparingly or use illustrations |

## Recommended CSS Starter

```css
/* Modern CSS Reset + Base Styles */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  /* Customize these colors */
  --color-primary: #6366f1;      /* Indigo - change this! */
  --color-primary-dark: #4f46e5;
  --color-secondary: #f59e0b;    /* Amber accent */
  --color-text: #1f2937;         /* Dark gray, not black */
  --color-text-light: #6b7280;
  --color-bg: #fafafa;           /* Off-white */
  --color-surface: #ffffff;
  --color-border: #e5e7eb;

  /* Typography */
  --font-heading: 'Inter', -apple-system, sans-serif;
  --font-body: 'Inter', -apple-system, sans-serif;

  /* Spacing scale (8px base) */
  --space-1: 0.25rem;  /* 4px */
  --space-2: 0.5rem;   /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;     /* 16px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-12: 3rem;    /* 48px */
  --space-16: 4rem;    /* 64px */

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);

  /* Border radius */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-full: 9999px;
}

html {
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-body);
  font-size: 1rem;
  line-height: 1.6;
  color: var(--color-text);
  background-color: var(--color-bg);
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-heading);
  font-weight: 600;
  line-height: 1.25;
  color: var(--color-text);
}

a {
  color: var(--color-primary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

a:hover {
  color: var(--color-primary-dark);
}

button, .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-3) var(--space-6);
  font-family: var(--font-body);
  font-size: 0.875rem;
  font-weight: 500;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-primary {
  background-color: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  background-color: var(--color-primary-dark);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

input, textarea, select {
  width: 100%;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-body);
  font-size: 1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

input:focus, textarea:focus, select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

/* Container */
.container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--space-4);
}

/* Card */
.card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-6);
  transition: box-shadow var(--transition-normal);
}

.card:hover {
  box-shadow: var(--shadow-md);
}
```

## Color Palette Suggestions

Instead of generic colors, consider these modern palettes:

### Palette 1: Modern Indigo
- Primary: #6366f1 (Indigo)
- Accent: #f59e0b (Amber)
- Background: #f8fafc

### Palette 2: Fresh Teal
- Primary: #14b8a6 (Teal)
- Accent: #f43f5e (Rose)
- Background: #f0fdfa

### Palette 3: Bold Purple
- Primary: #8b5cf6 (Purple)
- Accent: #22d3ee (Cyan)
- Background: #faf5ff

### Palette 4: Warm Coral
- Primary: #f97316 (Orange)
- Accent: #0ea5e9 (Sky)
- Background: #fff7ed

### Palette 5: Professional Slate
- Primary: #3b82f6 (Blue)
- Accent: #10b981 (Emerald)
- Background: #f8fafc

## Font Pairing Suggestions

| Headings | Body | Style |
|----------|------|-------|
| Inter | Inter | Clean, modern, versatile |
| Poppins | Open Sans | Friendly, approachable |
| Playfair Display | Source Sans Pro | Elegant, editorial |
| Montserrat | Lora | Bold headings, readable body |
| Space Grotesk | DM Sans | Tech, contemporary |

## Verification

Before marking design complete:

```bash
# Visual checklist script
echo "Design Quality Checklist:"
echo "[ ] Custom color palette (not Bootstrap defaults)"
echo "[ ] Custom fonts loaded"
echo "[ ] Hover states on buttons/links"
echo "[ ] Consistent spacing"
echo "[ ] Mobile responsive"
echo "[ ] No browser default form styles"
echo "[ ] Favicon present"
echo "[ ] Page loads without layout shift"
```

## Integration

This skill should be used:
- When generating any frontend code
- Before deployment to verify visual quality
- During code review of frontend components

Reference this skill in `system_prompt.txt` to ensure Claude applies these principles.
