# Frontend Changes

## Sources Panel Redesign

### Summary
Replaced the cramped comma-separated source links with a clean list — one pill per source, each with an icon, on its own line.

### Files Modified

#### `frontend/script.js`
- Sources are now rendered as `<ul class="sources-list">` with one `<li class="source-item">` per entry
- Each linked source gets an external-link SVG icon; plain-text sources get a document icon
- The `<summary>` now includes a chevron SVG (rotates on open) and a count badge showing the number of sources

#### `frontend/style.css`
- `.sources-collapsible summary` — flex row with chevron, label, and count badge; uppercase/tracked label style
- `.sources-chevron` — rotates 90° when `[open]` via CSS transition
- `.sources-count` — pill badge showing source count
- `.sources-list` — vertical flex column, 0.35 rem gap between items
- `.source-item a` — bordered pill with hover highlight (`--surface-hover` + primary border), primary-coloured text
- `.source-icon` — 13 px inline SVG, slightly muted opacity

---

## Image Upload in Chat

### Summary
Added the ability to attach an image to any chat message. The image is sent to Claude alongside the text query, enabling visual question answering.

### How it works
1. Click the paperclip button in the input bar to open the file picker (images only)
2. A thumbnail preview appears above the input with a ✕ button to remove it
3. Type an optional message and hit Send — the image and text are sent together
4. The image appears in the chat bubble, followed by the text

### Files Modified

#### `frontend/index.html`
- Added `<input type="file" id="imageInput" accept="image/*" style="display:none">` — hidden file picker
- Added `<button id="attachButton">` with a paperclip SVG icon, placed before the text input
- Added `.image-preview-container` with a thumbnail `<img id="imagePreview">` and a `<button class="image-remove-btn">` — shown/hidden via JS

#### `frontend/script.js`
- Added `selectedImageData` and `selectedImageMediaType` global state variables
- `handleImageSelect(e)` — reads the selected file with `FileReader`, stores raw base64 (strips the data-URL prefix), shows the preview
- `clearSelectedImage()` — resets state and hides the preview
- `sendMessage()` updated to: capture image before clearing UI, pass `imageSrc` to `addMessage()`, include `image_data` and `image_media_type` in the API request body
- `addMessage()` updated to accept optional `imageSrc` parameter and render `<img class="chat-image">` inside the message bubble when present

#### `frontend/style.css`
- `#attachButton` — circular button matching the send button's dimensions, with hover/focus styles and a `.has-image` active state
- `.image-preview-container` / `.image-preview-wrapper` / `#imagePreview` — thumbnail area above the input, max 120 px tall
- `.image-remove-btn` — small circular ✕ button overlaid on the thumbnail corner
- `.chat-image` — images inside chat bubbles, capped at 300 px tall, rounded corners

#### `backend/app.py`, `backend/rag_system.py`, `backend/ai_generator.py`
- `QueryRequest` extended with optional `image_data` (base64 string) and `image_media_type` fields
- `rag_system.query()` and `ai_generator.generate_response()` updated to thread image data through to the Claude API call
- When an image is present, the user message content is built as a list `[image_block, text_block]` per the Anthropic vision API format

---

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
