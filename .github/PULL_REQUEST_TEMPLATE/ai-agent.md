---
name: AI Agent Change
about: Pull request opened by an AI agent
title: '<type>(<scope>): <description>'
labels: 'ai-agent'
assignees: ''
---

## Summary

<!-- What does this PR change and why? -->

## Pre-PR checklist (AI agent must confirm)

- [ ] `black --check` passed on touched Python files
- [ ] `isort --check-only` passed
- [ ] `flake8` passed (no D103/F401/etc.)
- [ ] `mypy --config-file=backend/mypy.ini backend/src/homepot/` passed
- [ ] Backend tests for touched code pass
- [ ] Frontend `format:check` + `lint` + `test` + `build` pass (if frontend touched)
- [ ] `mkdocs build --strict` passes (if docs touched)
- [ ] No secrets or API keys committed
- [ ] No emoji status markers in docs
- [ ] AGENTS.md conventions followed

## Testing

<!-- Commands run and their output summary -->

## Notes for reviewer

<!-- Anything the human reviewer should pay attention to -->
