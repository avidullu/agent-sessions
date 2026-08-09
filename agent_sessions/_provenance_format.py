"""Human-readable formatting for provenance summaries."""

from __future__ import annotations

from typing import Any


def format_summary(value: dict[str, Any]) -> str:
    attribution = value["attribution"]
    observed = value["observed"]
    agents = ", ".join(attribution["agent_ids"]) if attribution["agent_ids"] else "unknown"
    lines = [
        f"{value['repository']}#{value['pull_number']}: {value['title']}",
        f"Observed: submitted_by={observed['submitted_by'] or '-'} merged_by={observed['merged_by'] or '-'} state={value['state']} merged={str(value['merged']).lower()}",
        f"Agent attribution: {agents} (status={attribution['status']}, confidence={attribution['confidence']})",
    ]
    if attribution["evidence"]:
        lines.append("Evidence:")
        lines.extend(f"- {item}" for item in attribution["evidence"])
    lines.append("Commits:")
    for commit in value["commits"]:
        lines.append(
            f"- {commit['sha'][:12]} author={commit['author_name']} <{commit['author_email']}> "
            f"forgejo={commit['forgejo_author'] or '-'} signed={str(commit['signature_verified']).lower()}"
        )
    if value["declared_coauthors"]:
        lines.append("Declared co-authors (unverified trailers):")
        lines.extend(f"- {item['name']} <{item['email']}>" for item in value["declared_coauthors"])
    if value["reviews"]:
        lines.append("Reviews:")
        lines.extend(f"- {item['actor_login']}: {item['state']}" for item in value["reviews"])
    if value["comment_actors"]:
        actors = sorted({item["actor_login"] for item in value["comment_actors"]})
        lines.append("Comment actors: " + ", ".join(actors))
    return "\n".join(lines)
