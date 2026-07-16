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

## Recursive dogfood boundaries

These are working staging capabilities on agent branches; they are not claimed
as deployed on canonical main.

- **Authoritative issue File Scope.** When an issue declares one, planner
  responses selecting paths outside it are rejected; `ChangeApplier` likewise
  rejects coder changes outside the resulting planned-file set.
- **Transactional structured edits.** Creates, single or multi-block exact
  replacements, and bounded rewrites are validated before they are written; the
  agent never applies a model-supplied raw diff.
- **Truncation handling.** Token-limit completion signals are rejected and
  retried with a request for a complete, more concise structured response.
- **Token-budget admission.** Before every planner, coder, repair, or critic
  call, Forge0 conservatively estimates prompt tokens and reserves a minimally
  usable completion; the requested completion is capped to the estimated
  remaining run budget and a call is refused before provider invocation when
  it cannot fit. Provider-reported usage remains authoritative after each
  admitted call and still fails a run if the configured budget is exceeded.
- **Path-aware coverage reporting.** The fixed repository suite still runs, while
  changed paths are classified as Python-covered, documentation review-only, or
  unsupported and requiring explicit manual acceptance. Repository-level health
  checks are not claimed as artifact-specific verification.
- **Bounded verification repair.** One retry is permitted to fix a failing
  verification gate, restricted to the original planned paths.
- **Bounded critic repair.** One retry is permitted to address read-only critic
  findings, also restricted to the original planned paths.
- **Structured critic findings.** Bounded, staged-path-validated findings are
  persisted alongside normalized critic feedback and supplied to repair.
  Every normalized critic decision is appended to `critic_reviews`; each
  history entry records a 1-based attempt number and the repair count at
  that decision. The `critic_feedback` and `critic_findings` fields remain
  compatibility fields containing the latest decision.
- **Evidence-grounded criticism.** A plan may select at most three existing
  read-only repository files, disjoint from changed files; selected evidence
  context is capped at 60,000 characters and supplied to both initial and
  post-repair criticism. Issue text and plans are requirements, not evidence.
  An unsupported behavioral claim is a blocking high-severity finding with
  `pass=false`.

Every repair—verification or critic—must remeasure the diff, rerun the fixed
verification, and pass read-only criticism before publication.

**Final authority boundary.** The agent may push to its own branches and open
native draft pull requests only. It never merges or deploys.

## Completion criteria

The MVP is releasable when unit tests, Ruff, Pyright, Python byte-compilation,
Compose validation, image build, container health, and portal smoke tests all
pass. Roadmap items should only move into the working section with tests and an
operator-facing integration path.
