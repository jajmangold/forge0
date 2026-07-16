---
name: trailmark
description: Build and query a code property graph — functions, classes, calls, entrypoints, complexity, trust boundaries, and semantic annotations for analysis, refactoring, and security
license: Apache-2.0
compatibility: opencode
metadata:
  audience: developers
  workflow: analysis
  source: https://github.com/trailofbits/trailmark
---

## What I do

TrailMark parses source code into a queryable graph — functions, classes, calls, and semantic annotations. It's a **code property graph** useful for much more than security.

Use it to:
- **Understand code structure** — functions, classes, modules, dependencies
- **Trace data flow** — who can reach this sink? what can this source reach?
- **Find entrypoints** — HTTP handlers, CLI commands, public APIs
- **Analyze complexity** — cyclomatic complexity hotspots
- **Map call graphs** — who calls whom, transitive dependencies
- **Diff structural changes** — compare code between revisions
- **Overlay findings** — fold SARIF/weAudit results into the graph
- **Support refactoring** — understand impact of changes
- **Track trust boundaries** — which code handles untrusted input

## When to use me

- **Understanding unfamiliar code** — quickly map a codebase
- **Refactoring** — understand what will break
- **Code review** — see the full picture of changes
- **Debugging** — trace data flow to find bugs
- **Performance** — find complexity hotspots
- **Security** — find entrypoints and trust boundaries
- **Documentation** — generate architecture diagrams
- **Impact analysis** — what does this function affect?

## Supported Languages

Python, JavaScript, TypeScript, PHP, Ruby, C, C++, C#, Java, Go, Rust, Solidity, Cairo, Circom, Haskell, Erlang, Miden Assembly, Swift, Objective-C, Kotlin, Dart, Move, Tact, Func, Sway, Rego, Proto, Thrift, GraphQL

## Commands

### Analyze — build the code graph

```bash
# Full JSON graph (default: python)
trailmark analyze <path>

# Auto-detect all languages and merge
trailmark analyze <path> --language auto

# Human-readable summary
trailmark analyze <path> --summary

# High-complexity functions (cyclomatic ≥ threshold)
trailmark analyze <path> --complexity 10

# Machine-readable JSON output
trailmark analyze <path> --json
```

### Entrypoints — find public interfaces

```bash
# List detected entrypoints with trust classification
trailmark entrypoints <path>

# JSON output for programmatic use
trailmark entrypoints <path> --json
```

### Diff — structural changes between revisions

```bash
# Compare two directories
trailmark diff <before> <after>

# Compare git refs
trailmark diff --repo . main HEAD

# JSON output
trailmark diff --json <before> <after>
```

### Augment — overlay external findings

```bash
# Add SARIF findings (repeatable)
trailmark augment <path> --sarif results.sarif

# Add weAudit findings
trailmark augment <path> --weaudit findings.json

# Multiple sources + JSON output
trailmark augment <path> --sarif a.sarif --sarif b.sarif --json
```

### Diagram — generate Mermaid graphs

```bash
# Call graph
trailmark diagram --target <path> --type call-graph

# Focused on a specific function with depth limit
trailmark diagram -t <path> -T call-graph -f parse_file --depth 3

# Complexity visualization
trailmark diagram -t <path> -T complexity --threshold 5 --direction LR

# Class hierarchy
trailmark diagram -t <path> -T class-hierarchy

# Module dependencies
trailmark diagram -t <path> -T module-deps
```

## QueryEngine API (programmatic)

```python
from trailmark.query.api import QueryEngine

engine = QueryEngine.from_directory("src/", language="auto")

# === Code Structure ===
engine.summary()                        # Node counts, edge counts
engine.callers_of("handle_request")     # Who calls this?
engine.callees_of("handle_request")     # What does this call?

# === Data Flow ===
engine.ancestors_of("Auth._check_sig")    # Who can reach this?
engine.reachable_from("handle_request")    # What can this reach?
engine.paths_between("src", "dst")         # All paths between two nodes
engine.entrypoint_paths_to("Auth._check_sig")  # Paths from entrypoints

# === Complexity Analysis ===
engine.complexity_hotspots(10)         # Functions with complexity ≥ 10
engine.functions_that_raise("PermissionError")  # Exception propagation

# === Annotations ===
engine.annotate("handle_request", AnnotationKind.ASSUMPTION, "Caller authenticated", source="llm")
engine.annotations_of("handle_request")
engine.nodes_with_annotation(AnnotationKind.FINDING)

# === Pre-analysis ===
engine.preanalysis()                   # Run built-in audit passes
engine.findings()                      # Get findings
engine.subgraph_names()                # List named subgraphs

# === Structural Diff ===
before = QueryEngine.from_directory("before/")
diff = engine.diff_against(before)     # Structural changes
```

## Use Cases Beyond Security

### 1. Understanding Unfamiliar Code

```bash
# Quick overview
trailmark analyze src/ --summary

# Find the entrypoints
trailmark entrypoints src/

# See what the main function calls
trailmark analyze src/ --json | jq '.functions[] | select(.name == "main")'
```

