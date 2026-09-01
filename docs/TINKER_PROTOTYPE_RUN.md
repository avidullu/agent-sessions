# Session-concept Tinker prototype — proposed $40 envelope

## Purpose

Run a deliberately small, non-promoting experiment before expanding the data
factory. The prototype asks whether reviewed session concepts produce a visible
grounding/alignment signal and whether the agent-sessions → sft-factory →
ons-lab → code-doot boundaries work end to end. It does not select a production
model or consume the separately planned larger-experiment budget.

No paid operation is authorized by this proposal. Launch requires the exact
dataset, token plan, current price snapshot, work orders, and one explicit owner
approval for this prototype's `$40` maximum.

## Pre-registered arms

| Arm | Starting model | Renderer | Training |
| --- | --- | --- | --- |
| A | `Qwen/Qwen3.5-9B-Base` | `role_colon` | none |
| B | `Qwen/Qwen3.5-9B-Base` | `role_colon` | one-epoch concept SFT |
| C | `Qwen/Qwen3.5-9B` | `qwen3_5_disable_thinking` | none |
| D | `Qwen/Qwen3.5-9B` | `qwen3_5_disable_thinking` | one-epoch concept SFT |

Both trained arms use seed 1729, R64 attention-only LoRA, no MLP/unembed
adaptation, the Dronacharya v2.1 learning-rate reference, and a maximum of
500,000 exact training tokens per arm. The renderer differs because raw-base and
chat-ready models have different native conversation surfaces; config validation
binds the mapping. No sports adapter initializes either arm.

## Small data target

Target 160 independently reviewed examples before splitting:

- 80 abstractions from Avi's logs, selected across distinct session families;
- 80 controlled synthetic teaching cases whose scenario families are disjoint
  from the golden suite;
- approximately 60/15/25 family-disjoint train/development/grounded-test roles
  (about 96/24/40 examples; exact counts depend on family grouping);
- the 40-case controlled golden suite remains evaluation-only and never trains.

Avi's labeling pass sees admitted evidence, the draft answer, a proposed concept,
and a corrected target. For each case he accepts, corrects, or rejects it and
separately marks grounding, alignment, and training-use permission. A correction
must cite displayed evidence. Entity names are consistently abstracted after
review. Rejected or uncertain cases do not become positive examples.

This prototype needs a separately named `prototype` admission profile frozen
before labels or results are inspected. It must not weaken the full experiment's
500/100/200 thresholds. The target prototype minimum is 96 train examples from
at least 15 families, 20 development examples, and 40 grounded test examples
from at least eight families. If review attrition misses that bar, the run waits.

## Evaluation and manual work

First run a 10-case format smoke against all four arms. If prompts, citations,
and blinded pack generation are valid, evaluate all four arms on:

- 40 controlled golden counterfactual cases;
- 40 grounded held-out cases from distinct user-log families.

That is 320 full evaluation responses after the 40-response smoke. Randomize
model identity per case. Avi rates task success, citation correctness,
unsupported claims, secret disclosure, and optional notes. Report arm-level and
per-concept scores, paired-counterfactual family success, grounded-family
bootstrap intervals, and the trained-minus-untuned delta within each starting
model. Do not compare raw-base prose style directly with chat-ready style as a
quality metric.

Prototype success means both trained arms complete, all artifacts bind exact
inputs, and at least one tuned arm improves its matched untuned baseline without
a secret disclosure or a material concept regression. The result is directional
only: 40 grounded and 40 synthetic test cases cannot authorize deployment.

## Budget

Pricing observed 2026-09-01 from Tinker's official model table for both 9B arms:
`$1.463/M` training tokens, `$0.660/M` prefill tokens, `$1.995/M` sampled tokens,
and `$0.10/GB-month` checkpoint storage.

| Bucket | Hard reservation | Expected use |
| --- | ---: | ---: |
| Two training arms | $8 | <= $1.463 at the two 500k-token maxima |
| Four-arm smoke + evaluation | $12 | expected under $3 even at conservative prompt/output lengths |
| Checkpoint/export/storage | $4 | expected well below $1 for short retention |
| Explicit recovery reserve | $8 | unused unless owner approves a diagnosed retry |
| Unallocated contingency | $8 | never consumed automatically |
| **Total** | **$40** | expected materially below cap |

Do not build a prototype-specific or cross-repository ledger for this run. Track
the estimate, actual charge, request identifier, and outcome in the Markdown run
record below. Before each paid stage, compare the recorded cumulative spend plus
the next estimate with the `$40` cap. A failed or timed-out request stops the run
for manual reconciliation; the recovery reserve is not retry permission. ONS,
SFT, and code-doot can adopt their durable ledger contracts independently later.

### Prototype run record

| Stage | Status | Estimate | Actual | Request/evidence | Decision |
| --- | --- | ---: | ---: | --- | --- |
| Data and token-plan freeze | Not started | $0 | $0 | — | Await reviewed dataset |
| Raw-base training | Not started | — | — | — | No launch approval yet |
| Chat-model training | Not started | — | — | — | No launch approval yet |
| Four-arm smoke | Not started | — | — | — | No launch approval yet |
| Full evaluation | Not started | — | — | — | No launch approval yet |
| Recovery | Not authorized | $8 reserved | $0 | — | Requires explicit diagnosis and approval |
| **Cumulative paid use** | **Not started** | **$0** | **$0** | — | **Hard stop at $40** |

## Integration stress path

1. **agent-sessions:** freeze reviewed data, whole-family splits, golden cases,
   blind packs, human grades, and score report.
2. **sft-factory:** render exact tokens, enforce arm-specific renderer and
   prototype admission, train, sample, and export short-lived checkpoints.
3. **ons-lab:** validate two matched managed work orders without reading prompts
   or executing the provider.
4. **code-doot:** consume a locator-free model-result candidate in inspection
   mode and record `deployment_candidate=false`. A small follow-up PR may add
   this generic inspection contract; the prototype does not create an endpoint,
   deploy weights, or move a serving default.

## Stop conditions

Stop before paid submission if renderer/tokenization, family isolation, source
use, the Markdown spend record, observer health, or exact work-order identity is
not current and green. Stop after the smoke if response parsing or citations are invalid. Stop
after training if either run is ambiguous until provider state is reconciled.
Regardless of scores, retain `promotion_authorized=false` and
`deployment_candidate=false` for this prototype.
