# Durable sessions and owned-model research

> **Status:** IN PROGRESS — project authorized; documentation and first implementation slice in review preparation.
> **Owner:** avidullu · **Created:** 2026-10-03 · **Updated:** 2026-10-03
> This document owns this project's scope, delivery order, and acceptance criteria.
> Runtime deployment and research success are separate from merged source code.

## Decision and investment case

Preserve coding-agent conversations periodically on independent storage, then
test whether reviewed examples improve a privately runnable assistant. Invest
first in recoverability, which is useful even if fine-tuning produces no gain.
Expand training only after a controlled comparison demonstrates useful behavior.

The initial model objective is a private, read-only workflow copilot: reconcile
work already performed, distinguish claims from evidence, incorporate corrections,
and identify the next useful check. General autonomous coding, broad personal
assistant coverage, pretraining from scratch, and unattended retraining are later
research choices, not requirements of this project.

The owner requested the documentation PR and execution on 2026-10-03. This
authorizes development of the retention path and local research preparation.
It does not create a new paid-training envelope, authorize transcript submission
to a provider, or select a production model. Existing prototype permissions
remain scoped to the inputs and limits recorded in [the prototype plan](TINKER_PROTOTYPE_RUN.md).

## Starting point and reuse

| Component | Inspected capability | Work needed here |
| --- | --- | --- |
| Agent Sessions | Installed workspace setup, batch export, source identity, collection health, native scheduling | Durable snapshots, independent backup health, dependable periodic capture |
| Historical backup branch | Gzip/SHA-256 objects, append-only manifests, verification, new-directory restore, statistics | Port onto current main; preserve installed onboarding and existing configuration |
| Router | VS Code discovery and normalized archive feed | Record raw-store coverage separately from parsed-conversation coverage |
| Bheem | Versioned Agent Sessions routine inspect/apply adapter | Extend the adapter after the upstream retention contract is implemented |
| bheem-copy | Private-route file transfer | Transfer to staging, then verify and publish through the archive receiver |
| Session copilot | Candidate review, family grouping, dataset construction, golden cases, grading | Measure usable-example yield and complete a bounded reviewed dataset |
| sft-factory / ons-lab | Conversational SFT preparation and managed experiment contracts in companion work | Verify current integration revisions before any experiment |