### 2. Refactoring Support

```bash
# Before renaming a function, see who calls it
trailmark analyze src/ --json | jq '.calls[] | select(.target == "old_name")'

# See the full call chain
trailmark entrypoint_paths_to "module:old_name"

# Diff after refactoring
trailmark diff before/ after/
```

### 3. Debugging Data Flow

```bash
# Trace where data comes from
trailmark entrypoint_paths_to "module:sink_function"

# Trace where data goes
trailmark reachable_from "module:source_function"

# Find all paths between two points
trailmark paths_between "module:input_handler" "module:database_query"
```

### 4. Performance Analysis

```bash
# Find complexity hotspots
trailmark analyze src/ --complexity 10

# Visualize complexity
trailmark diagram -t src/ -T complexity --threshold 5

# Find deeply nested call chains
trailmark analyze src/ --json | jq '[.functions[] | select(.cyclomatic_complexity > 15)]'
```

### 5. Architecture Documentation

```bash
# Generate call graph diagram
trailmark diagram -t src/ -T call-graph --focus module --depth 3

# Generate class hierarchy
trailmark diagram -t src/ -T class-hierarchy

# Generate module dependencies
trailmark diagram -t src/ -T module-deps
```

### 6. Impact Analysis

```bash
# What breaks if I change this function?
trailmark analyze src/ --json | jq '.calls[] | select(.source == "module:function_to_change")'

# What modules depend on this?
trailmark ancestors_of "module:function_to_change"

# Full dependency graph
trailmark diagram -t src/ -T containment -f module
```

### 7. Code Review

```bash
# See what changed structurally
trailmark diff main..feature-branch

# Find new entrypoints introduced
trailmark diff main..feature-branch | jq '.entrypoints.added'

# Find high-complexity additions
trailmark diff main..feature-branch | jq '.nodes.added[] | select(.cyclomatic_complexity > 10)'
```

### 8. Test Coverage Analysis

```bash
# Find entrypoints that need tests
trailmark entrypoints src/ --json

# Find functions never called (dead code?)
trailmark analyze src/ --json | jq '.functions[] | select(.callers == [])'

# Find the most-called functions (critical path)
trailmark analyze src/ --json | jq 'group_by(.source) | map({source: .[0].source, count: length}) | sort_by(-.count)'
```

## Entrypoint Override File

`.trailmark/entrypoints.toml` at project root:

```toml
# Single-node entry
[[entrypoint]]
node = "my_module:handle_request"  # node id, or "module.path:function"
kind = "api"                       # user_input | api | database | file_system | third_party
trust = "untrusted_external"       # untrusted_external | semi_trusted_external | trusted_internal
asset_value = "high"               # high | medium | low
description = "HTTP POST /auth"

# Rule: every PHP script under public_html/ is web-exposed
[[entrypoint]]
file_glob = "public_html/**/*.php"
kind = "user_input"
trust = "untrusted_external"
asset_value = "high"

# Rule: any function taking a PSR-7 request
[[entrypoint]]
param_type = "ServerRequestInterface"
kind = "api"
trust = "untrusted_external"

# Rule: functions named handle_*
[[entrypoint]]
name_regex = "^handle_"
kind = "api"
trust = "untrusted_external"
```

## Output Formats

### Summary (--summary)
```
src/
├── Functions: 42
├── Classes: 8
├── Entry points: 5
│   ├── HTTP handlers: 3
│   ├── CLI commands: 2
│   └── Public APIs: 2
├── High complexity (≥10): 3
└── Call depth: 4
```

### JSON (--json)
```json
{
  "functions": [...],
  "classes": [...],
  "calls": [...],
  "entrypoints": [...],
  "complexity": {...}
}
```

## Integration with Forge0

### Planner Agent
- Use `trailmark analyze --summary` to understand existing code
- Use `trailmark entrypoints` to identify what needs protection
- Use `trailmark diagram` to document architecture

### Coder Agent
- Use `trailmark entrypoints` to understand what needs tests
- Use `trailmark reachable_from` to trace data flow
- Use `trailmark complexity_hotspots` to find areas to simplify

### Reviewer Agent
- Use `trailmark diff` to review structural changes
- Use `trailmark entrypoint_paths_to` to trace security impact
- Use `trailmark diagram` to visualize changes

### Security Agent
- Use `trailmark augment` to overlay findings
- Use `trailmark entrypoint_paths_to` to trace attack paths
- Use `trailmark complexity_hotspots` to find risky code

## Rules

- **Run on every repo** — understand before you change
- **Use before refactoring** — see what will break
- **Use during code review** — understand the full picture
- **Use for debugging** — trace data flow
- **Use for documentation** — generate architecture diagrams
- **Overlay findings** — combine with other tools
- **Diff before merging** — understand structural changes

## References

- Source: https://github.com/trailofbits/trailmark
- License: Apache-2.0
- Tree-sitter: https://tree-sitter.github.io/
- rustworkx: https://www.rustworkx.org/
