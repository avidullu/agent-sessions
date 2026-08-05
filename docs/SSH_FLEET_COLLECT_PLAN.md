# SSH Fleet Collect — Primary-Host Session Pull

> **Status:** `DRAFT` — owner-gated design (docs-only; no implementation in this PR)
> **Owner:** `avidullu` · **Created:** `2026-08-05` · **Last updated:** `2026-08-05`
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived` (move to `docs/archives/` when DONE)
> **Tracking anchors:** §7 progress tracker is the source of truth; indexed in `docs/README.md`
> **Relation to existing docs:** peer-of / extends [MULTI_MACHINE.md](MULTI_MACHINE.md),
> [AUTOMATION.md](AUTOMATION.md); complements local-export primary-host mode
> **Honesty note:** claims marked `[design]` unless noted; discovery heuristics need a spike.

---

## 0. TL;DR

Make **one primary machine** (the WSL/Linux clone with the full archive) the
orchestrator for a **fleet of SSH-reachable machines**. The primary periodically
(default **hourly**, lightweight) discovers candidate hosts, probes for agent
session stores, **pulls only new/changed session files**, exports and indexes
them into the primary catalog, and—**only after explicit user approval**—may
push finalized catalog/artifacts to selected remotes. No second competing
archive repo is required on remote boxes.

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
| Ship-back | Optional, **approval-gated** push of finalized catalog/artifacts to remotes |
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
| D2 | **Default schedule is hourly lightweight check**, not daily full export. | Owner request | Probe mtimes/hashes first; transfer only deltas |
| D3 | **Ship-back is opt-in and approval-gated** (CLI confirm or approval file). | Owner request | No silent overwrite of remote disks |
| D4 | **Prefer pull of raw agent stores + export on primary** over remote-side full product install. | Design | Reuses extractors; remotes need only SSH + readable paths |
| D5 | **Explicit fleet allowlist is required for collect** (`fleet.toml` or CLI hosts); SSH config is discovery-only. | Security | Prevents scanning random `Host` entries into production collect |
| D6 | **Machine id** recorded as `source_origin` / fleet host id (username-free where possible). | Aligns with portable paths | Status can show per-host freshness |
| D7 | **Reuse local-export / export / merge_index_records**; do not invent a parallel catalog format. | Existing archive | Smaller surface area |
| D8 | **No auto-commit/push to public remotes** as part of fleet jobs. | Public launch privacy | Same rule as local-export |

## 3. Foundation — research / prior art

| Source | Lesson |
| --- | --- |
| [MULTI_MACHINE.md](MULTI_MACHINE.md) | Catalog merge by `session_id` + content hash; origins from path |
| [AUTOMATION.md](AUTOMATION.md) | Local-only primary vs private catalog sync; no personal catalog on public remotes |
| Existing `export` + `merge_index_records` | Already multi-origin; fleet is another source of files |
| SSH `~/.ssh/config`, `known_hosts`, ControlMaster | Discovery + connection reuse for hourly probes |
| `rsync` / `scp` / `sftp` | Delta transfer; prefer rsync when available |
| Remote Windows via OpenSSH | Paths differ (`C:\Users\...`); map via fleet host profile |

Spike needed `[design]`: cheapest “has anything changed?” probe per OS without
shipping a full agent binary (e.g. `find … -newer` / PowerShell `Get-ChildItem`).

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
  ~/.claude  ~/.codex   (if any)      C:\Users\…\.claude
```

Remotes are **session producers**, not archive peers, unless the user enables
ship-back.

### 4.2 Config: `fleet.toml` (gitignored)

Suggested shape (illustrative):

