# Research Sources & Key Takeaways

References that informed the Forge0 greenfield workflow design.

## McKinsey QuantumBlack: "Agentic Workflows for Software Development"

**Source:** https://medium.com/quantumblack/agentic-workflows-for-software-development-dc8e64f4a79d

**Key takeaways:**
- **Two-layer model:** Deterministic orchestration + bounded agent execution
- **Agents don't decide phases.** A workflow engine reads artifact state and transitions accordingly.
- **Spec-driven development (SDD):** Structured specifications drive what agents produce; ad-hoc prompts are eliminated.
- **Evaluations at every gate:** Deterministic checks (linters, structural validation) + critic agent (judgment calls).
- **Knowledge agent pattern:** A dedicated agent that other agents call via tool calls to query project context and log assumptions.
- **"Isn't this just waterfall?"** — Yes. But agents change the economics. When the full cycle takes hours instead of months, you can afford the structure. Teams run multiple complete cycles per day.
- **Folder conventions as contracts:** The hierarchy and naming tell the system what's persistent vs per-feature, what's related, where agents should read/write.

**Quote:** "The value comes when agents operate inside conventions, structured specifications, and deterministic processes."

## Agent-Driven Development Framework

**Source:** https://github.com/stuartsc/agent-driven-dev-framework

**Key takeaways:**
- **AGENTS.md standard:** 40,000+ projects adopted this. Root-level file telling AI agents how to work in the project.
- **PROTOCOL.md:** Mandatory session protocol. Agents consistently forget protocols — multiple enforcement layers needed.
- **HISTORY.md:** Living document for session continuity and agent handoffs. "Up Next" section tells agents what to work on.
- **Smart commits:** `<KEY> #command args` syntax for automatic issue updates.
- **Multiple enforcement layers:** File naming (alphabetically first), session-start prompts, git hooks, verification scripts, HISTORY.md integration. Single reminders don't work.

## LangGraph

**Source:** https://blog.langchain.com/building-langgraph/ and https://medium.com/@shuv.sdr/langgraph-architecture-and-design-280c365aaf2c

**Key takeaways:**
- **Graph-based agent workflows:** States and nodes, with conditional edges.
- **PregelLoop runtime:** Plans the computation graph for each agent invocation and executes it.
- **State flows through nodes:** Each node is a function or LLM call. State (message history) flows through.
- **Good for complex multi-step workflows** where different agents handle different phases.

## OpenCode Go Endpoints

**Source:** https://opencode.ai/docs/go/

**Key takeaways:**
- **OpenAI-compatible:** `https://opencode.ai/zen/go/v1/chat/completions`
- **Anthropic-compatible:** `https://opencode.ai/zen/go/v1/messages` (for some models)
- **Model list:** `https://opencode.ai/zen/go/v1/models`
- **Best value models:** deepseek-v4-flash ($0.14/$0.28 per 1M tokens), mimo-v2.5 ($0.14/$0.28)
- **Coding models:** kimi-k2.7-code ($0.95/$4.00), deepseek-v4-pro ($1.74/$3.48)
- **Zero retention policy** on provider side

## OpenCode Server API

**Source:** https://opencode.ai/docs/server/

**Key takeaways:**
- `opencode serve` runs a headless HTTP server with OpenAPI 3.1 spec
- Session-based: create sessions, send messages, get responses
- Supports tools, agents, MCP servers
- SSE event stream for real-time updates
- Can be used programmatically (not just via TUI)

## Other Patterns Observed

### Spec-driven development tools
- **Spec Kit** (GitHub): Structured specifications in repos
- **Kiro** (AWS): Agent-driven development with specs
- Both separate persistent project context from per-feature specifications

### Common agent failure modes (from multiple sources)
1. Agents skip steps when self-orchestrating
2. Agents create circular dependencies
3. Agents get stuck in analysis loops
4. Different developers get different results from the same model
5. Decisions live in chat windows with no audit trail

### Solutions that work
1. Deterministic orchestration (not agent-decided)
2. Structured artifact formats (YAML frontmatter + markdown)
3. Evaluation at every gate (deterministic + critic)
4. Everything in the repo (git as state store)
5. Knowledge accumulation (decisions + assumptions logged)

## Implications for Forge0

1. **Orchestration engine** = Python code that reads `.forge0/workflow.yaml` and transitions phases. Not an LLM.
2. **Agents** = Prompt + model + tools. Each bounded to a specific phase.
3. **Artifacts** = Markdown files with YAML frontmatter. Machine-readable status.
4. **Evaluations** = Lint/structural checks + critic agent. Run after every agent output.
5. **Portal** = Human interface to the workflow. Shows status, collects input, displays artifacts.
6. **Gitea** = Source of truth for code. Issues derived from task files. PRs for human review.
