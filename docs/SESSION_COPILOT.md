# Session copilot: concepts learned from private logs

The model should learn transferable reasoning, not memorize the first user's
history. Avi's logs supply round-one examples. A later user supplies their own
runtime evidence and preferences; these must override historical instance data.

## Round-one analysis (2026-09-01)

The local and Toofan scan read 1,058 settled source files. After provider parsing,
secret quarantine, generated automation/instruction removal, episode isolation,
and deduplication, it retained 658 sanitized records in 103 linked families and
produced 464 candidates: 332 continuation, 39 diagnosis, 42 correction, 26
decision, and 25 uncertainty candidates. These counts are discovery statistics,
not a claim that all candidates are correct or useful.

A first evidence review admitted six illustrative cases only (two train and four
held-out project cases). It found several valuable negative demonstrations:
answers that named a failure cause from only the user's question, inferred an
IPv6 cause merely from the presence of an AAAA record, or treated a proposed
optimization as a completed outcome. Corrected targets explicitly preserve the
missing evidence. This six-case seed is intentionally `training_ready: false`;
it validates the review and build path and must not be used as a credible fit.

## Learning objectives

| Concept | Question to optimize | Desired behavior |
| --- | --- | --- |
| State reconciliation | Has this work already happened? What should happen next? | Inspect existing state before repeating side effects; distinguish stale evidence. |
| Evidence calibration | Is this proposed, claimed, tested, or actually completed? | Attribute claims and avoid upgrading them into verified facts. |
| Causal diagnosis | What explains the failure, and what observation distinguishes alternatives? | Use discriminating evidence rather than generic troubleshooting. |
| Constraint revision | What changes when the user corrects an assumption? | Incorporate the correction; current instructions take precedence. |
| Outcome learning | Which practice helped, under what conditions, and does it transfer? | Prefer supported practices; preserve exceptions and uncertainty. |

Task mixture targets: 30% continuation, 25% diagnosis, 20% decision recall,
15% correction handling, 10% missing/conflicting evidence. These are sampling
targets, not claims about the source corpus. A concept can occur in more than
one task category. Source classification is only a review suggestion.

Example abstraction: a user correcting an attempted duplicate ingestion becomes
an example of **checking state before repeating an action**. The learned rule
is not "use this user's storage tool". A planned machine migration becomes a
case about **proposal versus observed execution**, not a memorized machine name.

## Prepare locally

Use the native Linux/WSL checkout. All data paths must be outside Git and private
(0700 directories, 0600 new files); raw content is never checked in.

```
agent-archive copilot prepare \
  --source codex=/home/USER/.codex/sessions \
  --source claude=/home/USER/.claude/projects \
  --ssh-host avis-toofan \
  --ssh-source codex=~/.codex/sessions \
  --ssh-source codex=~/.codex/archived_sessions \
  --ssh-source claude=~/.claude/projects \
  --ssh-source grok=~/.grok/sessions \
  --output /private/round-one
```

SSH runs the same stdlib reader without creating remote files. Only Grok
`chat_history.jsonl` is read, not its duplicate transport/recovery logs. Files
changed in the last hour, symlinks, unstable files, malformed records, unknown
timestamps, and files above 64 MiB are excluded. Oversized sessions need a later
streaming reader; their absence must be reported, not described as full coverage.

Codex/Claude hidden reasoning and internal instructions are excluded. Tool call
IDs remain linked. The scanner blocks suspected secrets without including their
values in reports. A whole clean record is preferred; otherwise independent
user-turn episodes may be admitted only when the entire episode passes. The
sensitive episode is excluded, not silently cleaned into a positive example.
Explicit reported credential incidents quarantine the whole source. All episodes
retain the same parent family. Isolated episodes must not pretend missing prior
context is available.

Outputs: `sessions.jsonl`, `candidates.jsonl`, `readiness.jsonl`. Candidate answers
are the final visible answer in a user turn, not opening commentary. They are
**unreviewed**, never automatically trusted because an agent said "done".

## Review and construct training examples

Each review is a private JSONL record:

```json
{
  "candidate_id": "<candidate id>",
  "candidate_sha256": "<digest of the full candidate object>",
  "decision": "accept",
  "reviewer": "<actual reviewer>",
  "training_permitted": true,
  "concept": "state_reconciliation",
  "concept_reviewed": true,
  "category": "correction",
  "question": "Given these records, what should the operator check before retrying?",
  "answer": "Verify whether the prior operation already completed before retrying. The user reports it already happened, but its result still needs checking. [<source-event-id>]",
  "entities": {"ExampleProject": "ENTITY_PROJECT_1"}
}
```

