# Durable session backups and statistics

An independent backup preserves logs when an agent is uninstalled, its history
is cleared, or the working checkout is deleted. Each run retains the previous
versions. Source deletion never deletes a backup object or snapshot.

## Choose a destination

Use a dedicated directory on an external disk or a mounted network share,
outside your checkout and agent stores. Mount the disk first, then initialize
an empty directory explicitly:

```sh
agent-archive backup init --destination /mnt/backup-disk/session-archive
```

On Windows, a destination such as `E:/session-archive` works as well. The parent
must already exist. Ordinary backup runs require the initialized destination;
they fail instead of silently recreating a directory on an absent drive.

New stores use **gzip** (level 6), suitable for text logs. For already compressed
inputs or storage that handles compression itself, use:

```sh
agent-archive backup init --destination /mnt/backup-disk/session-archive-plain --compression none
```

Compression is fixed per store in `backup.json`. Both formats use SHA-256 of the
**original bytes** as the object identity. Identical bytes share an object;
changed files get a new object. Existing `.gz` raw backups are preserved exactly,
including their original compressed bytes. They may gain little from another
compression layer. Compression saves space; it does not encrypt the archive.

## Configure regular exports

Add this to your ignored `sources.toml`:

```toml
[backup]
directory = "/mnt/backup-disk/session-archive"
machine = "workstation-linux"
on_export = true
```

With `on_export = true`, `export --all` checks that the backup is available
before exporting, then creates a backup after a successful export. A backup
failure makes the command fail; the local export may already have completed.
The backup covers **all configured source files and existing archive/raw files**,
even if the export itself used a source selector or limit. Inventory sources
are included without requiring an extractor. `--dry-run` does not back up.

To back up pre-existing data without re-exporting:

```sh
agent-archive backup run
# Override the configured directory for one run:
agent-archive backup run --destination /mnt/backup-disk/another-initialized-store
```

The run includes available configured source files, historical rendered
Markdown/PDF files, catalogs, and raw backups. It reports unavailable source
roots. Catalog-only entries whose originals and artifacts are already gone
cannot be reconstructed. Statistics distinguish those gaps from preserved logs.

Backup is a snapshot at command execution, not a watcher. Use the existing
export scheduling facilities if periodic capture is wanted. Logs created and
deleted between runs cannot be protected. Changing files are copied and checked
for stable size, modification time and inode, with three attempts; persistent
changes fail the run so it can be retried. This is not an application-wide
transaction across all active logs.

## Remote disk over SSH

The tool takes filesystem paths, not SSH URLs. Either mount remote storage or
run the tool on the machine that owns the disk. For example, copy a local
archive and raw logs into a private staging directory on the remote host,
without any deletion flags:

```sh
rsync -az archive/ backup-host:/mnt/backup-disk/import/workstation/archive/
rsync -az raw/ backup-host:/mnt/backup-disk/import/workstation/raw/
ssh backup-host 'agent-archive --repo-root /mnt/backup-disk/import/workstation backup run --destination /mnt/backup-disk/session-archive --machine workstation'
```

The staging repository needs a `sources.toml` (an `[archive]` section is sufficient
when importing only existing `archive/` and `raw/`). Add source entries for any
live logs to collect. Run a separate backup against the remote machine's own
configured repository to accumulate its logs in the same store. Machine labels
identify producers; use consistent labels on repeated runs. The archive has one
writer at a time. Never use a mirroring command with deletion against the backup
store itself.

## Verify and recover

```sh
agent-archive backup verify --destination /mnt/backup-disk/session-archive
agent-archive backup restore --destination /mnt/backup-disk/session-archive \
  --snapshot 20260101T120000-example.json --output /tmp/restored-session-logs
```

Use an actual filename from `snapshots/`. Verification checks every referenced
object, decompresses gzip, checks its full SHA-256 and original size, and exits
nonzero on corruption or missing data. Restore requires a **new** output
directory; it never overwrites live agent stores. `restore-map.json` maps
numbered restored files back to their original paths. If recovery fails, the
partial output remains for inspection; retry into another new directory.

Recovery with an explicit destination works without the original checkout or
source configuration. The format is also readable with standard JSON and gzip
tools; `RECOVERY.txt` in each store explains it. Snapshot manifests contain
private paths, and objects can contain secrets from logs. Protect access to the
entire directory. New directories use owner-only permissions where supported;
Windows/network-share ACLs are managed by the filesystem owner.

Objects are verified before a snapshot is atomically published. A failed run
can leave unreferenced objects, but does not replace or delete older snapshots.
Statistics count these separately. An interrupted process may leave
`.write.lock`; only remove it after confirming its recorded host/process is no
longer writing. No automatic retention, pruning, or deletion is implemented.

This protects against cleanup of **source locations**, not deletion of the
backup itself, administrator actions, ransomware, filesystem failure, or loss
of the disk. Use a second independent copy for those risks.

## Publish a local statistics report

```sh
agent-archive stats
agent-archive stats --json --output /tmp/archive-statistics.json
agent-archive stats --destination /mnt/backup-disk/session-archive \
  --output /tmp/archive-statistics.md
```

Reports are local; no metrics or transcripts are uploaded. Output includes:

- Catalog records versus distinct `(agent, session ID)` pairs, missing IDs,
  and message counts. Subagent files and retained versions can share an ID;
  messages summed across records are not a deduplicated conversation count.
- Known source bytes, missing size metadata, nearest-rank p50/p90/p99/max sizes,
  and record distributions by agent, source, and source modification month UTC.
  Modification month is not claimed to be the conversation creation date.
- Local Markdown availability and size.
- Backup snapshots, distinct file paths, file versions, unique objects,
  logical file-version bytes, referenced stored bytes, and object-directory
  bytes including unreferenced files. Byte counts are file lengths, not disk
  allocation or filesystem compression measurements; manifests are separate.
- Deduplication savings (`1 - unique original bytes / logical version bytes`)
  separately from compression savings (`1 - stored bytes / unique original bytes`).
- Catalog history across backed-up catalogs, deduplicated by agent/session ID
  and content digest (falling back to source/path/digest), and raw/rendered
  recovery coverage. All retained catalog versions contribute to this history.

For legacy raw gzip copies, reports hash the decoded original bytes to match
catalog entries even when their raw-file links are absent. This can require
reading/decompressing old backups. Undecodable raw gzip files are counted.

Statistics are not a full integrity check; run `backup verify` for
that. A report can include private source labels and dates: review it before
sharing publicly. The checked-in documentation and tests use synthetic data.
