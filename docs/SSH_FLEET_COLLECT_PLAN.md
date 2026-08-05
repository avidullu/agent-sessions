# SSH Fleet Collect — Primary-Host Session Pull

> **Status:** `DRAFT` — owner-gated design (docs-only; no implementation in this PR)
> **Owner:** `avidullu` · **Created:** `2026-08-05` · **Last updated:** `2026-08-06`
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived` (move to `docs/archives/` when DONE)
> **Tracking anchors:** §7 progress tracker is the source of truth; indexed in `docs/README.md`
> **Relation to existing docs:** peer-of / extends [MULTI_MACHINE.md](MULTI_MACHINE.md),
> [AUTOMATION.md](AUTOMATION.md); complements local-export primary-host mode
> **Honesty note:** claims marked `[design]` unless noted; discovery heuristics need a spike.

---

## 0. TL;DR

Make **one primary machine** (the WSL/Linux clone with the full archive) the
orchestrator for a **fleet of SSH-reachable machines**. The primary uses an
explicit allowlist and periodically (default **hourly**, lightweight) probes
those hosts for agent session stores, **pulls only new/changed session files**,
and exports and indexes them into the primary catalog. A separate manual command may push one exact,
finalized catalog snapshot to a selected remote only after scoped, single-use
approval; the scheduler never ships data back. No second competing archive repo
is required on remote boxes.

## 1. Problem & goal

### Why now

Today multi-machine convergence assumes either:

1. each machine runs export and pushes catalog metadata to a **private** remote, or
2. the primary can already **see** remote stores (e.g. WSL `/mnt/c` for Windows).

SSH-only machines (another laptop, a lab box, a cloud VM) leave sessions stranded
unless the user manually copies paths or maintains a second clone. After
establishing a single primary host + local-export schedule, the natural next step
is **pull-based fleet collection** over SSH. `[design]`

### Goal

| Outcome | Definition of good |
| --- | --- |
| Discover | Primary can list candidate SSH hosts the user already uses (config + explicit allowlist) |
| Collect | New command(s) pull remote session sources (or remote export packs) into the primary archive |
| Schedule | Default **hourly** lightweight probe; full transfer only on change |
| Index | Primary `archive/index.jsonl` is the unified catalog (existing merge identity) |
| Ship-back | Optional manual push of one exact artifact set after scoped, single-use approval |
| Safety | No unsolicited writes to remotes; no secrets in tracked trees; fail closed on unknown hosts |

### Non-goals (this plan)

- Replacing the private-git multi-machine catalog model for users who prefer it
- Running a permanent agent daemon on every remote
- Auto-installing agent-sessions on remotes without consent
- Real-time tailing of live sessions (hourly is enough; watcher is later)

## 2. Decisions locked

| # | Decision | Source / date | Implication |
|---|----------|---------------|-------------|
| D1 | **Primary pulls; remotes do not push by default.** | This doc, 2026-08-05 | Fits NAT, laptops, and “one truth” mental model |
| D2 | **Default schedule is hourly lightweight check**, not daily full export. | Owner request | Compare per-file manifests; transfer deltas; run periodic digest reconciliation |
| D3 | **Ship-back is manual and approval-gated.** Approval is single-use and scoped to host, destination, artifact set, and digest. | Owner request + security review, 2026-08-06 | The hourly path never ships; catalog changes invalidate approval |
| D4 | **Prefer pull of raw agent stores + export on primary** over remote-side full product install. | Design | Reuses extractors; remotes need only SSH + readable paths |
| D5 | **Explicit fleet allowlist and a pre-verified host key are required for collect** (`fleet.toml` or CLI hosts); SSH config is discovery-only. | Security | Prevents scanning random `Host` entries or accepting an unattended first-use key |
| D6 | **Machine id** recorded as `source_origin` must be a non-sensitive label, never a username or real hostname. | Aligns with portable paths | Status can show per-host freshness without publishing private identifiers |
| D7 | **Reuse local-export / export / merge_index_records**; do not invent a parallel catalog format. | Existing archive | Smaller surface area |
| D8 | **No auto-commit/push to public remotes** as part of fleet jobs. | Public launch privacy | Same rule as local-export |
| D9 | **Remote names, roots, manifests, and files are untrusted input.** | Security review, 2026-08-06 | Central command encoding, regular-file-only transfer, staging containment, and adversarial tests are required |

## 3. Foundation — research / prior art

| Source | Lesson |
| --- | --- |
| [MULTI_MACHINE.md](MULTI_MACHINE.md) | Catalog merge by `session_id` + content hash; origins from path |
| [AUTOMATION.md](AUTOMATION.md) | Local-only primary vs private catalog sync; no personal catalog on public remotes |
| Existing `export` + `merge_index_records` | Already multi-origin; fleet is another source of files |
| SSH `~/.ssh/config`, `known_hosts`, ControlMaster | Discovery + connection reuse for hourly probes |
| `rsync` / `scp` / `sftp` | Delta transfer; prefer rsync when available |
| Remote Windows via OpenSSH | Paths differ (`C:\Users\<user>\...`); map via fleet host profile |

Spike needed `[design]`: cheapest per-file manifest and tail-digest probe per OS
without shipping a full agent binary, plus the cost bound for daily full-digest
reconciliation.

## 4. Design / architecture

### 4.1 Roles

```
┌─────────────────────────────────────────────────────────┐
│ PRIMARY (archive SoT)                                   │
│  agent-sessions clone + sources.toml + fleet.toml       │
│  cron/timer: fleet collect --light (hourly)             │
│  archive/index.jsonl  ←  unified catalog                │
│  archive/<source>/    ←  rendered Markdown (local)      │
└───────────────┬─────────────────────────────────────────┘
                │ SSH (pull)
     ┌──────────┼──────────┬──────────────┐
     ▼          ▼          ▼              ▼
  laptop-b   work-vm    phone-ssh?    windows-ssh
  ~/.claude  ~/.codex   (if any)      C:\Users\<user>\.claude