The historical backup work is available at commits `ee1cd30` and `cdf8844` on
`feat/durable-session-archive-20260910`. [GitHub PR #138](https://github.com/avidullu/agent-sessions/pull/138)
is closed without merge as of this assessment. Reuse its implementation and
synthetic tests; do not treat that branch as released functionality.

Private storage inventory, actual corpus counts, machine paths, labels, and
experiment outputs stay outside Git. This public project document records
capabilities and acceptance criteria, not owner operational data.

## Architecture and boundaries

```text
native stores / Router
    -> local capture and versioned snapshots          Agent Sessions
    -> private transfer staging -> verified replica  archive receiver + bheem-copy
    -> independent second copy and restore proof     storage operator
    -> normalized, filtered, reviewed examples       session copilot
    -> frozen train / development / test datasets    session copilot
    -> token plan, SFT, exported adapter              sft-factory
    -> matched experiment and measured decision      ons-lab + client evaluator
```

Bheem configures the upstream routine and displays operational health. It does
not parse transcripts, assign training labels, or become a second archive owner.
Its shared CI closure store must not contain private logs. A successful copy is
transport evidence; the receiver's verified snapshot is the durability evidence.

Keep three layers distinct: retained original bytes, regenerable normalized
conversations, and explicitly admitted training examples. A backup is not a
training-use decision. Training examples retain private source-object and
event references, review provenance, conversation-family identity, and the
compiler revision. Tool results and verified outcome references are valuable;
PDFs alone are insufficient research inputs.

### Retention behavior and interfaces

1. Recover the existing `agent-archive backup init|run|verify|restore` and `stats`
   interface, including `[backup] directory`, `machine`, and `on_export` settings.
   Keep `agent-sessions-backup-v1` readable and make no destructive migration.
   Snapshot objects use original-byte SHA-256 identities and deterministic gzip.
2. Ordinary runs require an initialized destination outside the checkout and
   live sources. Missing storage refuses the operation. Publish a manifest only
   after its referenced objects are durable. Source deletion never propagates
   into retained snapshots. Restore always targets a new directory.
3. The first recovered slice remains manual and preserves existing fail-on-change
   behavior. Before scheduling it hourly, add isolated per-source capture:
   bounded retries for changing files, explicit exclusions for unsettled inputs,
   and publication of stable captures with a `partial` outcome. Never label that
   outcome complete. Unsupported live databases remain an explicit coverage gap;
   use a provider-supported consistent snapshot before claiming database coverage.
4. Add a separate versioned capture result, `agent-sessions.capture-result.v1`.
   Required information: run and machine identity, UTC start/finish, snapshot
   identity, `complete|partial|failed` outcome, included/deferred/failed counts,
   unavailable-source count, new stored bytes, and non-sensitive reason codes.
   Keep detailed paths in private manifests. Extend `status --json` additively
   with independent last-capture, last-replication, and last-restore timestamps;
   unknown timestamps stay unknown. Existing export health retains its meaning.
5. Target hourly local capture while awake, nightly replication at 02:30 in the
   host's configured timezone, and catch-up on the next invocation after downtime.
   Use one configured primary runtime for overlapping Windows/WSL sources.
   Preserve existing export schedules; retention is its own managed routine.
   A non-overlap lock prevents concurrent runs; an offline destination leaves
   snapshots queued without blocking local capture or deleting queued objects.
6. Replicate immutable objects before manifests into a private staging area.
   A single receiver verifies decoded object hashes/sizes, then atomically admits
   the snapshot. Retries are idempotent, source deletions are ignored, and
   conflicting manifests are refused. Restrict the writer to its archive path;
   use `bheem-copy --sensitivity private`, never destructive mirror mode.
7. Keep originals plus two backup copies on independent storage before calling
   retention durable against a storage-device loss. The second backup should
   have separate credentials or disconnected/off-site custody. Encrypt raw
   archives at rest using the storage layer, and test key recovery separately.
   No automatic pruning in v1; low capacity produces an actionable failure.

Hourly capture gives a target of one hour of loss for available, settled sources
while awake. Nightly independent replication gives a target of 24 hours for
machine loss while connected. Actual freshness and deferred inputs determine
the claim; sleeping machines and long-lived unsettled files extend these windows.

The existing implementation hashes complete sources on every run and stores a
new whole-file object when a growing log changes. Measure bytes read, newly stored
bytes, run duration, and exclusions during the pilot. Reuse unchanged content;
do not introduce chunk storage until measured growth or capture duration warrants
it. Stop frequency expansion if a run regularly exceeds half its interval.

### Research experiment

The hypothesis is that reviewed corrections and evidence-grounded examples improve
workflow decisions beyond a well-prompted assistant using the same retrieval.
Historical facts remain runtime evidence; fine-tuning targets behavior.

- Start with a stratified review of 50 candidates across the five concepts in
  [Session copilot](SESSION_COPILOT.md). Measure acceptance, correction time,
  unsupported targets, missing context, and usable examples per reviewer-hour.
  Check every retained category rather than selecting only easy examples.
- Admit only reviewed, training-permitted examples. Quarantine suspected secrets;
  exclude hidden reasoning and embedded internal instructions from model inputs.
  Unknown source-use eligibility is excluded from training, even if retention is
  permitted. Rejected answers are not positive SFT targets. Withdrawal excludes
  affected examples from subsequent dataset builds and marks dependent candidates
  for reassessment; deleting an example does not undo an already trained model.
- Deduplicate and group forks, copied prefixes, retries, and derived cases into
  whole families before splitting. Use a chronological cutoff and project holdout
  for the full experiment. Prompts must not contain outcomes learned after their
  simulated decision time. Reference answers remain local during evaluation.
- The first new comparison has two arms: an untuned assistant with a tuned prompt
  and retrieval, and the same model plus SFT with identical evidence and inference
  settings. Use the existing assistant-model integration first; pin its exact
  revision and renderer during preparation. Freeze prompt choices on development
  data. An ablation without retrieval is optional and receives its own budget.
- Reuse existing dataset admission profiles. The prototype requires at least
  96 training examples from 15 families, 20 development examples, and 40 grounded
  test examples from eight families, plus the evaluation-only golden suite.
  This is directional evidence. Do not weaken thresholds to accommodate attrition.
  A scaling decision uses the full profile: at least 500 training, 100 development,
  and 200 test examples, including held-out-project cases and family requirements
  already enforced by the compiler.
- Freeze blinded evaluation before training. Score task success, citation
  correctness, unsupported claims, changed-fact consistency, and secret disclosure;
  report conversation-family bootstrap intervals and per-concept regressions.
  Expansion requires at least 10 percentage points of task-success uplift,
  a positive lower bound on the 95% family-bootstrap interval for that uplift,
  at least 95% citation correctness, at most 5% unsupported claims, at least 80%
  paired counterfactual success, and zero observed secret disclosures. A small
  sample with wide uncertainty is inconclusive. It does not justify scaling.
- Evaluate unrelated retained tasks as a regression control. Repeated checkpoint
  or hyperparameter selection uses development data; once a test set guides a
  change, replace it with a fresh held-out evaluation for the next claim.
- Owned-model acceptance requires the dataset manifest, base-model revision and
  applicable license, tokenizer, renderer, adapter, training configuration, and
  evaluator to be retained. Demonstrate fresh local loading and inference outside
  the training provider. Model export is separate from deployment approval.

This two-arm research design is a new proposal for this project. It does not
silently replace or inherit spend from the earlier four-arm prototype.

## Delivery order and acceptance

| ID | Slice and owner | Depends on | Acceptance | State |
| --- | --- | --- | --- | --- |
| DR0 | Project document, hub | — | Scope, ownership, research stop rules, and source references are reviewable | In progress |
| DR1 | Recover durable backup and statistics, hub | Current main | Versioned restore works after source deletion; corruption/missing storage refuse; installed workspace still works | In progress |
| DR2 | Reliable bounded capture, hub | DR1 | One changing source cannot hide stable captures; partial coverage is explicit; result contract and failure-injection tests pass | Planned |
| DR3 | Retention scheduling, hub + Bheem adapter | DR2 | Hourly/nightly configuration, catch-up, no overlap, and idempotent inspection/apply on Linux/WSL and Windows | Planned |
| DR4 | Verified private replication, hub + Bheem Copy | DR2 | Interrupted transfer resumes; manifest-before-object and corrupt-object publication refuse; source deletion cannot delete replicas | Planned |
| DR5 | Operational pilot and second copy | DR3, DR4 | Seven days of observed freshness, explicit exclusions, independent-copy restore, and measured duration/growth | Planned |
| DR6 | Review-yield study, session copilot | Available retained corpus | 50 reviewed candidates with measured effort and a decision to continue, simplify, or stop | Planned; may run alongside DR1–DR5 |
| DR7 | Frozen pilot dataset and dry preparation, hub + SFT/ONS | DR6 | Existing admission thresholds, exact token plan, leakage checks, and matched work orders pass locally | Conditional on usable-data yield |
| DR8 | Bounded training comparison and portability proof | DR7 | Exact data/model/provider and total spend approved; blinded results and independent inference recorded | Requires experiment approval |

Each slice is a small reviewable change. DR1 is based on current main and can be
prepared independently of the docs PR; it does not imply DR2–DR5 are implemented.
Use this table rather than creating another dashboard or parallel tracker.

### Verification

Use synthetic fixtures for source deletion, same-path updates, duplicate objects,
gzip recovery, corrupt/missing objects, destination overlap/unavailability,
interrupted writes, concurrent writers, changing inputs, and restore without the
original checkout. Add installed-wheel onboarding and configuration compatibility
coverage when porting the historical branch.

Scheduling and replication add fake-clock/catch-up, offline destination,
receiver crash, idempotent retry, and truthful partial-result tests. Native
Windows execution is a separate acceptance check from Linux unit tests. Private
operational verification restores a bounded sample into a new directory; do not
copy private corpus data into CI or run unrelated media checksums.

Research tests cover family overlap, future-evidence leakage, withdrawn and
unreviewed data, secret quarantine, token/loss-mask correctness, dataset identity,
blinded grading, and provider-free inference from exported artifacts. A repository
test pass is not a demonstrated model improvement.

## Cost, continuation, and stop rules

Planning allowances, not measured delivery promises: 3–5 focused engineering days
for initial backup recovery and integration exploration; allow further slices
only after measuring operational behavior. Cap the initial review-yield study at
four reviewer-hours. If it cannot produce a useful sample within that allowance,
improve candidate selection or reduce the research objective before labeling more.

The first paid experiment needs a separately recorded all-in ceiling covering
training, evaluation, checkpoint storage, export, and possible recovery. No
automatic retry or automatic budget renewal. Refresh provider pricing and use
exact rendered tokens at preparation time. Hardware purchase is unnecessary to
decide whether this dataset is worth training on.

For scale context, reviewing 160 examples at 2–5 minutes each costs about 5–13
reviewer-hours before evaluation. This is an illustrative effort model, not
measured throughput. Evaluate return using net time saved after operation and
review costs: 40 hours invested and two hours saved per week would break even in
20 weeks. Research value may justify a bounded negative result, but does not
justify indefinite expansion.

Continue retention if restore and freshness remain useful even when SFT loses.
Stop training expansion if useful labels are too costly, the retrieval baseline
performs as well, improvement disappears on held-out projects or changed facts,
privacy regressions appear, or independent inference cannot be demonstrated.

The project is complete when DR1–DR5 provide proven periodic recovery and DR6–DR8
produce either a supported model-improvement result or an explicit evidence-based
stop decision. Research rejection is a valid outcome; unrun experiments remain
unrun. Merges, releases, paid runs, and production model selection remain the
owner's decisions.

## Research basis and related work

- [LIMA](https://arxiv.org/abs/2305.11206): evidence that carefully curated examples
  can adapt a strong pretrained model; not proof that raw logs train a capable agent.
- [SWE-smith](https://arxiv.org/abs/2504.21798): executable environments and
  objectively testable tasks matter when the objective is software engineering.
- [RAG versus fine-tuning](https://arxiv.org/abs/2403.01432): motivates a retrieval
  baseline for historical facts; its QA findings do not settle workflow behavior.
- [Training-data deduplication](https://arxiv.org/abs/2107.06499): supports family
  grouping and overlap controls; archive-object deduplication alone is insufficient.
- [Tinker pricing](https://tinker-docs.thinkingmachines.ai/tinker/models/models_and_pricing/)
  and [checkpoint export](https://tinker-docs.thinkingmachines.ai/tinker/howto/checkpoints/):
  recheck for the exact model at experiment preparation; export support does not
  establish local runtime compatibility.

This project extends [product direction](PRODUCT_DIRECTION.md),
[automation](AUTOMATION.md), and [Session copilot](SESSION_COPILOT.md).
It is a bounded implementation path alongside the broader
[collector/session-intel design](designs/SESSION_COLLECTOR_AND_INTEL.md) and
[SSH collection plan](SSH_FLEET_COLLECT_PLAN.md); it does not require their full
fleet or synthesis scope. Existing archive output identities remain unchanged.
The [xdsync boundary](XDSYNC_BOUNDARY.md) remains: archived observations do not
silently rewrite instructions or durable memory.
