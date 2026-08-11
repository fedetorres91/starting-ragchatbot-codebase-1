# Frontend Changes

## Code Quality Tooling

### What was added

**Prettier** (formatting) and **ESLint** (linting) have been added as frontend development tools.

### New files

| File | Purpose |
|---|---|
| `package.json` | Node.js project manifest; defines `format`, `format:check`, `lint`, and `quality` scripts |
| `.prettierrc` | Prettier config: 4-space indent, single quotes, semicolons, 100-char line width |
| `.prettierignore` | Excludes `backend/`, `docs/`, `node_modules/`, and lock files from Prettier |
| `.eslintrc.json` | ESLint config targeting ES2021 browser env; enforces `===`, `const`/`let`, warns on unused vars |
| `scripts/frontend-quality.sh` | Shell script that runs all frontend checks; pass `--fix` to auto-format |

### Modified files

| File | Change |
|---|---|
| `.gitignore` | Added `node_modules/` and `package-lock.json` |
| `frontend/index.html` | Reformatted by Prettier |
| `frontend/script.js` | Reformatted by Prettier (quote normalization, trailing commas) |
| `frontend/style.css` | Reformatted by Prettier |

### How to use

```bash
# Check formatting and lint (CI-style, no writes)
npm run quality

# Auto-format frontend files
npm run format

# Lint only
npm run lint

# All-in-one dev script (check mode)
bash scripts/frontend-quality.sh

# All-in-one dev script (auto-fix mode)
bash scripts/frontend-quality.sh --fix
```

### Tool choices

- **Prettier** — zero-config opinionated formatter, the JS/CSS/HTML equivalent of Python's `black`. Eliminates formatting debates.
- **ESLint v8** — static analysis for `script.js`; catches bugs (`eqeqeq`), enforces modern JS (`no-var`, `prefer-const`), and allows `console.*` since the frontend uses it intentionally.

---

## Dark/Light Mode Toggle Button

### What was added
A fixed-position theme toggle button in the top-right corner of the UI that lets users switch between dark mode (default) and light mode.

### Files modified

**`frontend/index.html`**
- Added a `<button id="themeToggle">` element before the closing `</body>` tag
- Button contains two inline SVGs: a sun icon (Feather-style, shown in dark mode) and a moon icon (shown in light mode)
- `aria-label` and `title` attributes set for accessibility; updated dynamically by JS when theme changes

**`frontend/style.css`**
- Added `body.light-mode` CSS variable overrides (see Light Theme section below)
- Added light-mode-specific overrides for code block backgrounds and source link colors
- Added `transition` rules on key elements (body, sidebar, chat area, inputs, buttons, text) for smooth 0.3s color transitions when toggling
- Styled `#themeToggle` as a 44×44px circular fixed button (top: 1rem, right: 1rem, z-index: 100)
- Hover effect: slight scale-up + primary-color border + focus ring
- Focus-visible ring for keyboard navigation
- Icon animation: sun/moon icons positioned absolutely, crossfade + rotate/scale on toggle (0.3s ease)

**`frontend/script.js`**
- Added `initTheme()` called on `DOMContentLoaded` — reads `localStorage` for saved preference and applies it
- Added `toggleTheme()` — flips between light and dark
- Added `applyTheme(theme)` — adds/removes `body.light-mode`, updates `aria-label`/`title` on the button, persists choice to `localStorage`

### Design decisions
- **Icon convention**: sun icon shown in dark mode (click → go light), moon icon shown in light mode (click → go dark)
- **Persistence**: preference saved to `localStorage` under key `"theme"`, restored on page load
- **Accessibility**: button is a native `<button>` (keyboard-focusable by default), `aria-label` dynamically describes the action ("Switch to light/dark mode"), SVGs have `aria-hidden="true"` since the label covers the meaning
- **Transitions**: scoped to specific elements rather than `* {}` to avoid interfering with existing animations (loading bounce, message fade-in)

---

## Light Theme Variant

### What was improved / added

**`frontend/style.css`** — comprehensive light mode color system:

| Token | Dark mode | Light mode | Notes |
|---|---|---|---|
| `--background` | `#0f172a` | `#f1f5f9` | Page canvas; contrast with white surface cards |
| `--surface` | `#1e293b` | `#ffffff` | Cards, sidebar, bubbles |
| `--surface-hover` | `#334155` | `#f8fafc` | Hover states |
| `--text-primary` | `#f1f5f9` | `#0f172a` | ~18:1 on white (AAA) |
| `--text-secondary` | `#94a3b8` | `#475569` | ~7.2:1 on white (AAA) |
| `--border-color` | `#334155` | `#cbd5e1` | Visible on both surface and background |
| `--primary-color` | `#2563eb` | `#2563eb` | ~5.9:1 on white (AA) — unchanged |
| `--focus-ring` | `rgba(37,99,235,0.2)` | `rgba(37,99,235,0.2)` | Unchanged |
| `--user-message` | `#2563eb` | `#2563eb` | White text on blue: ~5.9:1 (AA) |
| `--assistant-message` | `#374151` | `#ffffff` | White bubble on `#f1f5f9` background |
| `--welcome-border` | `#2563eb` | `#3b82f6` | Softer blue accent |

**Hardcoded color overrides (elements that don't inherit variables):**
- **Error messages**: `#f87171` → `#dc2626` (~5.9:1 on white, AA). The original color has ~2.3:1 on light backgrounds — fails WCAG.
- **Success messages**: `#4ade80` → `#16a34a` (~4.7:1 on white, AA). The original has ~1.6:1 — fails WCAG badly.
- **Source tag pills**: border opacity increased from 0.2 → 0.22, background token changed to slate-based for better visibility on white.
- **Source link pills**: adjusted to `#1d4ed8` text with lower-opacity backgrounds for clean look on white.
- **Code/pre blocks**: `rgba(0,0,0,0.2)` → `rgba(15,23,42,0.05)` background + `#1e293b` code text for legibility.
- **Assistant message bubble**: added `box-shadow: 0 1px 3px rgba(0,0,0,0.08)` to lift bubble off `#f1f5f9` background.
- **Welcome card**: replaced heavy `rgba(0,0,0,0.2)` shadow with `rgba(37,99,235,0.08)` blue-tinted shadow; uses `--welcome-border` for border color.

**Bug fix:**
- `blockquote` used `var(--primary)` (undefined variable) — corrected to `var(--primary-color)`.
