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
