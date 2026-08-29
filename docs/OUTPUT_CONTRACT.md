# Agent Sessions — Output Contract (v1)

> **Status:** canonical. This document is the single source of truth for the
> on-disk format that the `agent-sessions` archive produces and consumes.
> Helper tools that feed the archive (e.g. the
> [`agent-session-router`](https://github.com/avidullu/agent-session-router)
> VS Code extension) **must** conform to this contract byte-for-byte.
>
> **`format_version: 1`**

## 1. Why this exists

`agent-sessions` is the **hub**: a Python CLI (`tools/agent_archive.py`) that
discovers agent session logs, extracts them, and renders local Markdown/PDF
archive artifacts plus a shared catalog.

Some agents can't be reached by the Python importers — VS Code extensions such
as Copilot Chat store sessions in `globalStorage`/`workspaceStorage` and are
listed as `inventory`-only sources (see `sources.example.toml`). **Feeder
tools** fill that gap: they extract those sessions and write archive artifacts
*in this exact format*, so the hub can index them with no re-extraction.

The contract has two producer paths, both landing in the same `archive/`:

| Producer | Writes | Indexed by |
| --- | --- | --- |
| `agent-sessions` (Python) | local `archive/**/*.md`/`.pdf` artifacts + generated `archive/index.jsonl` + `archive/INDEX.md` (ignored when untracked) | itself, on `export` |
| Feeder tool (e.g. router) | local `archive/**/*.md` artifacts + `archive/.router-index.jsonl` sidecar | merged into `index.jsonl` on the next `export` |

If a feeder's output diverges from this document, the archive silently
fragments (duplicate files, mismatched catalog rows). The conformance tests in
both repos exist to prevent that — see §8.

By default, generated catalog metadata, rendered transcript bodies, and PDFs
are local-only files on the user's machine. Existing tracked private catalogs
continue to be tracked; a new private archive opts in with `git add -f
archive/index.jsonl archive/INDEX.md`. Set `[archive] track_artifacts = true`
only for an explicit repo policy change that intentionally commits rendered
transcript artifacts.

## 2. Archive Markdown format

Produced by `agent_sessions/render.py::markdown_for_session`. Exact structure:

```
# {title}
                                  ← blank line
## Metadata
                                  ← blank line
- Source: `{source_name}`
- Kind: `{source_kind}`
- Source file: `{source_file}`
- SHA-256: `{sha256_hex}`
- Source modified: `{source_modified}`
- Imported at: `{imported_at}`
{extra metadata bullets}
                                  ← blank line
## Transcript
                                  ← blank line
### 1. {role}[ ({timestamp})]

{message text}

### 2. {role}[ ({timestamp})]

{message text}
```

### Rules (all significant for byte-equality)

1. **Title** — `"# " + " / ".join(parts)` where `parts` is
   `[source_name, session_id]` with empties dropped, and `session_id` falls back
   to the **source file stem** (`path.stem`) when `metadata.session_id` is absent
   — *not* a literal like `"unknown"`.
2. **Fixed metadata bullets**, in this order: `Source`, `Kind`, `Source file`,
   `SHA-256`, `Source modified`, `Imported at`. Every value is wrapped in
   backticks.
3. **`Source file`** is the **OS-native** path string (`str(Path)`) — backslashes
   on Windows, forward slashes on POSIX. Do **not** normalize separators here.
   (Only the *catalog* paths in §5 are POSIX-normalized.)
4. **Extra metadata bullets** — every remaining key in `sorted(metadata)` whose
   value is not `None` and not `""`, rendered as ``- {key}: `{value}` ``. This
   **includes** `session_id` (it appears both in the title and as a bullet). Do
   **not** exclude `session_id` or `source_file`.
5. **Timestamps** (`Source modified`, `Imported at`) use
   `datetime.isoformat(timespec="seconds")` in **UTC**, i.e. the
   `YYYY-MM-DDTHH:MM:SS+00:00` form (offset `+00:00`, **not** `Z`, no fractional
   seconds). `imported_at` is preserved across re-exports when the `.md` already
   exists (see `existing_imported_at`).
6. **Transcript headings** — `### {n}. {role}` (1-based `n`), `role` falling back
   to `"message"`. Append ` ({timestamp})` **only** when the message carries a
   timestamp. **No other suffix** — in particular, no `[tool: …]` decoration.
   The message *timestamp* string is emitted verbatim from the extractor (its
   format is the extractor's responsibility, not the renderer's).
7. **Message body** is `text.rstrip()`, followed by a blank line.
8. **Empty transcript** — when there are no messages, the single line
   `_No transcript messages were extracted from this file._` replaces the
   entries.
9. **Trailing newline** — the whole document is `"\n".join(lines).rstrip() +
   "\n"`: exactly one trailing `\n`, no trailing blank line. UTF-8, LF endings.

### Reference example

```markdown
# codex-windows / 019f2174-38b2-7d92-bff9-9b57ab7306e6

## Metadata

- Source: `codex-windows`
- Kind: `codex`
- Source file: `C:\Users\example-user\.codex\sessions\2026\07\02\rollout-…​.jsonl`
- SHA-256: `15390945c8c4d53627b652eeac6761f25f5f547d8f2e08951bdc5e387c235d1e`
- Source modified: `2026-07-02T06:11:32+00:00`
- Imported at: `2026-07-05T16:48:15+00:00`
- cli_version: `0.142.5`
- model_provider: `openai`
- session_id: `019f2174-38b2-7d92-bff9-9b57ab7306e6`

## Transcript

### 1. user (2026-07-02T06:11:32.663Z)

hello. Please analyze the repo…

### 2. assistant (2026-07-02T06:11:32.663Z)

I'll start by getting oriented…
```

## 3. Timestamp formats

| Field | Format | Source |
| --- | --- | --- |
| `Source modified` | `isoformat(timespec="seconds")` UTC → `…+00:00` | file mtime |
| `Imported at` | `isoformat(timespec="seconds")` UTC → `…+00:00` | render time / preserved |
| catalog `mtime` | float epoch seconds | `path.stat().st_mtime` |
| message timestamp | extractor-defined, emitted verbatim | the session log |

`now_utc()` (`agent_sessions/utils.py`) is the canonical clock:
`datetime.now(timezone.utc).isoformat(timespec="seconds")`.

## 4. `slugify` (canonical algorithm)

File names and stems are produced by `agent_sessions/utils.py::slugify`.
Feeders must reproduce it exactly:

```python
def slugify(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^\w.\- ]+", "-", value, flags=re.ASCII)  # non [word . - space] → "-"
    value = re.sub(r"\s+", "-", value.strip())                  # runs of whitespace → "-"
    value = value.strip(".-_")
    return (value[:max_len].strip(".-_") or "session").lower()  # truncate 90, lowercase
```

Notes: ASCII-only `\w` (`[A-Za-z0-9_]`); result is **lower-cased**; empty result
becomes `"session"`; `max_len` default **90**.

## 5. Archive path & filename layout

```
archive/{source_name}/{stem}.md
archive/{source_name}/{stem}.pdf        # optional
```

Rendered Markdown/PDF files at these paths are local artifacts by default. Their
repo-relative paths remain in the catalog so a machine that has the local files
can open them, but Git ignores the rendered bodies unless
`[archive] track_artifacts = true` is enabled.

The **stem** (`agent_sessions/archive.py::export_sources`) is:

```
stem = slugify(f"{yyyymmdd}-{session_id}-{source_file_stem}-{sha256[:12]}")
```

where:
- `yyyymmdd` = UTC date of the source file's mtime (`strftime("%Y%m%d")`),
- `session_id` = `metadata.session_id` or the source file stem,
- `source_file_stem` = `path.stem`,
- `sha256[:12]` = first 12 hex chars of the file digest.

Rationale: the date + digest make the stem stable across machines/timezones and
change only when content changes, so re-exports supersede rather than duplicate.

**Catalog paths** (`markdown`, `pdf`, `raw` in the index) are stored
**repo-relative** and **POSIX-normalized** (forward slashes), unlike the
`Source file` metadata line in §2.3.

## 6. Catalog: `index.jsonl` record schema

`archive/index.jsonl` — one JSON object per line, UTF-8, LF, written by
`write_indexes`. `INDEX.md` is a generated human view and is never authored by a
feeder.

| Key | Type | Notes |
| --- | --- | --- |
| `source` | string | source name, e.g. `copilot-vscode-windows` |
| `kind` | string | extractor kind, e.g. `copilot_chat` |
| `source_file` | string | native path to the source log; a feeder writes it absolute, and the hub rewrites any user home prefix to a portable `~` form (plus a username-free `source_origin`) when the record enters the generated catalog — a deliberately tracked private catalog never carries a real home directory |
| `sha256` | string | hex digest of the source file |
| `size` | integer | source file size in bytes |
| `mtime` | number | source mtime, float epoch seconds |
| `messages` | integer | number of extracted messages |
| `markdown` | string | **repo-relative POSIX** path to the `.md` |
| `metadata` | object | the session metadata; **must** carry `session_id` |
| `pdf` | string \| null | optional, repo-relative POSIX |
| `raw` | string \| null | optional, repo-relative POSIX |

### Merge identity

`merge_index_records` dedupes by `index_identity_key`:
`("session", metadata.session_id, sha256)` when a non-empty `session_id` exists,
else `("path", source, source_file)`. When two records point at the same source
and rendered Markdown path, the newer record supersedes the older one. This
keeps append-only/sibling sessions with the same agent session id distinct when
their payload hashes differ, while still allowing a re-export of the same source
file to update one catalog row.

## 7. Feeder contract: `archive/.router-index.jsonl`

A feeder does **not** write `index.jsonl` directly. Instead it writes, alongside
its rendered Markdown:

```
archive/.router-index.jsonl
```

one **§6-schema record per exported session**, then the hub merges them into
`index.jsonl` automatically on the next `export`
(`archive.py::read_router_index_records` → `merge_index_records`). The reader is
fault-tolerant: a missing file yields no records, and malformed lines are
skipped with a warning (never a crash).

A feeder therefore produces, per session:
1. `archive/{source_name}/{stem}.md` — §2 format, §5 naming. In the hub repo
   this rendered Markdown file is local-only by default.
2. one line appended to `archive/.router-index.jsonl` — §6 schema, with
   `markdown` set to the repo-relative POSIX path of (1).

Nothing else is required; the hub owns `index.jsonl`/`INDEX.md` generation.

## 8. Source naming registry

`source` names and `kind` values must align with the hub's configuration
(`config/default_sources.toml`, template in `sources.example.toml`) so catalog
rows and dedup behave. Current `kind` values a feeder may emit:

| `kind` | Meaning |
| --- | --- |
| `copilot_chat` | VS Code native chat (Copilot and LM-API providers such as Z.AI); `metadata.model_provider` supplies the canonical agent when present |
| `deepseek_request_dump` | DeepSeek V4 VS Code extension request dumps |

New feeder kinds should be added here and, where the hub also has a Python
importer, use the **same** `kind` string so both producers converge on one
catalog row.

## 9. Versioning & conformance

- **`format_version: 1`** describes everything above. A change that alters bytes
  in §2, the schema in §6/§7, or the naming in §4/§5 is a version bump; add
  `v2` golden fixtures next to the `v1` ones rather than editing `v1`.
- **Golden fixtures** live at `tests/fixtures/contract/v1/` (input `*.json` +
  expected `*.md` + expected `*.router-index.jsonl`). They are the shared source
  of truth.
- **Hub conformance** — `tests/test_output_contract.py` asserts `render.py`
  reproduces every golden `.md`. If `render.py` changes, this test fails first.
- **Feeder conformance** — the feeder repo vendors the same goldens and asserts
  its renderer + index writer reproduce them byte-for-byte. If the feeder drifts,
  its CI fails.

Together these guarantee neither side can move without the other noticing.