```toml
[fleet]
primary_id = "wsl-home"          # optional human label
default_interval = "1h"
light_probe = true
# Ship-back never runs from the hourly job unless explicitly enabled AND approved.
ship_back = false

[[hosts]]
id = "msi-windows"
ssh = "avis-msi"                 # Host alias from ~/.ssh/config
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
- `id` becomes part of staging path and origin labeling, e.g.
  `archive/fleet-msi-windows-claude/` or staging under `raw/fleet/<id>/…`
  then export with a dedicated source name. `[design]` exact naming in P2.

### 4.3 CLI surface (proposed)

```text
agent-archive fleet discover [--ssh-config PATH] [--write fleet-candidates.md]
agent-archive fleet status
agent-archive fleet collect [--host ID]... [--light|--full] [--dry-run]
agent-archive fleet approve-ship [--host ID]...   # records approval token/time
agent-archive fleet ship [--host ID]... [--dry-run]  # requires prior approval
```

| Command | Behavior |
| --- | --- |
| `discover` | Read `~/.ssh/config` Host entries (and optional recent `known_hosts`); probe `ssh -G` / `BatchMode` connectivity; **do not** collect. Write a report of candidates + suggested `fleet.toml` snippets. |
| `status` | For each enabled host: last probe time, last successful collect, lag, error. |
| `collect --light` | **Default for hourly job.** Per host: run remote fingerprint (file count + max mtime + optional sample digests). If unchanged vs local ledger → skip. If changed → pull deltas only. Then run local export for staged files. |
| `collect --full` | Force full inventory + pull (manual recovery). |
| `approve-ship` | User explicitly allows ship-back for host(s) until revoked or TTL expires. |
| `ship` | Push finalized **catalog** and/or selected Markdown packs to remote staging dirs; never default on hourly timer. |

Entry points also available as `python tools/agent_archive.py fleet …`.

### 4.4 Collect pipeline (primary)

1. **Load** `fleet.toml` allowlist.
2. **Connect** with `ssh -o BatchMode=yes -o ConnectTimeout=…` (fail soft per host).
3. **Light probe** (default): remote script returns JSON
   `{ root, file_count, max_mtime, size_sum, top_n_hashes? }`.
4. **Compare** to `baseline/`-style or `archive/.fleet/ledger.jsonl` last probe
   (gitignored operational state under `archive/.fleet/` or `raw/fleet/`).
5. **Delta list**: remote `find`/`Get-ChildItem` for files newer than last
   watermark or with new digests.
6. **Transfer** into staging:
   - Preferred: `rsync -az --files-from=…` or `scp` into
     `raw/fleet/<host_id>/<kind>/…` (gitignored `raw/`).
7. **Export**: temporary or permanent `Source` entries pointing at staged roots
   with names like `fleet-<host_id>-claude`, kind mapped from config.
8. **Merge** into `archive/index.jsonl` via existing merge identity
   (`session_id` + `sha256`) so SSH-pulled and local-visible copies of the same
   session collapse.
9. **Ledger**: write probe + collect outcome for status and next light run.

### 4.5 Ship-back (approval-gated)

After primary has indexed, the user may want remotes to hold a **read-only mirror**
of catalog or a subset of Markdown for offline use.

| Artifact | Default ship? | Notes |
| --- | --- | --- |
| `archive/index.jsonl` + `INDEX.md` | Optional | Useful; still may contain portable paths — user accepts |
| Full `archive/**/*.md` | Optional, heavy | Prefer on-demand or selected sources |
| `raw/` | **Never** auto | Secrets risk |
| `sources.toml` / `fleet.toml` | **Never** | Machine-local |

Approval model `[design]`:

```bash
agent-archive fleet approve-ship --host lab-ubuntu --ttl 24h
agent-archive fleet ship --host lab-ubuntu --what catalog
```

Hourly timer **never** calls `ship` unless `fleet.ship_back = true` **and** a
non-expired approval exists for that host.

Remote destination: `~/agent-sessions-mirror/` or path in `fleet.toml`
(`ship_path`). Primary uses `rsync` push. Remotes do not need a full product
install to receive a mirror.

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

- Lock file (no concurrent collect)
- Per-host timeout budget so one dead host cannot block the hour
- Append logs under `~/.local/share/agent-sessions/logs/`
- Exit 0 on partial success with non-zero only for hard config errors (so cron
  is not noisy) — exact policy in P3

### 4.7 Host discovery heuristics

`fleet discover` may suggest hosts from:

1. `~/.ssh/config` `Host` entries with `HostName` (skip wildcards `*`)
2. Optional: hosts the user SSH’d to recently (`~/.ssh/known_hosts` names only)
3. Optional: `ProxyJump` graphs (list only; do not auto-enable)

Every suggestion is **disabled until copied into `fleet.toml` with roots**.
Connectivity probe: `ssh -o BatchMode=yes host 'echo ok'`.

Windows OpenSSH remotes: document path conventions; probe via `powershell -NoProfile -Command …` when `os = "windows"`.

### 4.8 Origin and identity

- Staged files keep remote absolute path in metadata before portable rewrite.
- `source_origin` should encode fleet host id without username when possible,
  e.g. `fleet-host:msi-windows` (extend `portable_origin` or set explicitly on
  fleet sources). `[design]` implementation detail in P2.
- Dedup with sessions already imported via `/mnt/c` uses existing sha/session_id
  merge — expected and desirable.

### 4.9 Security & privacy

| Risk | Mitigation |
| --- | --- |
| Collect from unintended Host | Allowlist-only collect (D5) |
| Credential leakage in logs | Log host ids, not full ssh -v; no passwords |
| Secrets in pulled raw JSONL | Stay under `raw/` (gitignored); export already subject to PII tooling on tracked catalog |
| Remote write accidents | Ship-back off by default; approval + TTL |
| Public remote push | Fleet jobs never git push |
| Supply-chain on remote scripts | Prefer inline quoted remote commands or a pinned small probe script checksummed in-repo |

## 5. Threat model / risk table

| ID | Risk | Likelihood | Impact | Handling |
| --- | --- | --- | --- | --- |
| T1 | Hourly SSH load / battery | Med | Low | Light probe; skip if unchanged; ConnectTimeout |
| T2 | Partial pull corrupts staging | Low | Med | Atomic staging dirs + watermark only advanced on success |
| T3 | Same session dual-home diverges | Med | Low | Merge by content hash; document “latest digest wins” |
| T4 | User enables ship_back globally | Low | High | Require per-host approval; refuse if TTL expired |
| T5 | Windows path / permission failures | Med | Med | Host `os` profile + clear status errors |

## 6. Honest limits — what this does NOT do

- Does not replace vendor cloud sync for agent products
- Does not guarantee capture of **in-progress** live sessions mid-write (watermark
  may pick them up next hour)
- Does not auto-configure SSH keys or Tailscale
- Does not run on remotes without SSH access
- Does not claim macOS probe parity until validated (same stance as hub overall)
- Does not by itself create a multi-primary HA setup

## 7. Deliverables & progress tracker   ⟵ **source of truth**

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated. **One small PR per row.**

| ID | Deliverable | Depends on | Gated? | Status | PR |
|----|-------------|-----------|--------|--------|----|
| P0 | This design doc + docs index / MULTI_MACHINE pointer | — | No | ☑ | this PR |
| P1 | `fleet.example.toml` + gitignore `fleet.toml` + empty CLI stub `fleet --help` with subcommands listed as “not implemented” **or** hidden behind experimental flag | P0 | No | ☐ | — |
| P2 | Staging layout + `fleet collect` for **one** Linux host (manual, no scheduler): probe, rsync delta, export, ledger | P1 | No | ☐ | — |
| P3 | Light vs full collect; per-host timeouts; `fleet status` | P2 | No | ☐ | — |
| P4 | `fleet discover` (ssh config → candidates report + suggested TOML) | P1 | No | ☐ | — |
| P5 | Windows OpenSSH host profile (probe + pull paths) | P2 | No | ☐ | — |
| P6 | Hourly installer `install-fleet-collect-schedule.sh` (+ ps1 if needed) + AUTOMATION.md section | P3 | No | ☐ | — |
| P7 | `approve-ship` + `ship` (catalog only) with TTL ledger | P3 | No | ☐ | — |
| P8 | Tests: probe parse, watermark, dry-run collect with fixture SSH stub | P2–P3 | No | ☐ | — |
| P9 | Docs polish: FAQ, GETTING_STARTED optional section, SESSION_HANDOFF pointer | P6 | No | ☐ | — |

### Suggested execution order for next sessions

1. Merge this docs PR after review.
2. Implement **P1 → P2 → P3** (end-to-end Linux path is the MVP).
3. Add **P6** hourly schedule once MVP is trustworthy.
4. **P4/P5** discovery + Windows as follow-ups.
5. **P7** ship-back last (highest foot-gun).

## 8. Open questions — owner / external

| # | Question | Default if unset |
|---|----------|------------------|
| Q1 | Stage under `raw/fleet/` only, or also mirror into normal source names? | `raw/fleet/` + synthetic source names at export |
| Q2 | Should light probe include content hashes for top-N newest files or only mtime/size? | mtime+size first; hashes if false positives |
| Q3 | Ship-back approval TTL default? | 24h |
| Q4 | systemd user timer vs cron for hourly? | cron for parity with local-export installer; document both |
| Q5 | Require `rsync` or support scp-only fallback? | rsync preferred; scp fallback for small deltas |
| Q6 | Include Android/Termux or only “real” SSH desktops? | desktops/VMs only in v1 |

## 9. Definition of done

- [ ] User can allowlist ≥1 SSH host in `fleet.toml` and run `fleet collect --light`
- [ ] Unchanged hosts produce near-no-op hourly runs (seconds, no full tree copy)
- [ ] New remote sessions appear in primary `archive/index.jsonl` with fleet origin
- [ ] Duplicate of a session already on primary collapses via existing merge rules
- [ ] Ship-back cannot run without prior `approve-ship` (tests lock this)
- [ ] Docs describe primary-host + fleet vs private-git multi-machine clearly
- [ ] No personal fleet config or raw pulls committed to public remotes

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

- `2026-08-05` — Initial DRAFT design for SSH fleet collect + hourly light probe + approval-gated ship-back.