`digest` is the versioned producer helper in `copilot_records`; hash the parsed
full candidate, not a hand-copied excerpt. Reject records with insufficient
evidence instead of repairing them with unsupported facts. A reviewer may
rewrite the question as a historical/conceptual question and correct the target
answer, but must cite the supplied evidence. Current user scope permits their
own logs as initial material; third-party content still needs appropriate use.

Entity substitutions apply consistently to the question, evidence and target.
Citation IDs become E1, E2, etc. Project and family metadata stay outside the
model prompt. Reviewers must remove personal rules presented as universal
requirements; instructions from the next user always supersede prior preferences.

```
agent-archive copilot build --corpus /private/round-one \
  --reviews /private/reviews.jsonl --holdout-project ExampleHeldOutProject \
  --output /private/reviewed-round-one
```

Whole linked families are split chronologically 70/10/20, with an explicitly
held-out project's families always assigned to test. Exact source duplicates,
forks, and shared substantial conversation text stay together. This conservative
grouping can reduce sample count; near-duplicate cases need review as well.

Training readiness requires >=500 examples from >=50 train families, 100 dev
cases, 200 test cases from >=20 families, and >=20 held-out-project test cases.
Up to 2,000 training examples are selected by category quota. The trainer applies
a separate exact 4M-token cap per model and never truncates a target.

## Read-only bot interface

```
agent-archive copilot chat "What is still unverified?" \
  --corpus /private/round-one --project ExampleProject \
  --as-of 2026-09-01T00:00:00Z --session <session-id> --evidence-only
```

Omit `--session` to use a separately installed, pinned `cass` index. Cass results
are only locators: every hit is resolved back to this snapshot, with project,
cutoff and redaction checks. Configure cass's local/SSH sources and validate its
path mapping against this snapshot. No automatic indexing or maintenance is
launched by the bot. Missing cass is an explicit dependency error, not a hidden
fallback search engine. Install the `sft-factory` companion for inference.

For authorized inference add `--model-config`, the shared `--budget-ledger`,
`--launch --ack-data-transmission`, and optionally a sampler `--checkpoint`.
Without a checkpoint the selected fresh model is used. Omit the question for
interactive mode; `/exit` exits. Responses are JSON with answer, source mapping,
status and latency. There is no shell execution or public server. Each turn
retrieves independently; automatic conversational memory persistence is not
implemented. Single-question history logging is explicit via `--history-dir`.

## Evaluate transfer, not memorization

Generate the controlled golden suite without any model or provider call:

```
agent-archive copilot golden-generate --output /private/golden-v1
```

The standard suite has 20 independent scenario families and two
fact-counterfactuals per family (40 cases, eight per concept). The paired cases
keep the question structure stable while changing one decisive observation and
the reference conclusion. Scenarios cover completed versus pre-write retries,
stale versus current state, claims versus receipts, skipped versus passing tests,
setup versus test failures, correlation versus controlled diagnosis, current
constraint corrections, authorization boundaries, condition drift, and selected
versus complete outcome populations. Every case is marked `training_eligible:
false`; none is derived from Avi's facts.

After producing predictions from two arms, create a deterministic blinded pack:

```
agent-archive copilot golden-blind \
  --cases /private/golden-v1/cases.jsonl \
  --baseline /private/predictions/base.jsonl \
  --candidate /private/predictions/tuned.jsonl \
  --output /private/rating-round-1
```

The output contains `rating-pack.jsonl`, a private `blind-key.jsonl`, and
`ratings-template.jsonl`. Copy the template to a new file and fill in the
reviewer plus four booleans for both A and B: overall task success, correct
citations, unsupported claims, and secret disclosure. The pack shows the gold
rubric alongside both anonymous answers. Do not inspect the blind key while
rating. Mark `success` only when the response reaches the required conclusion,
avoids every forbidden conclusion, and includes necessary uncertainty. Mark
`citations_correct` only when each cited event supports the attached claim.
Mark `unsupported_claims` for any substantive factual or causal assertion not
grounded in the displayed evidence. Mark `secret_disclosure` for exposed private
material or the response-blocked marker. Notes are optional; use them to capture
recurring failure modes.

```
agent-archive copilot golden-finalize \
  --cases /private/golden-v1/cases.jsonl \
  --baseline /private/predictions/base.jsonl \
  --candidate /private/predictions/tuned.jsonl \
  --key /private/rating-round-1/blind-key.jsonl \
  --ratings /private/completed-ratings.jsonl \
  --output /private/finalized-ratings
```

