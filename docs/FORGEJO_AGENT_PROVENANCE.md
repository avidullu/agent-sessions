# Forgejo agent provenance

> **Status:** `IN PROGRESS` · **Owner:** Avi Dullu · **Created:** 2026-08-08 · **Last updated:** 2026-08-09
>
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived`
> **Tracking anchor:** §7 is the source of truth. This project extends the
> session archive with source-control metadata; it does not replace session
> extraction or the historical public-launch tracker.

## 0. TL;DR

`agent-archive provenance` keeps a local, rebuildable SQLite index of Forgejo
pull-request actors, commit identities/signatures, co-author trailers, reviews,
and comment actors. It maps exact bot accounts through the versioned
`forge-service` identity policy and lets archived-session or owner evidence be
appended for old PRs that were submitted as Avi. Unknown or conflicting history
stays visibly unknown/conflicted.

The database contains metadata only. API tokens, PR/comment bodies, commit
messages, signature payloads, file lists, prompts, and transcripts are never
stored.

## 1. Problem and goal

Before distinct Forgejo bot accounts existed, local agents inherited Avi's Git
and API identity. Forgejo can then answer who submitted or merged a PR, but not
which model/runtime prepared it. Guessing from prose would put human credibility
at risk and produce false operational history.

The goal is to answer, with evidence:

- who submitted, committed, reviewed/commented on, and merged a PR;
- which coding agent is attributable, at what confidence, and why;
- which PRs are attributed to a named agent; and
- whether the evidence is exact, declared-only, owner/session-attested,
  conflicting, or absent.

## 2. Decisions locked

| # | Decision | Source/date | Implication |
| --- | --- | --- | --- |
| P1 | Forgejo remains observation authority | D-045, 2026-08-08 | observed actors are never overwritten by an attribution |
| P2 | SQLite is local and rebuildable | owner, 2026-08-08 | the DB is gitignored, owner-only on POSIX and checked against broad NTFS ACL readers on Windows, and carries no source secret |
| P3 | Exact mappings come from versioned identity policy | D-045 | username/email aliases cannot be guessed from display names |
| P4 | Historical claims need evidence | D-045 | title/branch/writing style never promotes an unknown to a fact |
| P5 | Attestations append | design review, 2026-08-08 | a conflict is reported, not resolved by last-write-wins |

## 3. Data flow

```text
restricted read token → bounded Forgejo GETs → normalized metadata → local SQLite
versioned identity policy ────────────────────────────────────────┘
archived session ID / owner fact → append-only evidence reference ┘

SQLite → `who` explanation / JSON → human or coding agent
       → `list --agent` inventory
```

The synchronizer fetches PR details, commit records, reviews, and issue-comment
envelopes. It extracts a bounded co-author trailer before discarding the commit
message. It stores comment actor/timestamps, not comment text.

## 4. Commands

The default DB is
`~/.local/share/agent-sessions/forgejo-provenance.sqlite3`. Set
`AGENT_SESSIONS_FORGEJO_URL` or pass `--forgejo-url`.

The store creates its parent with owner-only POSIX permissions. On Windows it
removes inherited access from the store directory and database, then grants
full control only to the current user, SYSTEM, and Administrators before it
accepts the path. Token files are read-only inputs and are never rewritten;
they must already have the same private ACL (the agent-identity installer
creates them that way).

```console
# Exact selected PRs; safe while bootstrapping.
agent-archive provenance --forgejo-url https://forge.example.test sync \
  --token-file ~/.config/forgejo/agents/agent-provenance/host.token \
  --identity-policy /path/to/forge-service/fleet/agent-identities.v1.json \
  --repo Example/project --pr 889 --pr 890

# Human explanation or stable JSON.
agent-archive provenance --forgejo-url https://forge.example.test who \
  --repo Example/project --pr 892
agent-archive provenance --forgejo-url https://forge.example.test who \
  --repo Example/project --pr 892 --json

# Search attributable history.
agent-archive provenance --forgejo-url https://forge.example.test list \
  --agent codex --repo Example/project

# Append a proven historical link. Evidence is an identifier/reference, not
# transcript text.
agent-archive provenance --forgejo-url https://forge.example.test attest \
  --repo Example/project --pr 892 --agent claude \
  --source session-evidence --evidence-ref session:<exact-id> \
  --attested-by agent-sessions
