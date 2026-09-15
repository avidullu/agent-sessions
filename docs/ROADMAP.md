# Roadmap

> **Status:** `Active (reference)` · **Owner:** `avidullu` · **Last updated:** `2026-09-15`
> Future importers and features; intentionally local-first.

This archive is local-first: importers should prefer session data stored on
owned CPU/RAM and local disks, including Windows and WSL paths.

Start with [Product direction and code map](PRODUCT_DIRECTION.md) for the north
star and honest shipped-versus-planned boundaries. Priority is a dependable
first archive, then a useful reviewed lesson—not importer count alone.

## Delivery order

1. **Now:** retain the installed hub/router onboarding and collection-health
   checks; finish release readiness and the [baseline user journey](BASELINE_USER_GUIDE.md).
2. **Next design discussion:** single-host, owner-attested handoff bridge (#149).
   Agree on source binding and stale/concurrent-write refusal before coding
   external-memory writes. Existing `baseline promote` is not that bridge.
3. **Then:** bounded local collector slices from the design below; preserve
   existing export identity and catalog contracts.
4. **Later:** fleet SSH collection, hosted export inboxes and broader synthesis
   after the local path is proven. Keep behavior-preserving refactors (#94/#95)
   separate from new parsing or publication semantics.

Search and live-memory features are intentionally delegated to the compose stack
instead of rebuilt here; see [COMPOSE_STACK.md](COMPOSE_STACK.md). Curated
instruction/project-memory continuity is a sibling control plane, not a roadmap
item for this archive; see [XDSYNC_BOUNDARY.md](XDSYNC_BOUNDARY.md).

## Active design: collector + non-code + session-intel

Canonical design (ready for implementation PR plan):
[designs/SESSION_COLLECTOR_AND_INTEL.md](designs/SESSION_COLLECTOR_AND_INTEL.md).

It covers the continuous lightweight **collector** (evolves daily-export),
chat/non-code catalog extension (official export inbox, no UI scraping), and
the **`session-intel`** synthesis path (routines, periodic-task candidates,
propose-only skills)—distinct from engineering baseline.

## Future Features

- Continuous collector agent (`agent-archive collect`) with health, settle, and
  shared write lock; see the design above. Daily scripts become thin wrappers.
- Optional hosted/cloud session import adapters if a tool later moves chat
  history off-device. Prefer official APIs, explicit export folders, or vendor
  extension hooks over UI scraping.
- Chat export inbox for official JSON/Markdown exports from web/app products
  (ChatGPT, Claude.ai, etc.); see design P1.
- Engineering baseline extraction that turns repeated session lessons into
  reviewable guardrails and agent-specific instruction files.
- Agent-assisted proposal generation that uses bounded, reasonable access to
  sessions, repos, PRs, issues, CI logs, and local instruction files to draft
  reviewable baseline candidates.
- Session-intel routine / skill proposals (propose-only; never auto-write agent
  memory); see design P2.
