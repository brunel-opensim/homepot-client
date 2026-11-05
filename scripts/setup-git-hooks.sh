#!/usr/bin/env bash
# Enable the repository's tracked git hooks.
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "Git hooks enabled (core.hooksPath = .githooks)."
echo "Pre-commit will now run black/isort/flake8 (and mypy for backend changes)."
