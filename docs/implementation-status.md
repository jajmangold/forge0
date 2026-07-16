# Implementation Status

This page is the source of truth for what Forge0 currently ships. The other
documents include design research and proposed workflows; examples in those
documents are not automatically implemented features.

## Working MVP

- Gitea hosting with SQLite persistence, loopback-only HTTP/SSH ports, health
  checks, API bootstrap, and a portal reverse proxy.
- FastAPI/HTMX portal with repository inventory, repository details, recent
  commits, issues, pull requests, and Gitea Actions run summaries.
- Project chat that assembles bounded repository context and calls an
  OpenAI-compatible LLM endpoint. Input/history are validated and chat output
  is rendered as untrusted text.
- SearXNG-backed research helpers.
- LLM client, requirements/research/architecture/critic agents, deterministic
  workflow state, stuck/cost tracking, self-correction helpers, rollback
  helpers, and coordination primitives.
- OpenCode configuration with role permissions, MCP definitions, LSPs, and 17
  reusable skills.
- Gitea governance templates and validation/maintenance workflows.
- Bounded self-extension from an explicitly labeled issue to a verified draft
  PR: persistent run records, signed webhooks, disposable clones, structured
  edits, path/diff/token limits, quality gates, critic review, and run UI.

## Experimental, opt-in tooling

- W&B local experiment tracking (`observability` Compose profile).
- Optuna study initialization (`optimization` Compose profile).
- OpenEvolve, OptiLLM, TrailMark, and language-specific development images and
  skills. These are agent tools, not portal services.

## Roadmap, not yet productized

- A long-running supervisor that autonomously dispatches multiple agents.
- A UI for requirements interviews and phase transitions.
- Cross-session semantic memory or tree-sitter repository maps.
- Automatic merging or deployment of agent-authored changes. Self-extension
  intentionally stops at a human-reviewed draft pull request.
- A bundled Gitea Actions runner. Workflows are supplied, but operators must
  register a runner appropriate for their Docker security model.
- Production authentication, TLS termination, multi-user authorization, and a
  production database. The current deployment is a localhost, single-operator
  development system.

## Completion criteria

The MVP is releasable when unit tests, Ruff, Pyright, Python byte-compilation,
Compose validation, image build, container health, and portal smoke tests all
pass. Roadmap items should only move into the working section with tests and an
operator-facing integration path.
