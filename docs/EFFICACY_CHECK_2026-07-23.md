# Mid-Project Efficacy Check — Rule Mining Pipeline

> **Status:** `Baseline (reference)` — a frozen measurement of the R1→R1b→R2 pipeline on real
> sessions as of 2026-07-23. **Owner:** `avidullu`. **Created:** `2026-07-23`.
> **Purpose:** the quantitative baseline the precision-hardening rows (R2a–R2c) are measured against.
> **Relation:** produced by the `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md` project (decision D23);
> reproduced by `tools/rules_demo.py`; illustrative examples live in the owner's private artifact
> (not committed — verbatim mined text stays off the tracked tree, per D17's redaction stance).

---

## 0. TL;DR

The shipped pipeline (extract → redact into a ledger → cluster & find contradictions) runs end to end
on 1,125 real sessions. **Mechanics and redaction are sound; ranking precision is not.** The tool
recalls 8/10 canonical rules but ranks agent-authored boilerplate above the user's own preferences.
The fix is measured, not guessed — scoring only user-authored turns surfaces the genuine rules — and
is captured as rows R2a–R2c.

---

## 1. What ran

- **Modules:** the merged `agent_sessions/rule_extractor` (R1), `rule_ledger` (R1b),
  `rule_clusterer` (R2) — the real shipped code, not a reimplementation.
- **Harness:** `tools/rules_demo.py` (reproducible; roots passed as `--root KIND=PATH`).
- **Corpus:** newest ≤500 sessions per source root reachable on the owner's machine.
- **Echo tagging (D18):** known-instruction texts limited to the owner's global `CLAUDE.md` and the
  repo `AGENTS.md` — deliberately *not* the agents' own system prompts (see finding #4).

---

## 2. Baseline metrics (compare post-fix runs to these)

| Metric | Baseline (2026-07-23) | Post-fix target |
|---|---:|---|
| Sessions mined | 1,125 | — |
| Agents | 5 (claude 467 · codex 136 · deepseek 500 · grok 20 · gemini 2) | — |
| Imperative statements extracted | 47,126 | ↓ (code/log lines filtered, R2c) |
| Evidence records (redacted, deduped) | 39,661 | — |
| **Secrets quarantined** | **43** | ≥ baseline (never regress) |
| Novelty split (novel / echo) | 30,981 / 16,160 | more echo caught (R2c #4) |
| Role split (user / request-prompt / assistant / developer / other) | 8,939 / 28,848 / 5,325 / 2,355 / 1,674 | — |
| Clusters | 6,490 | — |
| Saturation-suspect clusters (≥80% one agent) | 35 | penalized in score, not just flagged (R2b) |
| Contradictions surfaced | 7 | higher precision (fewer false positives) |
| **Ground-truth recall (§3.4)** | **8/10 overall · 6/6 session-derivable** | hold ≥ 6/6 derivable |
| **Top-20 precision (genuine user preference vs boilerplate)** | **≈ 0/20** — the core problem | ≥ 12/20 after R2a |

The last row is the headline regression to fix: the top-ranked clusters today are agent/tool
boilerplate, so a downstream consumer (R3 classifier, R4 publisher) would classify and publish noise.

---

## 3. The precision ladder (the core finding)

Same corpus, three scoring lenses:

1. **Raw (all roles) — noise wins.** Top clusters are injected system prompts and tool descriptions
   (e.g. "state that you are using DeepSeek V4 Pro", "respond with GitHub Copilot", GitHub-MCP
   `get_me`/`state_reason` tool instructions), each appearing in ~500 DeepSeek request-dumps that
   embed the full system prompt. They out-score everything by frequency alone.
2. **D18 ≥80% saturation filter — 35 clusters removed.** Kills the ~100%-saturation injected prompts,
   but moderate boilerplate (Codex/Claude system-reminders, MCP calls, skill triggers at 15–26%
   saturation) survives below the threshold.
3. **User turns only — signal emerges.** The canonical preferences rank at the top: *one PR per work
   item; never push to the default branch; paid LLMs = inference only, never a training source; stage
   explicit paths, never `git add -A`; resume as if the break never happened.*

The genuine rules are present in all three (recall is fine); they are simply outranked until agent
turns stop being scored as if the user wrote them.

---

## 4. Findings → tracker rows

| # | Finding | Fix (row) |
|---|---|---|
| 1 | Every role is scored equally; agent boilerplate outranks user preferences. | **R2a** — role-privileged scoring |
| 2 | D18 saturation is only a post-filter; ~100%-injected prompts still rank until removed by hand. | **R2b** — saturation as a score penalty |
| 3 | Code/log lines (line-numbered code, `//`/`#` comments, `=== CHECK ===` banners, `</tag>` fragments) are extracted as "rules" and pollute both clusters and contradictions. | **R2c** — extraction hygiene |
| 4 | Echo tagging only knew the owner's `CLAUDE.md`/`AGENTS.md`; the agents' own system prompts went untagged. | **R2c** (optional) — accept agent system prompts as `known_instruction_texts` |

Contradiction precision is mixed (7 pairs): some genuine (a paid-LLM "never a training source" nuance),
but false positives from polarity-flips on *agreeing* statements and token collisions on overloaded
words ("pass") — largely downstream of finding #3 (code/log lines mined as rules).

---

## 5. What held up

- **End-to-end mechanics** on real, multi-agent data: extraction, redaction, dedup, clustering,
  contradiction detection all function without error.
- **Redaction (D17):** 43 high-confidence secrets quarantined; home-dir paths and emails placeholdered
  across the 39,661 surviving records. Zero secret leakage into the ledger.
- **Recall (§3.4):** 6/6 session-derivable canonical rules found; the 2 misses are memory-only items
  (never written in a session), exactly as D12 predicted.

---

## 6. Reproduce

```bash
PYTHONPATH=. python3 tools/rules_demo.py --limit-per-source 500 \
  --root claude=<claude-projects> --root codex=<codex-sessions> \
  --root deepseek_request_dump=<deepseek-dumps> --root grok=<grok-sessions> \
  --known <global CLAUDE.md> --known AGENTS.md \
  --out /tmp/efficacy.json
```

Post-fix, re-run against the same roots and compare §2's table — especially **top-20 precision** and
**contradiction false-positive rate** — to quantify the R2a–R2c improvement.
