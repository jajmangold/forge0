# Requirements Elicitation Protocol

How the requirements agent conducts structured conversations.

## Principles

1. **Conversational, not interrogative.** Ask like a helpful colleague, not a form processor.
2. **Progressive disclosure.** 2-3 questions at a time. Don't dump 20 questions.
3. **Synthesize, don't parrot.** Reflect back what you understood in structured form.
4. **Flag gaps explicitly.** "You mentioned X but didn't address Y — is Y important?"
5. **Confirm before moving on.** Present a summary and wait for approval.

## Interview Flow

### Round 1: Purpose & Users (after initial request)

The user says something like "I need a website." The agent's first job is to understand the *why* and *who*.

**Agent asks:**
> "Tell me more about this — what's it for? Who's going to use it?"
>
> For example: Is it a portfolio site, a SaaS product, an internal tool, a blog, an e-commerce store?

**What the agent extracts:**
- Project type
- Target users
- Core purpose
- Success criteria (implicit)

### Round 2: Features (after understanding purpose)

**Agent asks:**
> "Based on what you've described, I'm thinking the core features would be [X, Y, Z]. What am I missing? What's the most important thing it needs to do on day one?"

**What the agent extracts:**
- MVP feature list
- Priority ordering
- Explicit non-goals ("I don't need X")

### Round 3: Technical Context

**Agent asks:**
> "A few technical questions:
> - Do you have any existing systems this needs to integrate with?
> - Any preferences on tech stack? (Or should I pick what makes sense?)
> - Where will this be hosted?"

**What the agent extracts:**
- Integration requirements
- Tech constraints
- Hosting/deployment preferences
- Existing infrastructure

### Round 4: Design & UX

**Agent asks:**
> "Any design preferences? Do you have a brand/style, or reference sites you like? Should it feel minimal and clean, or bold and colorful?"

**What the agent extracts:**
- Design direction
- Brand elements (if any)
- Reference sites

### Round 5: Data & Auth

**Agent asks:**
> "Let me make sure I understand the data side:
> - Does it need user accounts / login?
> - What kind of data does it store?
> - Any admin features needed?"

**What the agent extracts:**
- Auth requirements
- Data model hints
- Admin/management needs

### Round 6: Synthesis & Confirmation

**Agent presents:**
> "Here's what I've gathered. Let me know if I got anything wrong:
>
> **Project:** [type] — [one-line description]
> **Users:** [who]
> **Core Features (MVP):**
> 1. [feature]
> 2. [feature]
> 3. [feature]
> **Not doing (explicitly):**
> - [non-goal]
> **Tech:** [stack proposal]
> **Design:** [direction]
>
> Does this look right? Anything to add or change?"

**Gate:** User confirms → proceed to architecture. User requests changes → revise and re-present.

## Output Format: requirement.md

```markdown
---
id: REQ-001
title: "Project Name"
status: draft           # draft → in-review → approved → complete
type: greenfield        # greenfield | feature | enhancement
created: 2026-07-15
updated: 2026-07-15
---

## Description

[2-3 sentence description of what this project is and why it exists.]

## Users

- **Primary:** [who uses this daily]
- **Secondary:** [who uses this occasionally]
- **Admin:** [who manages it]

## MVP Features

1. **[Feature Name]**
   - [What it does]
   - Acceptance criteria:
     - [ ] [testable criterion]
     - [ ] [testable criterion]

2. **[Feature Name]**
   - [What it does]
   - Acceptance criteria:
     - [ ] [testable criterion]
     - [ ] [testable criterion]

## Explicit Non-Goals

- [What we are NOT building]
- [What we are NOT building]

## Technical Constraints

- [Any existing systems to integrate with]
- [Hosting requirements]
- [Performance requirements]

## Design Direction

- [Style/brand notes]
- [Reference sites if any]

## Open Questions

- [Anything unresolved]
- [Anything that needs human decision]
```

## Evaluation Criteria

The critic agent checks:

1. **Every feature has acceptance criteria.** No feature without at least one testable criterion.
2. **Criteria are testable.** "Fast" is not testable. "Page loads in under 2 seconds" is.
3. **Non-goals are explicit.** What we're NOT building is as important as what we are.
4. **No contradictions.** Feature A says "real-time" but Feature B says "batch processing" — flag it.
5. **All sections present.** Description, Users, Features, Non-Goals, Constraints, Design.
6. **Frontmatter valid.** id, title, status, type, created, updated.

## Handling Edge Cases

**User is vague:** "Just make something cool."
→ Agent proposes a concrete interpretation and asks for confirmation. Don't try to extract requirements from vagueness.

**User wants everything:** "I need auth, payments, AI, real-time, mobile app, admin panel, analytics..."
→ Agent acknowledges the full vision but scopes MVP to 3-5 core features. Explicitly defer the rest to "future phases."

**User doesn't know tech:** "I don't care about the stack."
→ Agent proposes sensible defaults and explains why. "I'll use Next.js + SQLite because it's fast to get started and easy to deploy. We can change this later."

**User changes their mind mid-conversation:**
→ Agent revises the synthesis. No problem — that's why we confirm before moving on.