```

Remotes are **session producers**, not archive peers. They receive a mirror only
when the user runs the separate, explicitly approved ship-back command.

### 4.2 Config: `fleet.toml` (gitignored)

Suggested shape (illustrative):

```toml
[fleet]
primary_id = "wsl-home"          # optional human label
default_interval = "1h"
light_probe = true
# Ship-back has no scheduler switch; it is always a separate manual command.

[[hosts]]
id = "windows-laptop"            # non-sensitive label; appears in tracked catalog metadata
ssh = "workstation-b"            # Host alias from ~/.ssh/config
os = "windows"                   # windows | linux | darwin
enabled = true
# Roots on the remote (absolute or ~ expanded remotely)
roots = [
  { kind = "claude", path = "~/.claude/projects", glob = "**/*.jsonl" },
  { kind = "codex", path = "~/.codex/sessions", glob = "**/*.jsonl" },
  { kind = "codex", path = "~/.codex/archived_sessions", glob = "**/*.jsonl" },
]

[[hosts]]
id = "lab-ubuntu"
ssh = "lab.example"
os = "linux"
enabled = true
roots = [
  { kind = "claude", path = "~/.claude/projects", glob = "**/*.jsonl" },
  { kind = "grok", path = "~/.grok/sessions", glob = "**/chat_history.jsonl" },
]
```

- File is **gitignored** (like `sources.toml`).
- Example file: `fleet.example.toml` in-repo.
- `id` must be a non-sensitive stable label matching `[a-z0-9-]+`; it becomes
  tracked origin metadata. It is also part of staging paths, e.g.
  `archive/fleet-windows-laptop-claude/` or staging under `raw/fleet/<id>/…`
  then export with a dedicated source name. `[design]` exact naming in P2.

### 4.3 CLI surface (proposed)

```text
agent-archive fleet discover [--ssh-config PATH] [--write archive/.fleet/candidates.md]
agent-archive fleet status
agent-archive fleet collect [--host ID]... [--light|--full] [--dry-run]
agent-archive fleet approve-ship --host ID --what catalog --destination PATH
agent-archive fleet ship --approval ID [--dry-run]  # consumes exact approval
```

| Command | Behavior |
| --- | --- |
| `discover` | Read `~/.ssh/config` Host entries (and optional recent `known_hosts`); probe `ssh -G` / `BatchMode` connectivity; **do not** collect. Write private host aliases/paths only to owner-readable gitignored operational state (default `archive/.fleet/candidates.md`), never a tracked docs path. |
| `status` | For each enabled host: last probe time, last successful collect, lag, error. |
| `collect --light` | **Default for hourly job.** Per host: compare a per-file manifest (relative path, type, size, high-resolution mtime, tail digest) with the local ledger. If unchanged → skip. If changed → pull deltas only, then export. A scheduled full-digest reconciliation catches metadata-preserving edits. |
| `collect --full` | Force full inventory + pull (manual recovery). |
| `approve-ship` | Record a single-use approval for one host, dedicated destination, artifact set, and current content digest; print the approval id. |
| `ship` | Recompute the digest, require an exact unexpired approval, atomically publish to the dedicated mirror directory, then consume the approval. Never called by a timer. |

Entry points also available as `python tools/agent_archive.py fleet …`.

### 4.4 Collect pipeline (primary)

1. **Load and validate** `fleet.toml`: strict schema, unique non-sensitive ids,
   supported kinds, absolute/`~` roots, no control characters, and no wildcard
   SSH aliases. Create operational state with owner-only permissions (`0700`
   directories, `0600` manifests/logs on POSIX; current-user ACL on Windows).
2. **Resolve and verify** each allowlisted alias with `ssh -G`; connect with
   `BatchMode=yes`, a timeout, and `StrictHostKeyChecking=yes`. An absent or
   changed host key is a hard per-host failure, never an unattended TOFU prompt.
3. **Probe through one tested command boundary.** Never concatenate config values
   into an ad hoc remote shell string. A versioned, checksummed probe and a
   centralized POSIX/PowerShell argument encoder must handle spaces, quotes,
   leading dashes, and metacharacters; adversarial path fixtures pin this.
4. **Return a per-file manifest** of relative path, regular-file type, byte size,
   high-resolution mtime, and tail digest. Reject absolute paths, `..`, duplicate
   paths, symlinks, devices, and entries outside the configured root.
5. **Compare** with the last successful manifest in gitignored
   `archive/.fleet/ledger.jsonl`. Select deltas by manifest identity—not solely by
   “newer than” watermarks, which are unsafe under clock skew. Run a bounded full
   content-digest reconciliation at least daily to catch edits that preserve file
   metadata; advance state only after transfer and export both succeed.
   A remote deletion records an operational tombstone but never deletes an
   archived session or enables a destructive rsync mode.
6. **Transfer into a private temporary sibling directory** beneath
   `raw/fleet/<host_id>/<kind>/` using a literal generated file list. Prefer
   rsync; a fallback must preserve the same no-symlink and containment contract.
7. **Validate staging again** before atomic promotion: every resolved path stays
   beneath staging, is a regular file, matches the manifest size/digest, and has
   an allowed extension. A failed/partial transfer never replaces the prior copy.
8. **Export**: temporary or permanent `Source` entries pointing at staged roots
   with names like `fleet-<host_id>-claude`, kind mapped from config.
9. **Merge** into `archive/index.jsonl` via existing merge identity
   (`session_id` + `sha256`) so SSH-pulled and local-visible copies of the same
   session collapse.
10. **Commit operational state atomically** only after success. Record a
    redacted per-host outcome for status and the next light run.

### 4.5 Ship-back (approval-gated)

After primary has indexed, the user may want remotes to hold a **read-only
catalog mirror** for offline use. Rendered transcripts are outside the v1
ship-back scope.

| Artifact | Default ship? | Notes |
| --- | --- | --- |
| `archive/index.jsonl` + `INDEX.md` | Optional | Useful; still may contain portable paths — user accepts |
| Full `archive/**/*.md` | **Not in v1** | Revisit only with a separate privacy/volume design |
| `raw/` | **Never** | Secrets risk |
| `sources.toml` / `fleet.toml` | **Never** | Machine-local |

Approval model `[design]`:

```bash
agent-archive fleet approve-ship \
  --host lab-ubuntu --what catalog --destination agent-sessions-mirror
