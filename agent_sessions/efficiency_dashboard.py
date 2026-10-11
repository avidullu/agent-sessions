"""One self-contained local dashboard. No remote assets, archive URLs or logs."""

from __future__ import annotations

import html
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from .efficiency import EvidenceRejected, validate_report


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _label(value: Any, unit: str = "") -> str:
    if value is None:
        return "Unavailable"
    if unit == "bytes":
        return f"{value / 1024**2:,.1f} MiB" if value >= 1024**2 else f"{value:,} B"
    return f"{value:,.2f} {unit}".strip() if isinstance(value, float) else f"{value:,} {unit}".strip()


def render(document: dict[str, Any]) -> str:
    report = validate_report(document)
    collection = report["collection"]
    bindings = {row["checkpoint_id"]: row for row in report["bindings"]}
    banner = (
        '<div class="demo" role="note">SYNTHETIC DEMO · Placeholder identities and observations. No owner sessions were read.</div>'
        if report["synthetic"]
        else ""
    )
    cards = "".join(
        f'<article class="stat"><span>{_esc(label)}</span><strong>{_esc(value)}</strong><small>{_esc(detail)}</small></article>'
        for label, value, detail in (
            (
                "Catalogued sessions",
                _label(collection["sessions"]),
                "Valid merged metadata rows; partial catalogs may omit sessions",
            ),
            (
                "Known messages",
                _label(collection["messages"]),
                "Incomplete" if not collection["counts_complete"] else "Catalog message counts complete",
            ),
            (
                "Local Markdown",
                _label(collection["local_markdown_bytes"], "bytes"),
                "Reported artifact size; private content stays local",
            ),
            ("Measured savings", "Unavailable", "Matched before / after evidence has not been imported"),
        )
    )
    source_rows = (
        "".join(
            f"<tr><td><strong>{_esc(row['source_id'])}</strong><small>{_esc(row['kind'])}</small></td>"
            f'<td><span class="badge">{_esc(row["state"].replace("_", " "))}</span></td></tr>'
            for row in collection["sources"]
        )
        or '<tr><td colspan="2">No configured sources reported</td></tr>'
    )
    gaps = "".join(
        f"<li><strong>{_label(collection[key])}</strong> {_esc(label)}</li>"
        for key, label in (
            ("invalid_catalog_rows", "invalid catalog rows"),
            ("sessions_with_partial_parse", "partially parsed sessions"),
            ("sessions_with_unknown_message_count", "sessions with unknown message counts"),
            ("empty_source_files", "empty or metadata-only inputs"),
            ("missing_local_artifacts", "missing local artifacts"),
        )
    )
    indexes = ", ".join(f"{_esc(key)}: {_esc(value)}" for key, value in collection["indexes"].items())
    action_rows = []
    for row in report["actions"]:
        ident = row["identity"]
        binding = bindings.get(row["checkpoint_id"])
        state = "blocked · no binding" if binding is None else binding["state"].replace("_", " ")
        if row["stale"]:
            state = "blocked · stale plan"
        details = (
            "Package bytes and no-egress execution unverified"
            if binding
            else "Supply an opaque session/worktree binding"
        )
        if binding and binding["state"] == "blocked":
            details = "; ".join(binding["reasons"])
        binding_details = (
            ""
            if binding is None
            else (f"<small>Session: {_esc(binding['session_id'])}<br>Worktree: {_esc(binding['worktree_id'])}</small>")
        )
        package = binding.get("package") if binding else None
        package_details = (
            ""
            if package is None
            else (
                f"<details><summary>Package declaration</summary><dl><dt>Package</dt><dd>{_esc(package['digest'])}</dd>"
                f"<dt>Closure</dt><dd>{_esc(package['closure_digest'])}</dd><dt>Cache</dt><dd>{_esc(package['cache_digest'])}</dd>"
                f"<dt>Created / expires UTC</dt><dd>{_esc(package['created_at'])} / {_esc(package['expires_at'])}</dd>"
                f"<dt>Downloads policy</dt><dd>{_esc(package['download_policy'])} (declared)</dd></dl></details>"
            )
        )
        action_rows.append(
            f'<tr data-checkpoint data-action="{_esc(row["action"])}"><td><strong>{_esc(ident["repository"])} #{ident["pr_number"]}</strong>'
            f"<small>{_esc(ident['recipe'])} · {_esc(row['observed_at'])} UTC</small>"
            f'<code title="{_esc(ident["source_sha"])}">{_esc(ident["source_sha"][:12])}</code>'
            f"<details><summary>Exact assurance identity</summary><dl>"
            + "".join(f"<dt>{_esc(key)}</dt><dd>{_esc(value)}</dd>" for key, value in ident.items())
            + f"<dt>Checkpoint</dt><dd>{_esc(row['checkpoint_id'])}</dd></dl></details></td>"
            f'<td><span class="badge action-{_esc(row["action"])}">{_esc(row["action"])}</span><small>{_esc(row["reason"])}</small>'
            f"<small>Not before: {_esc(row['not_before'] or 'not supplied')}</small></td>"
            f"<td><strong>{_esc(state)}</strong><small>{_esc(details)}</small>{binding_details}{package_details}</td></tr>"
        )
    actions = (
        "".join(action_rows)
        or '<tr><td colspan="3">No Bheem plan supplied. Checkpoint activity is unavailable.</td></tr>'
    )
    run_rows = []
    for run in report["runs"]:
        metrics = run["metrics"]
        cells = "".join(
            f"<td><strong>{_esc(_label(metrics[key]['value'], metrics[key]['unit']))}</strong>"
            f"<small>{_esc(metrics[key]['quality'])}</small><small>{_esc(metrics[key].get('reason') or metrics[key]['scope'])}</small></td>"
            for key in ("cpu", "peak_memory", "network_received", "network_sent")
        )
        run_rows.append(
            f"<tr><td><strong>{_esc(run['run_id'])}</strong><small>{_esc(run['outcome']['status'])} · "
            f"{_esc(run['cache']['state'])} cache</small><small>{_esc(run['machine']['surface_id'])}</small>"
            f"<small>{'Identity bound' if run['binding_checkpoint_id'] else 'No matching binding'}</small>"
            f"<details><summary>Collector and limits</summary><dl>"
            + "".join(f"<dt>{_esc(key)}</dt><dd>{_esc(value)}</dd>" for key, value in run["collector"].items())
            + f"<dt>Declared limits</dt><dd>{_esc(run['limits'])}</dd><dt>Observed controls</dt><dd>{_esc(run['controls'])}</dd>"
            f"<dt>Network boundary</dt><dd>{_esc(run['network_boundary'])}</dd>"
            f"<dt>Started / finished UTC</dt><dd>{_esc(run['timing']['started_at'])} / {_esc(run['timing']['finished_at'])}</dd>"
            f"</dl></details></td>{cells}</tr>"
        )
    runs = (
        "".join(run_rows)
        or '<tr><td colspan="5">No workload observations supplied. CPU, memory and traffic stay unavailable.</td></tr>'
    )
    counts = {
        kind: sum(row["action"] == kind for row in report["actions"]) for kind in ("select", "supersede", "defer")
    }
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Sessions · Checkpoints and efficiency</title><style>
:root{{--ink:#14223c;--muted:#58677e;--line:#dbe3ed;--blue:#2152b8;--bg:#f4f7fc}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}a{{color:var(--blue)}}
.skip{{position:absolute;left:1rem;top:-4rem;background:white;padding:1rem;z-index:3}}.skip:focus{{top:0}}
.wrap{{max-width:1260px;margin:auto;padding:32px}}header{{background:linear-gradient(125deg,#122449,#254da0);color:white;border-radius:22px;padding:34px;box-shadow:0 14px 40px #14223c18}}
.eyebrow{{font-size:13px;letter-spacing:.12em;font-weight:750;text-transform:uppercase;color:#c2d9ff}}h1{{margin:6px 0;font-size:clamp(27px,4vw,40px);line-height:1.2}}h2{{font-size:23px;margin:0 0 8px}}h3{{margin:0 0 8px;font-size:18px}}p{{margin:8px 0}}header p{{color:#e1ebff;max-width:760px}}
.demo{{background:#fff0bf;border:1px solid #e2c570;color:#5e4300;border-radius:12px;padding:13px 18px;margin-bottom:18px;font-weight:650}}
nav{{display:flex;flex-wrap:wrap;gap:10px;margin-top:21px}}nav a{{color:white;background:#ffffff14;border:1px solid #ffffff55;border-radius:9px;padding:10px 15px;min-height:44px;text-decoration:none}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}}.stat,section{{background:white;border:1px solid var(--line);border-radius:16px;padding:23px}}.stat{{min-width:0;overflow-wrap:anywhere}}.stat span{{font-size:13px;font-weight:700;color:var(--muted)}}.stat strong{{display:block;font-size:28px;margin:8px 0}}small{{display:block;color:var(--muted);font-size:12px;line-height:1.5;margin:4px 0}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}section{{margin-bottom:22px;scroll-margin-top:20px}}
.note{{border-left:4px solid #daa928;background:#fff9e8;padding:12px 16px;border-radius:0 8px 8px 0;font-size:14px;margin:17px 0}}.positive{{border-left-color:#287861;background:#edf8f3}}.badge{{display:inline-block;background:#eef2f8;border:1px solid #d7dfeb;border-radius:30px;padding:4px 10px;font-size:12px;font-weight:700;white-space:nowrap}}.action-select{{color:#175444;background:#edf8f3}}.action-supersede{{color:#654508;background:#fff6dc}}.action-defer{{color:#2b4b85;background:#eef4ff}}
table{{border-collapse:collapse;width:100%;text-align:left}}th{{font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.03em;background:#f7f9fc;padding:12px}}td{{padding:15px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}}tr:last-child td{{border-bottom:0}}.scroll{{overflow-x:auto}}.wide{{min-width:690px}}code{{font-size:12px;color:#365789}}details{{margin-top:8px}}summary{{cursor:pointer;color:var(--blue);padding:10px 0;min-height:44px;font-size:13px;font-weight:650}}dl{{margin:5px 0;font-size:12px;max-width:400px}}dt{{color:var(--muted);font-weight:700}}dd{{margin:0 0 8px;overflow-wrap:anywhere}}
.controls{{display:flex;flex-wrap:wrap;gap:14px;align-items:end;margin:18px 0}}label{{display:block;color:var(--muted);font-size:13px;font-weight:700}}input,select{{font:inherit;padding:10px 12px;min-height:44px;border:1px solid #aab8cc;border-radius:8px;background:white;color:var(--ink)}}input{{width:min(340px,100%)}}:focus-visible{{outline:3px solid #5988ef;outline-offset:3px}}ul{{padding-left:22px}}li{{padding:2px 0}}footer{{font-size:13px;color:var(--muted);padding:0 4px 30px}}.muted{{color:var(--muted);font-size:14px}}[hidden]{{display:none!important}}
@media(max-width:900px){{.stats{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}.wrap{{padding:18px}}header{{padding:26px}}}}@media(max-width:480px){{.wrap{{padding:12px}}.stat,section{{padding:18px}}.stats{{gap:10px}}.stat strong{{font-size:23px}}nav a{{font-size:14px}}}}
@media(max-width:380px){{.stats{{grid-template-columns:1fr}}}}
</style></head><body><a class="skip" href="#main">Skip to dashboard</a><div class="wrap">{banner}<header><div class="eyebrow">Agent Sessions × Bheem · local evidence</div><h1>Less churn. Clearer checkpoints.</h1><p>See collection gaps, planned checkpoints and attributable workload use together. Keep private logs in the archive and admission decisions with Bheem.</p><nav aria-label="Dashboard sections"><a href="#collection">Collection</a><a href="#checkpoints">Checkpoints</a><a href="#resources">Resource observations</a><a href="#next">Integration path</a></nav></header>
<main id="main"><div class="stats">{cards}</div><div class="grid"><section id="collection"><h2>Collection health</h2><p class="muted">{_esc(collection["state"].replace("_", " "))} · last recorded export: {_esc(collection["last_successful_export"] or "unavailable")}</p><div class="note">A source being available does not prove complete collection. Catalog counts can be partial.</div><table><thead><tr><th>Source alias / provider</th><th>Reported state</th></tr></thead><tbody>{source_rows}</tbody></table><p class="muted">{indexes}</p></section><section><h2>Evidence to repair</h2><p class="muted">Keep missing collection evidence visible before increasing capture frequency.</p><ul>{gaps}</ul><div class="note positive"><strong>Efficient log use</strong><br>Read existing catalog metadata here. Reuse the archive's existing incremental export fingerprints; this dashboard does not reparse provider transcripts or measure export savings.</div></section></div>
<section id="checkpoints"><h2>Timestamped checkpoint activity</h2><p class="muted">{counts["select"]} selected · {counts["supersede"]} superseded intents · {counts["defer"]} deferred decisions in this supplied plan</p><div class="note">Selection is a plan decision. It does not prove a run started or that a build was avoided. A matching package declaration does not admit execution.</div><div class="controls"><div><label for="search">Find repository, SHA or checkpoint</label><input id="search" type="search" placeholder="Filter checkpoint evidence" autocomplete="off"></div><div><label for="action">Plan action</label><select id="action"><option value="">All actions</option><option value="select">Selected</option><option value="supersede">Superseded</option><option value="defer">Deferred</option><option value="cancel-candidate">Cancellation candidate</option></select></div><p id="visible" class="muted" role="status" aria-live="polite"></p></div><div class="scroll" tabindex="0" aria-label="Checkpoint evidence table"><table class="wide"><thead><tr><th>Exact checkpoint</th><th>Plan decision</th><th>Package / binding state</th></tr></thead><tbody>{actions}</tbody></table></div><p id="empty" class="muted" hidden>No checkpoints match these filters.</p></section>
<section id="resources"><h2>Resource observations</h2><p class="muted">Per-run imported observations, with explicit quality and scope. No cross-run totals.</p><div class="scroll" tabindex="0" aria-label="Resource observations table"><table class="wide"><thead><tr><th>Run / collector</th><th>CPU time</th><th>Peak memory</th><th>Network RX</th><th>Network TX</th></tr></thead><tbody>{runs}</tbody></table></div><div class="note">CPU seconds differ from elapsed seconds. Memory peaks cannot be added. An isolation boundary or download-deny policy is not a traffic counter; unavailable traffic never becomes zero. Imported records are unsigned observations.</div></section>
<section id="next"><h2>From artifact seam to efficient execution</h2><ol><li><strong>Agent Sessions:</strong> export bounded catalog health and an opaque session/worktree binding.</li><li><strong>Bheem:</strong> supply the actual checkpoint plan and validated workload record for the exact source/base and closure identities.</li><li><strong>Executor follow-up:</strong> verify package bytes, closure completeness, boot/resource reservation and no-egress execution before admitting work.</li><li><strong>Measure:</strong> retain matched before/after context, cache state, collector scope and traffic counter evidence before reporting savings.</li></ol><p class="muted">This page installs no scheduler, runs no command from manifests and downloads no dependency. Production checkpoint adoption and automatic log/receipt transport remain follow-up work.</p></section></main><footer>Snapshot UTC: {_esc(report["generated_at"])} · {_esc(report["schema"])}<br>Generated from an allowlisted metadata projection. No prompts, transcripts, provider paths or external assets.</footer></div>
<script>const rows=[...document.querySelectorAll('[data-checkpoint]')];const search=document.getElementById('search'),action=document.getElementById('action');function filter(){{const q=search.value.toLowerCase();let visible=0;for(const row of rows){{row.hidden=!(row.textContent.toLowerCase().includes(q)&&(!action.value||row.dataset.action===action.value));if(!row.hidden)visible++;}}document.getElementById('visible').textContent=`${{visible}} of ${{rows.length}} decisions visible`;document.getElementById('empty').hidden=visible>0||rows.length===0;}}search.addEventListener('input',filter);action.addEventListener('change',filter);filter();</script></body></html>"""


def write_snapshot(document: dict[str, Any], output: Path) -> Path:
    rendered = render(document)
    output = output.absolute()
    # Refuse existing output and link ancestors. Never replace another runtime.
    if any(parent.is_symlink() for parent in (output, *output.parents)):
        raise EvidenceRejected("output links are refused")
    output.mkdir(mode=0o700)
    try:
        for name, raw in (
            ("report.json", json.dumps(document, indent=2, ensure_ascii=False)),
            ("index.html", rendered),
        ):
            fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(raw)
    except OSError:
        raise EvidenceRejected("snapshot output unavailable; existing bytes preserved") from None
    return output


def make_server(html_bytes: bytes, port: int = 0) -> HTTPServer:
    """Serve an immutable in-memory page on loopback only, never directory files."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in {"/", "/index.html"}:
                self.send_error(404, "Not found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(html_bytes)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return HTTPServer(("127.0.0.1", port), Handler)
