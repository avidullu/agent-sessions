# Agent Sessions 0.4.0rc1 reliability candidate

Status: IN PROGRESS. Owner: avidullu. Created: 2026-10-10 IST.
Lifecycle: DRAFT → IN PROGRESS → DONE → ARCHIVED.

## Scope and ownership

This candidate addresses the eleven synthetic reliability failures recorded in
Forgejo issue #179. Two isolated Codex worktrees split export/source integrity
and catalog/configuration correctness; the combined candidate is validated as
one artifact. The candidate is proposed for evaluation, not a stable release.

| Work package | Findings | Acceptance | State |
| --- | --- | --- | --- |
| Catalog/configuration | B03, B06, B07, B08, B09 | Damage-preserving write refusal, schema-aware health, strict booleans, alias-safe merges and selector failures | Complete |
| Export integrity | B01, B02, B04, B05, B10, B12 | Stable byte binding, serialized/atomic writes, collision-safe naming, explicit parse outcomes and read-only dry runs | Complete |
| Candidate artifact | BB9 | Green local and exact-head Linux/Windows CI, fresh wheel journey and prerelease artifacts | In progress |

## Changed behavior

- Export stages one stable source version, then hashes, parses and copies raw
  bytes from that same snapshot. Provider filename ancestry and original-path
  render metadata remain intact. Files which cannot settle after three attempts
  are deferred; usable sources still export and the CLI returns a partial result.
- Reuse verifies full source content, including same-size edits with restored
  mtimes. This adds source-read and temporary-disk work to export; no real-corpus
  throughput claim has been measured for this candidate. `status` retains a
  fast metadata/tail scan and labels its check mode; `status --verify` compares
  complete source hashes when an integrity comparison is required.
- CLI export, prune and PDF catalog mutations share one archive writer lock.
  Active/stale locks refuse overlap; do not remove a lock before checking its
  writer. Atomic file replacement preserves the old file if preparation fails.
  The catalog commits before its regenerable Markdown view; export repairs a
  view left outdated by an interrupted commit.
- Catalog inspection keeps usable rows and reports damage. Writers refuse
  malformed catalogs; existing bytes remain available for explicit recovery.
  This candidate does not ship an automatic corrupt-catalog repair command.
- Long hub artifact names retain identity/content suffixes under the version 2
  extension. Existing short-name outputs, Router version 1 ingestion, and
  `agent-sessions-backup-v1` remain readable. No bulk archive migration occurs.
- Parser damage, unsupported schemas and metadata-only inputs are explicit; partial exports return
  nonzero. Quoted boolean settings fail instead of silently enabling behavior.
  An all-unmatched selector fails before writes; mixed valid/invalid selectors
  warn and export valid matches. Catalog aliases persist alternate source paths;
  legacy missing counts/fingerprints remain readable and unknown counts stay unknown.

## Candidate validation and publication

Run `./scripts/local_ci.sh` before pushing. Preserve at least the 92% coverage
floor and inspect coverage against main's measured 93.89%. The candidate's
exact committed head must pass Forgejo Linux/Windows checks before publication.
Build both wheel and sdist, check distribution metadata, install the wheel in a
fresh workspace outside the checkout, and exercise version/init/export/status,
partial failures and a tiny synthetic backup/verify/restore roundtrip.

Publish `v0.4.0rc1` as a Forgejo prerelease with the wheel, source distribution,
release notes and artifact hashes bound to the validated commit. A publication
permission failure must be reported; do not switch to Avi's identity. GitHub
Actions remain disabled. The existing PyPI Trusted Publishing workflow rejects
prereleases, so this candidate is not a PyPI release.

To try the downloaded wheel:

```bash
python -m venv candidate-env
candidate-env/bin/python -m pip install /path/to/agent_session_hub-0.4.0rc1-py3-none-any.whl
candidate-env/bin/agent-archive --version
```

On Windows use `candidate-env\Scripts\python.exe` and
`candidate-env\Scripts\agent-archive.exe`. Keep an independent recovery copy
before evaluating the candidate against an existing archive. Return to the
previous installed wheel if candidate behavior fails; retain new artifacts and
catalogs for diagnosis rather than deleting them. Old readers can ignore the
additive fields, but their original integrity bugs remain.

## Acceptance and remaining work

- [ ] Eleven findings have meaningful synthetic regressions and green full gates.
- [ ] Exact candidate-head Linux/Windows CI and native PowerShell failure test pass.
- [ ] Fresh distribution installation, partial-outcome and backup recovery journey pass.
- [ ] Prerelease artifacts are published and downloaded bytes match the built distributions.

The scheduled collector, replication receiver, unattended pilot and tool-aware
Markdown export (B11) remain outside this reliability candidate. Follow the
existing [durable-retention project](DURABLE_SESSION_RESEARCH_PROJECT.md) for
DR2–DR5 rather than claiming those capabilities from this release. Automatic
external-memory promotion and paid training remain separate decisions.
Avi retains default-branch merge and stable-release authority.

Changelog: 2026-10-10 IST — reliability candidate implementation split and
publication contract recorded.


## Review follow-up after rc1 publication

The published rc1 artifacts remain bound to their original commit. Review found
that shallow source paths could inherit snapshot directory names as provider
identity, and known Codex web-search/tool envelopes could incorrectly mark an
otherwise complete transcript partial. The proposed follow-up uses the original
source path explicitly for extractor identity while reading captured bytes, and
recognizes known non-transcript Codex response items. Synthetic regressions cover
shallow paths, identity stability across edits, and successful CLI exports with
these tool events. Unknown payload shapes still report unsupported input.
Earlier content-hashed artifact versions remain retained by design. Old cached
parser results are re-extracted once via an additive extraction revision.

Changelog: 2026-10-10 IST — PR review identity and tool-envelope corrections
complete in the proposed source; revised artifact qualification remains pending.
