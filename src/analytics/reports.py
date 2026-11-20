from collections import Counter
from datetime import date
from html import escape

from src.core.models import Analysis, Status
from src.evaluation.scoring import CRITERIA


def summarize(calls: list[Analysis]) -> dict:
    scored = [c.score for c in calls if c.score is not None]
    misses = Counter(f.criterion_id for c in calls for f in c.findings if f.status == Status.FAIL)
    return {"calls": len(calls), "average_score": round(sum(scored) / len(scored), 1) if scored else None,
            "flagged": sum(c.review_priority != "Low" for c in calls), "misses": misses}


def report_html(calls: list[Analysis], agent_id: str, start: date, end: date) -> str:
    selected = [c for c in calls if c.agent_id == agent_id and start <= date.fromisoformat(c.created_at[:10]) <= end]
    stats = summarize(selected)
    issues = stats["misses"].most_common(3)
    goals = "".join(f"<li>Practice {escape(CRITERIA[key]['label'].lower())} ({count} flagged call(s)).</li>" for key, count in issues)
    examples = "".join(f"<li>{escape(c.call_id)}: {escape(item.title)} — {escape(item.next_step)}</li>"
                       for c in selected[:3] for item in c.coaching[:1])
    score = str(stats["average_score"]) + "%" if stats["average_score"] is not None else "Not enough evidence"
    caveat = "Findings are preliminary because fewer than 3 calls were analyzed." if len(selected) < 3 else "AI findings require human review."
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>CallIQ coaching report</title>
<style>body{{font:16px Arial;max-width:800px;margin:48px auto;color:#15243a;line-height:1.5}}h1{{color:#0a6172}}</style>
<h1>CallIQ weekly coaching report</h1><p><strong>Agent:</strong> {escape(agent_id)}<br><strong>Period:</strong> {start} to {end}</p>
<h2>Overview</h2><p>{stats['calls']} calls analyzed · average assessable score: {score} · {stats['flagged']} flagged for review.</p>
<h2>Coaching examples</h2><ul>{examples or '<li>No evaluated calls in this period.</li>'}</ul>
<h2>Next goals</h2><ul>{goals or '<li>Maintain observed strengths and review more calls.</li>'}</ul>
<p><em>{escape(caveat)} Scores omit criteria with insufficient evidence.</em></p></html>"""