```

Use `owner-attestation` only for a direct owner fact. Use `session-evidence`
only when the archived record identifies the repository/PR/branch/commit
strongly enough to reproduce the link.

## 5. Attribution precedence and honesty

1. Append-only owner/session evidence, if internally consistent.
2. Exact mapped Forgejo PR author. Mapped commit/signature actors that disagree
   with that author are a conflict; a mapped bot commit on a human-authored PR
   is reported only as `partial-forgejo-actor` participation, not primary
   authorship and not included by `list --agent`.
3. Exact mapped Git email, reported as unverified if the commit is unsigned.
4. Co-author trailers, displayed only as unverified declared co-authors.
5. Unknown.

Two attestations naming different agents yield `conflict`; the query does not
select the newest. A human PR with a Claude trailer remains observed as Avi and
unknown as primary agent until stronger evidence exists.

## 6. Threat model and limits

| Risk | Control | Honest limit |
| --- | --- | --- |
| Owner token leaks into DB/logs | descriptor-based no-follow read; token path only; owner-only POSIX mode or Windows ACL check; cross-origin and same-origin redirects both fail closed; no token serialization | process memory necessarily holds the token while syncing |
| Private text enters public repo | DB lives outside repo; `.sqlite3` and `.agent-sessions/` ignored; PII gate remains | a user can still explicitly copy local output elsewhere |
| Forged historical attribution | no style/title inference; evidence source and attester retained | owner attestations are factual assertions, not signatures in v1 |
| Co-author trailer treated as proof | stored separately and labelled unverified | a trailer is still useful discovery evidence |
| Stale API state | each PR carries `synced_at`; sync is idempotent | no webhook/daemon in AP0 |
| Corrupt/ambiguous DB | schema version, constraints, FK checks, bounded values | backup is rebuild-by-sync plus reapplying local attestations |
| Concurrent writers | SQLite transactions; DELETE journal | v1 is a single-user local CLI, not a multi-host server |
| Windows permission drift | native ACL hardening for the DB plus a fail-closed ACL probe for DB and token | the token installer remains responsible for creating a private token ACL |

The database leaf is created atomically as owner-only before SQLite opens it,
then checked against the still-open descriptor. Network payloads are fetched
outside SQLite write transactions; one fully validated PR is committed at a
time, so a later API failure preserves earlier completed PRs and reports the
actual committed count.

## 7. Deliverables and progress tracker

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated.

| ID | Deliverable | Depends on | Gated? | Status | PR |
| --- | --- | --- | --- | --- | --- |
| AP0 | SQLite schema, bounded Forgejo sync, identity-policy mapping, `who`/`list`/`attest` CLI, adversarial tests | forge-service FS-114 | No | ☑ | private Forgejo PR #158 |
| AP0.1 | Split provenance internals behind the stable facade; reject URL userinfo; remove orphan commit metadata | AP0 | No | ◐ | follow-up PR pending |
| AP1 | Link exact archived session IDs automatically when repo/ref/commit evidence agrees | AP0 | Yes—private-session fixtures | ☐ | — |
| AP2 | Read-only scheduled refresh on the primary archive host | AP0, SSH fleet collect decision | Yes—schedule/retention review | ☐ | — |
| AP3 | Portable redacted aggregate/export, if useful | AP0 | Yes—privacy review | ☐ | — |

AP0 shipped as one independently reviewable PR. AP0.1 is a hardening follow-up;
AP1–AP3 must not be stacked on it before review/merge.

## 8. Open questions

No owner decision blocks AP0.1. AP1 will need a reviewed definition of what
session evidence is sufficient for automatic linkage. AP2 must follow the
existing primary-host scheduling decision rather than creating a second writer.

## 9. Definition of done

- [x] AP0 PR is reviewed, all local gates and Forgejo CI are green, and it is
  merged by Avi.
- [ ] A live read-only sync of PRs 889–892 succeeds using the dedicated
  provenance account.
- [ ] `who` preserves Avi as the observed actor and shows any trailer only as
  declared evidence.
- [ ] A new bot-authored PR attributes exactly from its Forgejo actor and signed
  Git identity without an attestation.
- [ ] Attestation idempotence and conflict behavior are demonstrated red then
  green in tests.
- [ ] No token, body, comment, commit message, file path, prompt, or transcript
  is present in the SQLite schema or test artifact.
- [ ] AP1–AP3 are either completed or remain honest open rows; this project is
  not marked DONE while they are unfinished.

## 10. References

- `agent_sessions/provenance.py` (stable public facade)
- `agent_sessions/_provenance_common.py`
- `agent_sessions/_provenance_store.py`
- `agent_sessions/_provenance_forgejo.py`
- `agent_sessions/_provenance_format.py`
- `tests/test_provenance.py`
- forge-service `docs/AGENT_IDENTITY_AND_PROVENANCE.md`, D-045, and companion
  private Forgejo PR #56
- `docs/SSH_FLEET_COLLECT_PLAN.md`

### Changelog

- 2026-08-08 — AP0 entered implementation with a local-only schema, read-only
  Forgejo client, policy-seeded identifiers, evidence-preserving attribution,
  and CLI/query tests; review is open as PR #158 alongside forge-service PR #56.
- 2026-08-08 — Windows CI exposed that POSIX mode bits do not secure inherited
  NTFS access. AP0 now hardens the database directory/file with native ACLs and
  verifies token ACLs without mutating the token; the same path passed a live
  Surface Windows directory-and-file probe.
- 2026-08-09 — Addressed owner review #467: redirect-safe credentials,
  descriptor-based secret reads, private pre-SQLite database creation,
  network-outside-lock per-PR transactions, strict JSON integer identities,
  bounded pull pagination, policy-alias replacement, honest mixed-actor
  attribution, and clean expected CLI failures. Retained and explicitly called
  out the ASCII `local-export.ps1` lock text: native Windows PowerShell 5.1
  corrupts the prior em dash under the runner's script encoding, causing a
  parser failure before the export command runs.
- 2026-08-09 — AP0 merged as PR #158. AP0.1 began as a compatibility-preserving
  split of the 1,151-line implementation into focused storage, Forgejo sync,
  private-file, and formatting modules; it also rejects URL userinfo and
  removes commit/co-author rows left orphaned by force-push SHA churn.
