# Baseline Efficacy Evaluation

- Passed: `6`
- Failed: `0`
- Total: `6`

| Metric | Phase | Status | Detail |
|--------|-------|--------|--------|
| `E1.detect.tracked-project-template` | detect | pass | Found guardrail.tracked-project-docs with confidence 0.99. |
| `E2.anchor.template-source` | anchor | pass | Anchor links badminton-highlight-indexer/docs/PROJECT_DOC_TEMPLATE.md. |
| `E3.dogfood.tracked-project-doc` | dogfood | pass | Tracked project doc with §7 rows present. |
| `E4.promote.global-baseline` | promote | pass | 3 promoted guardrail block(s) in engineering-guardrails.md. |
| `E5.publish.agent-slices` | publish | pass | CLAUDE.generated.md has 8 rules across 96 lines. |
| `E6.calibrate.feedback-loop` | calibrate | pass | Suppressed 1 ids; 0 confidence adjustments. |