agent-archive fleet ship --approval <approval-id>
```

The approval records the resolved host key fingerprint, dedicated destination,
artifact list, aggregate content digest, and a short expiry. `ship` refuses any
mismatch, publishes through a temporary sibling plus atomic rename, and consumes
the approval on success. The destination must be a configured mirror directory;
the command never overwrites an arbitrary or unmanaged path. The hourly timer
**never calls `ship`**, regardless of approval state.

Remote destination: a dedicated path such as `~/agent-sessions-mirror/` declared
in `fleet.toml` (`ship_path`). Primary uses a containment-checked rsync push.
Remotes do not need a full product install to receive a mirror.

### 4.6 Scheduling

| Job | Default | Script |
| --- | --- | --- |
| Local sources | Daily (existing local-export) | `scripts/local-export.sh` |
| Fleet light collect | **Hourly** | `scripts/fleet-collect.sh` → `agent-archive fleet collect --light` |
| Fleet ship | Manual / rare | No default timer |

Installer (P-series):

```bash
./scripts/install-fleet-collect-schedule.sh   # systemd user timer or cron hourly
```

`fleet-collect.sh` properties:

- Atomic ownership-checked lock directory (no concurrent collect; no unsafe age eviction)
- Per-host timeout budget so one dead host cannot block the hour
- Append logs under `~/.local/share/agent-sessions/logs/`
- Continue across hosts, then exit non-zero if any enabled host failed so the
  scheduler can surface degraded collection; reserve a distinct exit for hard
  config errors. The status ledger preserves per-host outcomes.

### 4.7 Host discovery heuristics

`fleet discover` may suggest hosts from:

1. `~/.ssh/config` `Host` entries with `HostName` (skip wildcards `*`)
2. Optional: hosts the user SSH’d to recently (`~/.ssh/known_hosts` names only)
3. Optional: `ProxyJump` graphs (list only; do not auto-enable)

Every suggestion is **disabled until copied into `fleet.toml` with roots**.
Connectivity probes use `BatchMode=yes` and strict host-key verification. A
candidate is not collectable until its key is already present and verified in
the selected `known_hosts` file.

Windows OpenSSH remotes: document path conventions; probe via `powershell -NoProfile -Command …` when `os = "windows"`.

### 4.8 Origin and identity

- Staged files keep remote absolute path in metadata before portable rewrite.
- `source_origin` encodes the required non-sensitive fleet host id,
  e.g. `fleet-host:windows-laptop` (extend `portable_origin` or set explicitly on
  fleet sources). `[design]` implementation detail in P2.
- Dedup with sessions already imported via `/mnt/c` uses existing sha/session_id
  merge — expected and desirable.

### 4.9 Security & privacy

| Risk | Mitigation |
| --- | --- |
| Collect from unintended / impersonated host | Allowlist plus pre-verified host key; strict checking on every unattended connection |
| Shell or argument injection | Strict config validation, one centralized OS-specific encoder, no ad hoc interpolation, adversarial tests |
| Symlink / path traversal reads | Regular files only; reject absolute, `..`, symlink, device, duplicate, and resolved-outside-root entries before and after transfer |
| Credential leakage in logs | Log host ids, not full ssh -v; no passwords |
| Secrets in pulled raw JSONL | Private filesystem permissions under gitignored `raw/`; export remains subject to PII tooling on tracked catalog |
| Remote write accidents | Manual-only ship to a dedicated mirror; exact-digest, scoped, single-use approval and atomic publish |
| Public remote push | Fleet jobs never git push |
| Supply-chain on remote scripts | Versioned small probe checksummed in-repo; verify the transmitted content/version before parsing results |

## 5. Threat model / risk table

| ID | Risk | Likelihood | Impact | Handling |
| --- | --- | --- | --- | --- |
| T1 | Hourly SSH load / battery | Med | Low | Light probe; skip if unchanged; ConnectTimeout |
| T2 | Partial pull corrupts staging | Low | Med | Private temporary staging, manifest verification, atomic promotion; ledger advances only after export |
| T3 | Same session dual-home diverges | Med | Low | Preserve distinct digest variants under existing merge identity and surface the divergence; never silently choose “latest” |
| T4 | Stale/broad approval ships unexpected data | Low | High | No global/scheduled ship; approval binds host key, destination, files, and exact digest, then is consumed |
| T5 | Windows path / permission failures | Med | Med | Host `os` profile + clear status errors |
| T6 | Metadata-only light probe misses a changed file | Med | Med | Per-file tail digest plus bounded daily full-digest reconciliation; never rely only on max mtime |
| T7 | Malicious remote manifest escapes staging | Low | High | Treat manifest as untrusted; validate path/type/uniqueness/containment before and after transfer |

## 6. Honest limits — what this does NOT do

- Does not replace vendor cloud sync for agent products
- Does not guarantee a coherent snapshot of an **in-progress** live session;
  manifest/digest comparison picks up a later stable version on a subsequent run
- Does not auto-configure SSH keys or Tailscale
- Does not run on remotes without SSH access
- Does not claim macOS probe parity until validated (same stance as hub overall)
- Does not by itself create a multi-primary HA setup

## 7. Deliverables & progress tracker   ⟵ **source of truth**

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated. **One small PR per row.**

Every implementation PR updates its own row and this document's changelog. A
row is not complete until its code, required tests, and green CI have shipped;
work parked in an issue remains `Deferred`/incomplete rather than being counted
done.

| ID | Deliverable | Depends on | Gated? | Status | PR |
|----|-------------|-----------|--------|--------|----|
| P0 | This design doc + docs index / MULTI_MACHINE pointer | — | No | ☑ | this PR |
| P1 | `fleet.example.toml`, ignored `fleet.toml`, strict config validation, and help-only `fleet` CLI whose unimplemented functional commands fail clearly | P0 | No | ☐ | — |
| P2 | Manual `fleet collect` for **one** Linux host: strict SSH boundary, manifest probe, private/contained atomic staging, rsync delta, export, ledger, and unit/fixture tests | P1 | No | ☐ | — |
| P3 | Light vs full/daily-digest reconciliation, per-host timeouts, honest aggregate exit status, `fleet status`, and ledger/failure tests | P2 | No | ☐ | — |
| P4 | `fleet discover` (SSH config → disabled candidates report + suggested TOML), strict host-key behavior, and parser/probe tests | P1 | No | ☐ | — |
| P5 | Windows OpenSSH host profile (encoded probe + pull paths) with native-Windows and adversarial-path tests | P2 | No | ☐ | — |
| P6 | Hourly cron installer `install-fleet-collect-schedule.sh`, atomic lock/recovery, failure visibility, tests, and AUTOMATION.md section | P3 | No | ☐ | — |
| P7 | Manual `approve-ship` + atomic `ship` (catalog only), exact single-use approval ledger, containment checks, and denial-path tests | P3 | No | ☐ | — |
| P8 | End-to-end fault/adversarial matrix: partial transfer, symlink/traversal, shell metacharacters, changed host key, clock skew, and metadata-preserving edit | P2–P5 | No | ☐ | — |
| P9 | Docs polish, FAQ / GETTING_STARTED section, inbound-reference verification, completion audit, and tracker archival | P4–P8 | No | ☐ | — |

### Suggested execution order for next sessions

1. Merge this docs PR after review.
2. Implement **P1 → P2 → P3** (end-to-end Linux path is the MVP).
3. Add **P4/P5**, then the **P8** robustness matrix.
4. Add **P6** hourly scheduling only after the collection path is trustworthy.
5. Implement **P7** ship-back last (highest foot-gun), then close with **P9**.

## 8. Open questions — owner / external

| # | Question | Default if unset |
|---|----------|------------------|
| Q1 | Stage under `raw/fleet/` only, or also mirror into normal source names? | `raw/fleet/` + synthetic source names at export |
| Q2 | Full content-digest reconciliation interval? | 24h, while hourly light probes retain per-file tail digests |
| Q3 | Ship-back approval expiry? | 1h; still single-use and exact-digest scoped |
| Q4 | systemd user timer vs cron for hourly? | cron for parity with local-export installer; document both |
| Q5 | Require `rsync` or support a fallback? | rsync preferred; explicit file-by-file SFTP fallback for small deltas |
| Q6 | Include Android/Termux or only “real” SSH desktops? | desktops/VMs only in v1 |

## 9. Definition of done

- [ ] User can allowlist ≥1 SSH host in `fleet.toml` and run `fleet collect --light`
- [ ] Unchanged hosts produce near-no-op hourly runs (seconds, no full tree copy)
- [ ] New remote sessions appear in primary `archive/index.jsonl` with fleet origin
- [ ] Duplicate of a session already on primary collapses via existing merge rules
- [ ] Missing/changed host keys, unsafe paths/types, partial transfers, and command metacharacters fail closed in tests
- [ ] Scheduler reports any enabled-host failure and never advances failed-host state
- [ ] Ship-back cannot run with a missing, expired, reused, wrong-destination, or wrong-digest approval
- [ ] Docs describe primary-host + fleet vs private-git multi-machine clearly
- [ ] No personal fleet config or raw pulls committed to public remotes
- [ ] Every implementation row ships its own tests; full lint, type, test, privacy, link, and coverage gates remain green

## 10. References

**Internal:**

- [MULTI_MACHINE.md](MULTI_MACHINE.md)
- [AUTOMATION.md](AUTOMATION.md)
- [NEW_MACHINE_SETUP.md](NEW_MACHINE_SETUP.md)
- [OUTPUT_CONTRACT.md](OUTPUT_CONTRACT.md)
- `agent_sessions/archive.py` (`merge_index_records`, export)
- `agent_sessions/portable_paths.py` (origins)
- `scripts/local-export.sh` / `install-local-export-schedule.sh`

**External:**

- OpenSSH `BatchMode`, `ControlMaster`
- rsync daemonless over SSH

### Changelog

- `2026-08-06` — Review hardening: strict SSH trust and command boundary,
  contained/private staging, digest reconciliation, honest failure status,
  single-use exact ship approval, and tests delivered with each implementation row.
- `2026-08-05` — Initial DRAFT design for SSH fleet collect + hourly light probe + approval-gated ship-back.
