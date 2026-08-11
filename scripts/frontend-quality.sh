#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Frontend Quality Checks ==="

echo ""
echo "--- Formatting (Prettier) ---"
if [ "${1}" = "--fix" ]; then
    npx prettier --write frontend/
    echo "Formatting applied."
else
    npx prettier --check frontend/
    echo "Formatting OK."
fi

echo ""
echo "--- Linting (ESLint) ---"
npx eslint frontend/script.js
echo "Linting OK."

echo ""
echo "All checks passed."
