#!/usr/bin/env python3
"""
report.py — Read evolution_log.jsonl and post summary to Telegram.

Usage:
  python3 report.py                   # latest run summary
  python3 report.py --trend 5        # last 5 candidates trend
  python3 report.py --candidate 12    # detailed for candidate 12
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

WORKSPACE = Path.home() / "hermes-evolution"
LOG_FILE  = WORKSPACE / "evolution_log.jsonl"
CANDIDATES_DIR = WORKSPACE / "candidates"


def load_log(n: Optional[int] = None):
    """Load last n entries from evolution log."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().strip().split("\n")
    entries = []
    for line in reversed(lines):
        if line:
            try:
                entries.append(json.loads(line))
            except:
                pass
        if n and len(entries) >= n:
            break
    return entries


def load_candidate(candidate_num: int):
    """Load full eval_results.json for a candidate."""
    f = CANDIDATES_DIR / f"candidate_{candidate_num}" / "eval_results.json"
    if f.exists():
        return json.loads(f.read_text())
    return None


def format_score(score: float) -> str:
    """Color-coded score string."""
    if score >= 90:
        return f"🟢 {score:.1f}"
    elif score >= 75:
        return f"🟡 {score:.1f}"
    elif score >= 60:
        return f"🟠 {score:.1f}"
    else:
        return f"🔴 {score:.1f}"


def trend_arrow(current: float, prior: float) -> str:
    if current > prior + 1:
        return "▲"
    elif current < prior - 1:
        return "▼"
    else:
        return "➟"


def report_latest(entries):
    """Single-line summary of most recent run."""
    if not entries:
        return "No evolution runs yet."
    latest = entries[0]
    candidate = latest.get("candidate", "?")
    score = latest.get("final_score", 0)
    br = latest.get("br_gate", "?")
    categories = latest.get("category_scores", {})

    # Delta vs prior
    delta_str = ""
    if len(entries) >= 2:
        prior = entries[1].get("final_score", 0)
        arrow = trend_arrow(score, prior)
        delta = score - prior
        delta_str = f" ({arrow}{delta:+.1f} vs prev)"

    header = f"*{candidate} — {format_score(score)}/100* {delta_str}"
    header += f"\n_BR gate: {br}_"

    cat_lines = []
    for cat, val in sorted(categories.items()):
        cat_lines.append(f"  {cat}: {val:.0f}/100")

    return f"{header}\n" + "\n".join(cat_lines)


def report_trend(entries, n):
    """Multi-candidate trend table."""
    rows = []
    for i, e in enumerate(entries[:n]):
        candidate = e.get("candidate", "?")
        score = e.get("final_score", 0)
        br = e.get("br_gate", "?")
        pf_dom = e.get("pf_dominated", None)

        dom_str = "📉" if pf_dom else "🏔️"
        rows.append(f"{dom_str} {candidate}: {score:.1f}/100 [{br}]")

    return "*Evolution Trend*\n" + "\n".join(rows)


def report_detailed(candidate_num: int):
    """Full breakdown for one candidate."""
    data = load_candidate(candidate_num)
    if not data:
        return f"No eval_results.json found for candidate_{candidate_num}"

    score = data.get("final_score", 0)
    br = data.get("br_gate", "?")
    phases = data.get("phases", {})
    pf = data.get("pf", {})
    rw = data.get("rw_metrics", {})

    lines = [f"*candidate_{candidate_num} — {format_score(score)}/100*"]
    lines.append(f"_BR gate: {br}_")

    # Categories
    cats = data.get("category_scores", {})
    if cats:
        lines.append("\n*Categories:*")
        for cat, val in sorted(cats.items()):
            av = data.get("category_av_scores", {}).get(cat, 0)
            ij = data.get("category_ij_scores", {}).get(cat, 0)
            lines.append(f"  {cat}: {val:.0f}/100 (AV={av:.0f} IJ={ij:.0f})")

    # BR results
    br_data = phases.get("phase3_br", {})
    if br_data:
        failed = [k for k, v in br_data.items() if not v.get("pass", True)]
        if failed:
            lines.append(f"\n*BR failures:* {', '.join(failed)}")
        else:
            lines.append("\n✅ All BR checks passed")

    # PF
    if pf:
        lines.append(f"\n*Pareto Frontier:* {pf.get('frontier_candidates', [])}")
        if pf.get("regression"):
            lines.append(f"⚠️ *Regressions:* {pf['regression']}")

    # RW
    if rw:
        lines.append(f"\n*Real-world:* trust={rw.get('trust_score', 0):.0%}, "
                     f"escalation={rw.get('escalation_rate', 0):.0%}")

    return "\n".join(lines)


def build_telegram_message(args):
    """Build the message based on args."""
    if args.candidate:
        return report_detailed(args.candidate)

    entries = load_log(n=args.trend)
    if not entries:
        return "No evolution data yet. Run `python3 evaluate_v2.py <n> --stubs` first."

    if args.trend and args.trend > 1:
        return report_trend(entries, args.trend)

    return report_latest(entries)


def main():
    parser = argparse.ArgumentParser(description="Post evolution report to Telegram")
    parser.add_argument("--trend", type=int, help="Show trend for last N candidates")
    parser.add_argument("--candidate", type=int, help="Detailed report for one candidate")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending")
    args = parser.parse_args()

    msg = build_telegram_message(args)
    print(msg)
    print(f"\n{'='*50}")
    print(f"Message length: {len(msg)} chars")

    if args.dry_run:
        print("\n[DRY RUN] — not sending")
        return

    # Send via Hermes send_message tool
    # This will be called by the parent agent after we return
    # The parent agent reads this output and calls send_message
    print("\n[SEND] To send this report, the parent agent will call:")
    print("  send_message(platform='telegram', target='home', text=...)")
    print("\nSaving report to evolution_reports.json for record...")
    report_file = WORKSPACE / "evolution_reports.json"
    reports = []
    if report_file.exists():
        try:
            reports = json.loads(report_file.read_text())
        except:
            reports = []
    reports.append({
        "timestamp": datetime.now().isoformat(),
        "text": msg,
        "args": vars(args),
    })
    report_file.write_text(json.dumps(reports, indent=2))
    print(f"  Saved to {report_file}")


if __name__ == "__main__":
    main()
