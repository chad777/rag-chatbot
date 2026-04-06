# Frontend Changes

## Theme Toggle Button

### Summary
Implemented a dark/light mode toggle button positioned in the top-right corner of the UI.

### Light Theme Colour Decisions
- **Primary colour**: `#2563eb` — consistent with dark mode for cross-theme brand identity (contrast 4.54:1 on white, WCAG AA pass)
- **Primary hover**: `#1e40af` — one step darker to maintain visible hover feedback on light backgrounds
- **Text secondary**: `#475569` — tightened from `#64748b` for 5.74:1 contrast (vs 4.48:1), keeping secondary text comfortably legible
- **Code blocks**: `rgba(15,23,42,0.06)` background with `rgba(15,23,42,0.08)` border — replaces hardcoded dark-mode `rgba(0,0,0,0.2)` via new `--code-bg` / `--code-border` variables

### Files Modified

#### `frontend/index.html`
- Added a `<button class="theme-toggle" id="themeToggle">` fixed to the top-right, outside the main `.container`
- Button contains two inline SVGs: a sun icon (visible in dark mode) and a moon icon (visible in light mode)
- `aria-label` set to `"Switch to light mode"` by default; updated dynamically by JS on each toggle
- Both SVGs use `aria-hidden="true"` — the button label carries the accessible name

#### `frontend/style.css`
- Added `:root[data-theme="light"]` CSS custom property overrides for all colour tokens (`--background`, `--surface`, `--text-primary`, etc.)
- Added `body.theme-transition` rule that briefly enables `transition` on background-color, color, border-color, and box-shadow — giving a smooth 300ms crossfade when switching themes
- Added `.theme-toggle` styles: `position: fixed; top: 1rem; right: 1rem`, circular shape (44×44 px), hover/focus-visible ring using `--focus-ring`, scale transforms on hover and active
- Added `.theme-icon` base styles with `position: absolute` and opacity/transform transitions (350ms)
- Dark mode default: `.sun-icon` fully visible; `.moon-icon` rotated 30° and scaled down to 0
- Light mode (`:root[data-theme="light"]`): states swapped — moon visible, sun hidden

#### `frontend/script.js`
- Added `themeToggle` to the DOM element declarations
- `applyTheme(theme)` — sets `document.documentElement.dataset.theme`, persists to `localStorage`, and syncs the button's `aria-label`
- `toggleTheme()` — reads current theme from `localStorage`, computes the next, wraps `applyTheme()` in a `theme-transition` class that is removed after 350 ms
- `initTheme()` — reads `localStorage` on page load and defaults to `'dark'` if no preference is saved (Option A)
- `setupEventListeners()` — wires `themeToggle` click to `toggleTheme()`

### Accessibility
- Button is a native `<button>` — keyboard focusable and activatable with Enter/Space by default
- `aria-label` describes the *next* action ("Switch to light mode" / "Switch to dark mode") and is kept in sync on every toggle
- `focus-visible` ring provides a clear visual indicator for keyboard users
- Icons are `aria-hidden` so screen readers rely solely on the button label
