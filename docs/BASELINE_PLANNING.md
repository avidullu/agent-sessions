# Engineering Baseline Planning

Status: draft
Date: 2026-07-05

## North Star

Build a portable engineering baseline system that learns from agent sessions,
repositories, reviews, CI, docs, and user corrections, then proposes durable
guardrails and project knowledge for future work.

The system should support personal repos first, then scale to teams,
organizations, and client onboarding. A future user should be able to point it
at a new codebase or organization and get a reviewable onboarding plan, a map of
important project knowledge, and candidate guardrails for agent-assisted work.

## Pilot Scope

Start with a small but representative corpus:

- `badminton-highlight-indexer`: mothership project and primary source of tribal
  knowledge.
- `muneem`: newer project with useful upserts from newer agents and workflows.
- Telegram-related repo: workflow and integration-heavy pilot.
- `avidullu` GitHub account: broader personal repo inventory and cross-project
  patterns.
- `KhelSutra` GitHub organization: organization-style pilot and future team
  sharing candidate.

The first implementation should not assume these names are permanent. They are
seed candidates for configuration and evaluation.

## Product Shape

The baseline has four layers:

1. Evidence: archived sessions, repo docs, code, PRs, issues, CI logs, and local
   agent instruction files.
2. Candidates: proposed rules, patterns, project facts, and onboarding notes with
   provenance.
3. Promoted baseline: reviewed guidance accepted into global or project-specific
   baseline files.
4. Published agent views: generated Codex, Claude, and VS Code-supportive files
   kept separate from hand-written project instructions until the system earns
   enough trust.

## Suggest Interface

Use Markdown first because it is reviewable in GitHub PRs, easy to edit, and
works with any agent.

Suggested layout:

```text
baseline/
  candidates/
    2026-07-05-extraction.md
  global/
    engineering-guardrails.md
    repo-workflows.md
    regression-frameworks.md
    prompt-patterns.md
  projects/
    badminton-highlight-indexer/
      overview.md
      decisions.md
      pitfalls.md
      test-and-release.md
    muneem/
    telegram/
  agents/
    codex/AGENTS.generated.md
    claude/CLAUDE.generated.md
    vscode/copilot-instructions.generated.md
```

Candidate entries should be structured enough to promote later:

```markdown
## PR-Only Repo Writes

Status: proposed
Scope: global
Risk: high
Confidence: strong
Category: repo-governance

Evidence:
- Session or PR reference
- User correction or incident reference

Suggested baseline text:
Agents must not push directly to shared or durable repos. Create a branch,
commit there, open a PR, and merge only after explicit approval or scoped
umbrella authorization.

Promotion:
- [ ] Accept
- [ ] Edit and accept
- [ ] Reject
- [ ] Project-specific only
```

## Approval Model

Approval policy should be explicit and machine-readable:

- `strict`: PR required, human approval required. This applies to shared repo
  writes, publishing baseline changes, and any destructive or irreversible
  operation.
- `umbrella`: user grants scoped approval for a batch of related work, such as
  debugging several findings and opening individual PRs.
- `auto-promote`: allowed only for low-risk facts or formatting improvements
  after confidence thresholds are met. It must not apply to repo writes,
  security rules, architecture pivots, or policy changes.
- `observe-only`: capture evidence and suggestions, but do not publish into
  agent-facing instructions.

Direct pushes to durable repos should be treated as a cardinal violation unless
the repo policy explicitly allows it or the user grants an explicit exception.

## What To Extract

The baseline should cover all of these dimensions:

- Repo governance: branch creation, PR discipline, merge approval, release
  etiquette, staging explicit paths.
- Architecture decisions: pivots, trade-offs, ADRs, integration boundaries,
  data model choices.
- Regression frameworks: test commands, coverage floors, lint/type checks,
  fixtures, smoke tests, replay harnesses.
- Coding discipline: local patterns, preferred abstractions, style rules,
  naming conventions, dependency rules.
- Docs freshness: handoff updates, README drift, runbooks, generated docs,
  decision logs.
