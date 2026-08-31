"""CLI orchestration: local retrieval and a separately authorized sampler CLI.

Only the admitted evidence pack crosses into inference. Search output is never
trusted as evidence: hits resolve back to the frozen, redacted local snapshot.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from .baseline_redaction import redact_text
from .copilot_dataset import SYSTEM, build_dataset, prepare, private_dir, read_jsonl, write_jsonl
from .copilot_records import digest, timestamp


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    if not args.launch or not args.ack_data_transmission:
        raise ValueError("evaluation requires --launch and --ack-data-transmission")
    cases = read_jsonl(args.cases)
    if len({c["id"] for c in cases}) != len(cases) or not cases:
        raise ValueError("evaluation cases must have unique IDs and be nonempty")
    output = private_dir(args.output)

    def predictions() -> Any:
        for case in cases:
            messages = case["messages"]
            if messages[-1]["role"] != "assistant":
                raise ValueError("evaluation case must end in a withheld reference answer")
            prompt = messages[:-1]
            if any(redact_text(m["content"]).blocked for m in prompt):
                raise ValueError("unsafe evaluation prompt; no inference submitted")
            command = [
                args.sftf,
                "chat",
                "sample",
                "--config",
                str(args.model_config),
                "--budget-ledger",
                str(args.budget_ledger),
                "--request-id",
                digest([args.evaluation_id, case["id"]]),
                "--launch",
                "--ack-data-transmission",
            ]
            if args.checkpoint:
                command.extend(["--checkpoint", args.checkpoint])
            start = time.monotonic()
            response = subprocess.run(
                command, input=json.dumps({"messages": prompt}), capture_output=True, text=True, timeout=180, check=True
            )
            value = json.loads(response.stdout)
            clean = redact_text(value["answer"])
            if clean.blocked:
                value["answer"] = "[RESPONSE BLOCKED: suspected secret]"
                value["secret_scanner_blocked"] = True
            else:
                value["answer"] = clean.redacted_text
            yield {
                **value,
                "id": case["id"],
                "input_sha256": digest(prompt),
                "elapsed_s": round(time.monotonic() - start, 3),
                "evaluation_id": args.evaluation_id,
            }

    write_jsonl(output / "predictions.jsonl", predictions())
    return {
        "status": "predictions_complete_grading_pending",
        "cases": len(cases),
        "prediction_file": str(output / "predictions.jsonl"),
    }


def source(value: str) -> tuple[str, str]:
    kind, separator, root = value.partition("=")
    if not separator or not root or kind not in ("codex", "claude", "grok"):
        raise argparse.ArgumentTypeError("expected codex=PATH, claude=PATH, or grok=PATH")
    return kind, root


def retrieve(
    corpus: Path, question: str, *, project: str, as_of: str, session: str | None = None, cass: str = "cass"
) -> list[dict[str, str]]:
    cutoff = timestamp(as_of)
    if not cutoff:
        raise ValueError("--as-of must include a timezone")
    records = [r for r in read_jsonl(corpus / "sessions.jsonl") if r["project"] == project]
    if session:
        records = [r for r in records if r["session_id"] == session]
    else:
        result = subprocess.run(
            [cass, "search", question, "--robot", "--limit", "50", "--no-maintenance"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        value = json.loads(result.stdout)
        paths = {hit.get("source_path") or hit.get("path") for hit in value.get("hits", [])}
        records = [r for r in records if r["source_file"] in paths]
    evidence = []
    seen = set()
    for record in records:
        for event in record["messages"]:
            if not event["timestamp"] or event["timestamp"] > cutoff or event["event_id"] in seen:
                continue
            clean = redact_text(event["text"])
            if clean.blocked:
                continue
            evidence.append({**event, "text": clean.redacted_text})
            seen.add(event["event_id"])
    evidence.sort(key=lambda e: (e["timestamp"], e["event_id"]), reverse=True)
    selected = []
    chars = 0
    for event in evidence:
        if chars + len(event["text"]) > 16000:
            continue
        selected.append(event)
        chars += len(event["text"])
        if len(selected) == 12:
            break
    return list(reversed(selected))


def answer(args: argparse.Namespace, question: str) -> dict[str, Any]:
    scanned = redact_text(question)
    if scanned.blocked:
        raise ValueError("question contains suspected secrets; not transmitted")
    evidence = retrieve(
        args.corpus, scanned.redacted_text, project=args.project, as_of=args.as_of, session=args.session, cass=args.cass
    )
    # Source locators never reach the model. Case-local IDs improve transfer.
    sources = {f"E{i + 1}": e["event_id"] for i, e in enumerate(evidence)}
    packed = [{**e, "event_id": f"E{i + 1}", "call_id": ""} for i, e in enumerate(evidence)]
    prompt = {"question": scanned.redacted_text, "as_of": args.as_of, "evidence": packed}
    if not evidence:
        return {
            "answer": "I found no admitted evidence for that project and time. Select a session or refresh the local index.",
            "sources": {},
            "status": "insufficient_evidence",
            "provider_called": False,
        }
    if args.evidence_only:
        return {"evidence": packed, "sources": sources, "provider_called": False}
    if not args.launch or not args.ack_data_transmission or not args.model_config or not args.budget_ledger:
        raise ValueError("inference needs --model-config, --budget-ledger, --launch and --ack-data-transmission")
    command = [
        args.sftf,
        "chat",
        "sample",
        "--config",
        str(args.model_config),
        "--budget-ledger",
        str(args.budget_ledger),
        "--request-id",
        str(uuid.uuid4()),
        "--launch",
        "--ack-data-transmission",
    ]
    if args.checkpoint:
        command.extend(["--checkpoint", args.checkpoint])
    started = time.monotonic()
    result = subprocess.run(
        command,
        input=json.dumps(
            {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(prompt)}]}
        ),
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )
    value = json.loads(result.stdout)
    output = redact_text(value["answer"])
    if output.blocked:
        raise ValueError("model response blocked by secret scanner")
    citations = re.findall(r"\[(E\d+)\]", output.redacted_text)
    if not citations or any(c not in sources for c in citations):
        return {
            "answer": "The response did not provide valid evidence references; no grounded answer is available.",
            "sources": sources,
            "status": "invalid_citations",
            "provider_called": True,
        }
    return {
        **value,
        "answer": output.redacted_text,
        "sources": sources,
        "status": "answered",
        "provider_called": True,
        "elapsed_s": round(time.monotonic() - started, 3),
    }


def handle(args: argparse.Namespace) -> int:
    try:
        if args.copilot_action == "prepare":
            value = prepare(args.output, args.source, args.ssh_host, args.ssh_source)
        elif args.copilot_action == "build":
            value = build_dataset(args.corpus, args.reviews, args.output, tuple(args.holdout_project))
        elif args.copilot_action == "propose":
            from .copilot_concepts import propose_lesson

            value = propose_lesson(args.corpus, json.loads(args.proposal.read_text()), args.output)
        elif args.copilot_action == "score":
            from .copilot_eval import compare

            value = compare(args.cases, args.baseline, args.candidate, args.grades)
        elif args.copilot_action == "evaluate":
            value = evaluate(args)
        else:
            if not args.question:
                while True:
                    try:
                        question = input("You> ").strip()
                    except EOFError:
                        return 0
                    if question in ("/quit", "/exit"):
                        return 0
                    if question:
                        print(json.dumps(answer(args, question), ensure_ascii=False, indent=2))
                # Each turn retrieves fresh evidence; no silent permanent memory writes.
            value = answer(args, args.question)
            if args.history_dir:
                write_jsonl(private_dir(args.history_dir) / f"{uuid.uuid4()}.jsonl", [value])
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, KeyError) as exc:
        # Provider stderr and input dumps can contain raw data. Never echo them.
        message = (
            "external command failed; no automatic retry" if isinstance(exc, subprocess.SubprocessError) else str(exc)
        )
        print(f"copilot: {message}", file=sys.stderr)
        return 2


def add_parser(sub: Any) -> None:
    parser = sub.add_parser("copilot", help="Private concept-learning session copilot; no automatic paid work.")
    actions = parser.add_subparsers(dest="copilot_action", required=True)
    collect = actions.add_parser("prepare", help="Read and sanitize local/SSH logs into unreviewed candidates.")
    collect.add_argument("--source", action="append", type=source, default=[])
    collect.add_argument("--ssh-host")
    collect.add_argument("--ssh-source", action="append", type=source, default=[])
    collect.add_argument("--output", required=True, type=Path)
    build = actions.add_parser("build", help="Build datasets from explicit concept/evidence reviews.")
    build.add_argument("--corpus", required=True, type=Path)
    build.add_argument("--reviews", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument(
        "--holdout-project", action="append", default=[], help="Entire project held out for concept transfer."
    )
    chat = actions.add_parser("chat", help="Interactive chat or one question; inference requires explicit opt-in.")
    chat.add_argument("question", nargs="?")
    chat.add_argument("--corpus", required=True, type=Path)
    chat.add_argument("--project", required=True)
    chat.add_argument("--as-of", required=True)
    chat.add_argument("--session", help="Select an exact session instead of cass search.")
    chat.add_argument("--cass", default="cass")
    chat.add_argument("--sftf", default="sftf")
    chat.add_argument("--model-config", type=Path)
    chat.add_argument("--budget-ledger", type=Path)
    chat.add_argument("--checkpoint")
    chat.add_argument("--evidence-only", action="store_true")
    chat.add_argument("--launch", action="store_true")
    chat.add_argument("--ack-data-transmission", action="store_true")
    chat.add_argument("--history-dir", type=Path)
    propose = actions.add_parser("propose", help="Append an evidence-backed correction/lesson; never rewrite logs.")
    propose.add_argument("--corpus", type=Path, required=True)
    propose.add_argument("--proposal", type=Path, required=True)
    propose.add_argument("--output", type=Path, required=True)
    score = actions.add_parser("score", help="Compare predictions using reviewed grades and grouped intervals.")
    for name in ("cases", "baseline", "candidate", "grades"):
        score.add_argument("--" + name, type=Path, required=True)
    evaluation = actions.add_parser("evaluate", help="Run identical evidence prompts, withholding reference answers.")
    for name in ("cases", "model-config", "budget-ledger", "output"):
        evaluation.add_argument("--" + name, type=Path, required=True)
    evaluation.add_argument("--evaluation-id", required=True)
    evaluation.add_argument("--checkpoint")
    evaluation.add_argument("--sftf", default="sftf")
    evaluation.add_argument("--launch", action="store_true")
    evaluation.add_argument("--ack-data-transmission", action="store_true")
    for action in (collect, build, chat, propose, score, evaluation):
        action.set_defaults(func=handle)
