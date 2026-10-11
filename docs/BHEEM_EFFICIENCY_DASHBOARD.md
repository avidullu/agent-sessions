# Agent Sessions and Bheem: checkpoints and efficiency

The local efficiency dashboard joins sanitized collection health with actual
Bheem checkpoint-plan decisions, opaque session/worktree bindings and imported
workload observations. It helps an operator see missing evidence before changing
capture frequency or execution policy. No transcripts, prompts, provider paths,
configured source names or remote assets enter the report.

This is an offline artifact integration seam. It runs no manifest command,
installs no scheduler, fetches no package and admits no execution. A checkpoint
selected by a planner is separate from an observed run and from a successful
required CI context. The implementation slice is tracked as DR9 in
[the durable sessions project](DURABLE_SESSION_RESEARCH_PROJECT.md).

## Run the synthetic demo

Python 3.11 or newer is sufficient; no package installation is needed when
running from the checkout:

```bash
python3 tools/agent_archive.py efficiency demo \
  --output /tmp/agent-efficiency-demo --serve
```

The output directory must be new. It is created with mode `0700` on POSIX, with
`0600` HTML and JSON files. The command prints an ephemeral loopback URL. Open it
in a browser; Ctrl-C closes only this foreground server. The synthetic banner
appears before any numbers. The fixture uses a fixed UTC snapshot clock so the
same package and plan states reproduce each time.

Only `/` and `/index.html` serve an immutable in-memory HTML page. The server
never exposes `report.json`, adjacent files or a directory listing, and never
logs request paths. It binds `127.0.0.1`, uses no external assets and includes a
CSP that forbids network connections. It neither stops an existing listener nor
uses ambient PID files. Omitting `--serve` produces a file-only snapshot.

The mode bits are a POSIX privacy measure. Native Windows applies its existing
filesystem ACLs; this command does not configure Windows ACLs or publish a page.

## Generate a local report

```bash
python3 tools/agent_archive.py --repo-root /path/to/archive-workspace \
  efficiency report --output /path/to/new-private-snapshot \
  --bindings /path/to/checkpoint-bindings.json \
  --plan /path/to/bheem-plan.json \
  --run /path/to/workload-observation.json

python3 tools/agent_archive.py efficiency render \
  --report /path/to/private-snapshot/report.json \
  --output /path/to/new-render --serve
```

All integration inputs are optional for `report`. Missing inputs remain visible
as unavailable. `--run` is repeatable. The command reads only the configured
archive catalogs and local artifact metadata through the existing collection
health API; it does not walk provider stores or reparse their transcripts.
Existing export fingerprints continue to own incremental export behavior. This
view does not measure the bytes read, CPU used or savings of those exports.

Collection counts describe valid merged catalog rows, including the existing
Router deduplication rules. A malformed catalog retains its readable evidence
and sets incomplete counts; an unreadable or refused catalog leaves aggregate
session/message counts null. Source availability is a reported operational state,
separate from collection completeness. Source aliases are ordinal identifiers
within the current configuration, not durable cross-machine identities. Unknown
provider kinds are represented as `inventory`; custom source names are omitted.

Catalog inputs are regular files with one link, each bounded to 16 MiB. Other
integration JSON is bounded to 1 MiB, 16 levels of nesting and bounded objects
and arrays. Links, FIFOs, changed inode, duplicate JSON keys, nonfinite numbers,
unsupported fields and private/secret-shaped metadata are refused with constant
diagnostics that do not echo input. A refused catalog becomes unreadable health;
a refused integration document fails report creation. Existing output is never
replaced. Snapshot files stay outside source control and must not be uploaded as
part of a public PR or package.

## Versioned contracts

The output is `agent-sessions.efficiency-report.v1` with:

| Field | Meaning |
| --- | --- |
| `generated_at`, `synthetic` | Explicit UTC snapshot clock and sample-data marker |
| `collection` | Allowlisted health projection, nullable counts, completeness, catalog states, source aliases and evidence gaps |
| `bindings` | Opaque session/worktree IDs, exact checkpoint identity, timestamped package declarations and derived blocked/declaration states |
| `actions` | Projected actual `bheem.checkpoint.plan.v1` decisions and per-action observation timestamps; stale plans remain marked |
| `runs` | Structurally checked `bheem.workload-run.v1` metadata, qualities/scopes and an exact-identity binding when unique |
| `comparison` | Explicitly unavailable until a supported matched before/after comparison integration exists |

The binding input schema is `agent-sessions.bheem-bindings.v1`:

```json
{
  "schema": "agent-sessions.bheem-bindings.v1",
  "generated_at": "2026-10-11T10:30:00Z",
  "bindings": [
    {
      "session_id": "session-opaque-a",
      "worktree_id": "worktree-opaque-a",
      "checkpoint_id": "<Bheem checkpoint ID: 64 lowercase hex>",
      "identity": "<full Bheem checkpoint Identity object>",
      "package": null
    }
  ]
}
```

Angle-bracket strings above describe required producer values; they are not a
valid runnable manifest. The fully runnable synthetic shape is checked in as
[the demo fixture](../agent_sessions/efficiency_demo.json).