- Tech debt principles: recurring refactors, cleanup thresholds, known risky
  areas, debt that should not be repeated.
- Checkpointing and resuming: session handoffs, ramp-up kits, open threads,
  "start here" files.
- Work tracking: bugs, follow-ups, deferred ideas, project-specific backlog
  items.
- Prompt and agent patterns: instructions that reliably produce better work,
  common failure modes, corrective phrasing.

## AI-Assisted Proposal Generation

Yes, giving a capable AI agent reasonable access can make the suggestions much
crisper. The useful pattern is not "agent decides the baseline." It is "agent
helps mine evidence and drafts proposals with citations."

Reasonable access tiers:

- Session-only: read archived Markdown/index files and propose candidate
  baseline entries.
- Repo read-only: inspect docs, tests, CI config, git history, and project
  instruction files.
- Collaboration metadata: inspect PRs, issues, review comments, and CI logs.
- Local agent context: inspect Codex/Claude/VS Code instruction files and
  propose generated slices.
- Write access: only for opening branches/PRs or writing candidate files. Merge
  and promotion remain governed by approval policy.

Agent-assisted extraction should follow these rules:

- Every proposal needs provenance.
- Agents should classify risk, scope, category, and confidence.
- Agents should identify contradictions, stale rules, and project-specific
  exceptions.
- Agents should draft concise baseline text, not long transcript summaries.
- Agents should never promote secrets, credentials, private file contents, or
  one-off debug noise.
- Agents should produce suggestions as PR-reviewable Markdown first.

## Interaction Flow

1. User selects a repo, organization, or archive slice.
2. Tool inventories available evidence and records access level.
3. Tool asks an agent to identify patterns and draft proposals.
4. Tool writes candidate Markdown with provenance and confidence.
5. User reviews candidates in a PR or local review file.
6. Accepted candidates are promoted into global or project baseline files.
7. Agent-specific publishers generate separate Codex, Claude, and VS Code files.

## Work Items

### PR 1: Baseline Planning

- Add this planning document.
- Link it from the existing roadmap, baseline overview, README, and handoff.

### PR 2: Baseline Scaffold

- Add baseline directory skeleton and candidate template.
- Add pilot project configuration placeholders.
- Keep generated agent files out of project instruction files for now.
- Add the first metacognition harness: generate explicit predictions, attach
  evidence, and provide feedback hooks for calibration.

### PR 3: Candidate Extractor

- Read `archive/index.jsonl` and selected Markdown transcripts.
- Produce candidate Markdown from deterministic signals first:
  repeated repo names, commands, headings, test gates, user corrections, and
  failure patterns.
- Include provenance links back to archive files.

### PR 4: AI Proposal Adapter

- Add an interface that can hand bounded evidence bundles to an AI agent.
- Require structured proposal output with risk, scope, category, confidence, and
  evidence.
- Keep model-specific wiring replaceable so Codex, Claude, Grok, Gemini, or
  other local/authorized agents can be used later.
- Keep raw evidence bundles ignored by default because future client/org bundles
  may contain private excerpts.

### PR 5: Review And Promote

- Add a manual promotion command.
- Preserve rejected and edited candidate history.
- Write promoted entries into `baseline/global` or `baseline/projects/<repo>`.

### PR 6: Agent Publishers

- Generate separate Codex, Claude, and VS Code-supportive instruction files.
- Keep generated files separate initially.
- Later, support managed sections inside `AGENTS.md`, `CLAUDE.md`, or VS Code
  instruction targets once the output proves useful.

### PR 7: Organization Onboarding

- Inventory repos in an account or organization.
- Identify docs, tests, CI, release workflows, and project instruction files.
- Produce an onboarding plan and baseline candidates for user review.

## Open Questions

- What exact Telegram repo should be named in the pilot config?
- Should `KhelSutra` organization access be read-only at first?
- Which PR/issue providers should be supported first beyond GitHub?
- What confidence threshold should qualify a fact for future low-risk
  auto-promotion?
- Where should VS Code-supportive generated instructions land on each machine?