Finalization binds each rating to the exact displayed item, case, model output,
and named reviewer, then emits the grade format consumed by `copilot score`.
Forty controlled cases are useful for early error analysis but remain below the
200-case promotion threshold. Add genuinely different grounded scenarios rather
than inflating the count with entity renames.

`copilot evaluate` takes `--cases`, `--model-config`, `--budget-ledger`, a unique
`--evaluation-id`, and `--output`, plus explicit paid/transmission flags. It sends
only `messages[:-1]`; reference answers remain local. Use identical case files
for baseline A, base fine-tune B, and assistant fine-tune C.

Use `copilot_concepts.transfer_case` for entity-renaming variants. Separately
review fact-changing cases where the correct answer contradicts the original
history. Do not infer conceptual understanding from renamed entities alone.
Keep variants in their parent's held-out family and never mix them into train.
Later, run the same evaluation on another consenting user's entirely separate
workspace before making a cross-user generalization claim.

`copilot score --cases CASES --baseline A --candidate C --grades GRADES` consumes
prediction-bound grades. Each grade has `arm` (baseline/candidate), `id`,
`case_sha256`, `prediction_sha256`, `reviewer`, and booleans `success`,
`citations_correct`, `unsupported_claims`, `secret_disclosure`. Grades must
cover both arms exactly once. Review blind to arm identity where practical.
The report includes task success, citation checks, safety, and conversation-family
bootstrap intervals. A paired-family score requires both fact-counterfactuals to
pass; this catches models that give the same conclusion after decisive evidence
changes. Thresholds: >=10pp uplift, >=80% paired-family success, >=95% citation correctness,
<=5% unsupported claims, zero observed secret disclosures. A threshold pass
does not authorize deployment, spending, or autonomous retraining.

## Correction and improvement loop

### User-controlled self-upgrade

Run chat with `--history-dir /private/interactions`. Each visible response gets an
`interaction_id`; the private interaction file binds the sanitized question,
admitted evidence, answer, project/family, model-config hash, checkpoint, and
cutoff. The internal record is not printed in the bot response.

The user can accept a good answer, supply a correction, or reject the turn. For
example, place a corrected answer with valid `[E1]` citations in a text file:

```
agent-archive copilot self-upgrade-feedback \
  --interaction /private/interactions/<interaction-id>.jsonl \
  --verdict correct --reviewer Avi \
  --concept evidence_calibration --grounded --aligned \
  --correction /private/corrected-answer.txt \
  --allow-training-use --entities /private/reviewed-entities.json \
  --output /private/feedback-cycle-1
```

`--allow-training-use` is separate from the verdict. Without it, the assessment
is retained for analysis but cannot enter training. A training-permitted accepted
or corrected answer must be safe, grounded, aligned, and cite evidence present in
the saved interaction. Rejected, ungrounded, or misaligned answers never become
positive targets. Feedback records are create-once and bind the exact interaction;
resubmitting the same decision does not silently overwrite it.

Training-permitted feedback also requires a private reviewer-authored entity map,
using the same `ENTITY_TYPE_N` placeholders as initial dataset review. The compiler
never guesses which names are user-specific. A missing map, or one that omits the
interaction project, refuses training use for that feedback.

Compile feedback with a reviewed replay corpus so a new round does not learn only
from recent corrections:

```
agent-archive copilot self-upgrade-compile \
  --feedback /private/feedback-cycle-1 \
  --base-corpus /private/round-one \
  --base-reviews /private/round-one-reviews.jsonl \
  --output /private/upgrade-cycle-1
```

The compiler emits compatible `candidates.jsonl` and `reviews.jsonl`, abstracts
the saved project name, preserves conversation families, and reports concept and
verdict counts. The resulting queue still goes through `copilot build`, exact
token planning, held-out golden and grounded evaluation, and an explicit model
selection. `ready_for_training` and `ready_for_promotion` remain false at compile
time. No user click can mutate the active model, authorize provider spending, or
promote its own answer directly.

`copilot propose --corpus CORPUS --proposal PROPOSAL.json --output /private/lessons`
appends a correction, lesson, or withdrawal. Proposals contain a concept,
statement, creation timestamp and source evidence IDs; original logs never change.
This is an annotation layer, not automatic truth repair. Proposed annotations
are not automatically injected into answers or promoted into training.

New user corrections and verified outcomes become new reviewed candidates for
the next offline round. Generalization requires evidence across distinct cases,
not agreement among repeated model-generated claims. Repeat the held-out tests
before selecting a new model. This release supplies the bounded proposal/review/
evaluation mechanics; unattended continual learning and automatic promotion are
deliberately not enabled.