The checkpoint identity includes repository/PR, recipe/workflow, exact source and
base Git IDs, recipe/toolchain/dependency/configuration SHA-256 digests and
required contexts. The checkpoint hash reproduces Go's typed field order,
sorted contexts and JSON escaping, including ampersands, angle brackets and
Unicode line separators. Conformance tests use Bheem's actual Go-produced
[first-window plan](../tests/fixtures/bheem_checkpoint_plan.json), plus an
independently Go-produced escaping golden.

An optional package object requires `digest`, `closure_digest`, `cache_digest`,
`created_at`, `expires_at`, the same full `identity`, `download_policy` and
`evidence_digest`. Digests use `sha256:` with 64 lowercase hex characters. A
missing package, expired timestamp, mismatched identity or policy other than
`deny` derives a blocked binding. There is no fetch fallback. Even a current
matching package remains `declaration_bound`, with
`package_content_unverified` and `no_egress_execution_unverified` reasons.

Digest-shaped metadata and a matching checkpoint hash do not establish that
package bytes exist, that every dependency is installed, that the closure is
complete or that a workload actually ran without egress. Those checks belong to
Bheem's content verifier and actual executor. A policy declaration is not a
traffic counter or a signed receipt.

### Plan and resource semantics

The plan adapter projects actions from `bheem.checkpoint.plan.v1`; it does not
reimplement or validate the selector's entire persistent state machine. Use
Bheem's selector/validator for that authority. Accepted plans are `PLANNED` in
`shadow` or `dispatch` mode. Future observations are refused and plan
observations older than 30 minutes are shown as stale. `select`, `defer`,
`supersede` and `cancel-candidate` retain their actual meanings. Counts apply only
to the supplied plan; a superseded intent does not prove an avoided build.

The workload adapter validates the fields needed by the local observation seam,
including identities, units, qualities, scope, outcome contradictions, timestamps,
collector omissions and network boundary. Bheem's full validator remains the
upstream authority. Imported observations are unsigned and their declared
identity does not prove the executed checkout, tests or package contents. A run
matches a binding only when repository, PR, source/base and all four assurance
digests match exactly; unbound runs remain unbound.

CPU uses `CPU-s`; elapsed/queue use seconds. Peak memory is a maximum, not an
integral or an additive host total. No arbitrary cross-run totals are displayed.
A failed or partial run keeps its consumption and omissions. Known traffic,
including numeric zero, requires `network_boundary.kind=counter` with source,
version, scope and evidence digest; each metric must use that scope. `isolation`
and `download_policy=deny` do not authorize a traffic value. Unavailable traffic
requires a null and a reason and never becomes zero.

A future comparison must match the actual source/base/recipe/toolchain,
dependency/configuration, machine/surface/host class, known cache state, declared
limits, observed controls, collector scope/version/coverage and test evidence.
Keep preparation, failed attempts and missing traffic evidence visible before
claiming overall CPU, RAM or network savings.

### Bheem collection dashboard compatibility

This report deliberately does not produce `agent-sessions.collection-report.v1`
from Bheem's separate collection dashboard. That schema requires numeric
per-source files/records/messages/bytes and a staging count. Current collection
health does not supply all of those measurements. Converting unknown values to
zero would fabricate completeness. A later producer must measure those fields
or introduce a mutually reviewed nullable contract before enabling a live feed.

## UX review and walkthrough

The layout puts collection completeness and unavailable savings beside the
reported volume. Checkpoint rows expose action reasons, observation time,
package blockers and exact identity details. Resource rows retain each metric's
quality and reason, with collector limits available on demand. This follows
[visibility of system status](https://www.nngroup.com/articles/visibility-system-status/)
and the principle that status must explain what the operator can do next.

Search and action filters work in the page without fetching data. Keyboard focus,
labels, a skip link, responsive wrapping, scrollable tables and control targets
of at least 44 CSS pixels support inspection on desktop and mobile. The target
choice is informed by the
[W3C target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).
This is a heuristic design review with browser verification, not participant
research or a full WCAG certification.

1. Launch the synthetic demo and confirm the banner appears before counts.
2. Inspect the collection cards and evidence gaps. Available sources coexist
   with incomplete collection; missing traffic does not show zero.
3. Search `session-hub`, then choose `Deferred`: its missing package stays blocked.
4. Clear search, choose `Selected`, and expand identity/package details. Compare
   exact source/base and closure digests with the declaration-bound state.
5. Inspect per-run CPU, memory and unavailable traffic. Expand collector/limits;
   no overall savings percentage or combined memory peak is produced.
6. Resize to a phone viewport and navigate with the keyboard. Tables scroll
   horizontally while headings and controls remain readable.
7. Request `/report.json`: the local server returns 404. Stop with Ctrl-C;
   saved private files remain for deliberate local inspection.

## Next integration steps

Connect approved producers of opaque binding metadata and Bheem's actual plan
and run outputs. Keep private logs and shared dependency closures in separate
stores. Add authenticated package-content verification and actual executor
no-egress/reservation evidence before displaying an admitted state. Automatic
transport, production scheduler cutover and matched economics are separate
implementation work; this PR leaves them unimplemented.
