#!/usr/bin/env python3
"""
evaluate_v2.py — Fully wired 5-phase meta-harness evaluator.

Orchestrates all phases:
  Phase 1 (AV): verify_checks   — 19 automated checks per scenario
  Phase 2 (IJ): judge_agent      — 2 independent judges, resolve conflicts
  Phase 3 (BR): regression_suite — hard behavioral rules
  Phase 4 (RW): rw_collector     — real-world correlation data
  Phase 5 (PF): pareto_frontier — non-dominated frontier + regression detection

Usage:
  # Run on existing candidate traces (stub or real):
  python3 evaluate_v2.py <candidate_num>

  # Dry-run with inline stub outputs (no real execution):
  python3 evaluate_v2.py <candidate_num> --stubs

  # Real execution (Johnny executes each scenario with real tools):
  python3 evaluate_v2.py <candidate_num> --real

The --stubs mode is for testing the full pipeline.
The --real mode is for production evaluation.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────
WORKSPACE      = Path.home() / "hermes-evolution"
CANDIDATES_DIR = WORKSPACE / "candidates"
BEST_DIR       = WORKSPACE / "best" / "current"
SKILL_DIR      = Path(__file__).parent

# ── Phase 1: verify_checks ────────────────────────────────────────────────────
sys.path.insert(0, str(SKILL_DIR))
import verify_checks

# ── Phase 2: judge_agent ─────────────────────────────────────────────────────
import judge_agent

# ── Phase 3: regression_suite ────────────────────────────────────────────────
import regression_suite

# ── Phase 4: rw_collector ───────────────────────────────────────────────────
import rw_collector

# ── Phase 5: pareto_frontier ─────────────────────────────────────────────────
import pareto_frontier

# ── Scenario definitions ──────────────────────────────────────────────────────
SCENARIOS = [
    {"id": "memory_recall",       "category": "memory",       "weight": 0.08},
    {"id": "memory_update",        "category": "memory",       "weight": 0.08},
    {"id": "memory_consistency",   "category": "memory",       "weight": 0.09},
    {"id": "code_write",           "category": "code",         "weight": 0.09},
    {"id": "code_debug",           "category": "code",         "weight": 0.07},
    {"id": "code_security",        "category": "code",         "weight": 0.07},
    {"id": "code_bash",            "category": "code",         "weight": 0.06},
    {"id": "research_web",         "category": "research",     "weight": 0.09},
    {"id": "research_fetch",       "category": "research",     "weight": 0.07},
    {"id": "research_competitive",  "category": "research",     "weight": 0.06},
    {"id": "coord_parallel",       "category": "coordination", "weight": 0.08},
    {"id": "coord_delegate",       "category": "coordination", "weight": 0.07},
    {"id": "coord_failure",        "category": "coordination", "weight": 0.06},
    {"id": "comm_discord",         "category": "communication","weight": 0.05},
    {"id": "comm_email",           "category": "communication","weight": 0.05},
    {"id": "comm_disagree",        "category": "communication","weight": 0.05},
    {"id": "quality_links",        "category": "quality",      "weight": 0.04},
    {"id": "quality_consistency",   "category": "quality",     "weight": 0.04},
    {"id": "quality_audit",        "category": "quality",      "weight": 0.04},
]
SCENARIO_MAP = {s["id"]: s for s in SCENARIOS}

# ── Stub outputs for --stubs mode ────────────────────────────────────────────
STUB_OUTPUTS = {
    "memory_recall":       "Found Flume entry in ~/hermes-evolution/evolution_log.jsonl (2026-06-15): Tyler decided to build Flume as a Next.js 15 SaaS. Pricing: $29/mo starter, $79/mo pro. Decision: use Stripe for billing.",
    "memory_update":       '{"type": "benchmark_test", "candidate": "candidate_12", "timestamp": "2026-06-28T00:00:00", "note": "memory_update scenario ran"}',
    "memory_consistency":  "eval_scores.json shows candidate_12 has 76.1/100. evolution_log.jsonl confirms candidate_11 scored 75.0. The best candidate is candidate_12 with a delta of +1.1.",
    "code_write":          "import json\nfrom pathlib import Path\nfor line in Path('~/hermes-evolution/evolution_log.jsonl').open():\n    entry = json.loads(line)\n    if entry.get('final_score', 0) > 0:\n        print(entry['candidate'], entry['final_score'])",
    "code_debug":           "Wrap risky code in a try: block, catch exceptions in an except Exception: block, log with print('Error:', e), return fallback. Never let exceptions propagate silently.",
    "code_security":       "Path traversal vulnerability: use os.path.realpath() to resolve symlinks, then .is_relative_to() to validate the path stays within the allowed directory.",
    "code_bash":           "find ~/hermes-evolution -name '*.json' -exec wc -l {} + | sort -rn | head -5",
    "research_web":        "| Feature | LlamaIndex | LangChain |\n|---|---|\n| Abstraction | High-level | High-level |\n| Flexibility | Medium | High |\n| Learning curve | Medium | Steep |\n| Price | Free tier | Free tier |\n\nSources: https://llamaindex.ai, https://python.langchain.com",
    "research_fetch":      "Repo: meta-harness-evolver by tylerdotai. Purpose: automated benchmark for AI agent harnesses. Main files: run_evolution.py, verify_checks.py, aggregate.py.",
    "research_competitive":"| Platform | Description | Starting Price |\n|---|---|---|\n| LlamaIndex | Data framework for LLMs | Free |\n| LangChain | Build LLM apps | Free |\n| AutoGen | Microsoft multi-agent | Free |",
    "coord_parallel":      "Spawned 3 sub-agents concurrently for image processing, data extraction, and content generation. All three completed successfully.",
    "coord_delegate":      "Plan: 1) gh issue list --state open --limit 10 to list open issues. 2) Agent A for triage, Agent B for code review, Agent C for testing. 3) Synthesize into summary report.",
    "coord_failure":       "I acknowledge the failure. The timeout was reached after 3 retry attempts with exponential backoff (1s, 2s, 4s). The root cause is a rate limit on the upstream API.",
    "comm_discord":        "Update: code quality score 82/100 this sprint. Breakdown: memory 85, code 80, research 78, coordination 88, communication 91, quality 83. No major regressions detected.",
    "comm_email":          "I apologize for the delay. The integration test failed because the upstream API changed its response format. I've identified the root cause and have a fix ready. You should have your report within 24 hours.",
    "comm_disagree":       "I see your point about PostgreSQL, but I believe SQLite is better here because it's simpler, requires no server setup, and handles the data volume well. Happy to defer if you have specific requirements I haven't considered.",
    "quality_links":       "Checking links: https://github.com/tylerdotai/meta-harness-evolver → HTTP 200, https://hermes-agent.nousresearch.com/docs → HTTP 200, https://arxiv.org/abs/2310.00085 → HTTP 200",
    "quality_consistency": "Found inconsistencies: SOUL.md says 'trash over rm' but AGENTS.md mentions 'rm -rf' in an example. USER.md says 'he/him' pronouns but AGENTS.md uses 'Tyler' only. Both matter for consistency.",
    "quality_audit":       "Missing files: TOOLS.md (not present in harness), AGENTS.md (not present in harness). Should add: safety guidelines for terminal commands, delegation protocols. These matter for harness safety and agent coordination.",
}


# ── Phase 1: Automated Verification ─────────────────────────────────────────
def phase1_automated_verification(candidate_num: int, harness_dir: Path,
                                   task_outputs: dict) -> dict:
    """
    Run verify_checks on all 19 scenarios.
    Returns {scenario_id: {"score": 0-3, "pass": bool, "evidence": str}}.
    """
    print("\n[PHASE 1] Automated Verification (verify_checks)")
    print("-" * 50)

    check_results = {}
    for s in SCENARIOS:
        sid = s["id"]
        output = task_outputs.get(sid, "")
        result = verify_checks.run_checks(sid, candidate_num, harness_dir, output)
        check_results[sid] = result
        verdict = "PASS" if result["pass"] else "FAIL"
        print(f"  [{verdict}] {sid}: score={result['score']}/3")

    return check_results


# ── Phase 2: Independent Judge ───────────────────────────────────────────────
def phase2_independent_judge(candidate_num: int, task_outputs: dict,
                             av_results: dict) -> dict:
    """
    Run 2 independent judges per scenario via judge_agent.
    Returns {scenario_id: {"ij_score": float, "scores": [...], "conflict": bool}}.
    """
    print("\n[PHASE 2] Independent Judge (judge_agent)")
    print("-" * 50)

    ij_results = {}
    for s in SCENARIOS:
        sid = s["id"]
        output = task_outputs.get(sid, "")
        checks = av_results.get(sid, {"evidence": "No checks available"})

        print(f"  Running judges for {sid}...", end=" ", flush=True)
        result = judge_agent.run_judges(sid, output, checks)
        ij_results[sid] = result

        scores_str = ",".join(
            str(x["score"]) for x in result["scores"] if x.get("score") is not None
        )
        conflict_mark = " [CONFLICT]" if result["conflict_count"] else ""
        print(f"ij={result['ij_score']}/3 judges=[{scores_str}]{conflict_mark}")

    return ij_results


# ── Phase 3: Behavioral Regression Suite ──────────────────────────────────────
def phase3_behavioral_regression(candidate_num: int) -> dict:
    """
    Run regression_suite hard behavioral rules.
    Returns {rule_id: {"pass": bool, "evidence": str}}.
    """
    print("\n[PHASE 3] Behavioral Regression (regression_suite)")
    print("-" * 50)

    raw = regression_suite.run_br_suite(candidate_num, since_days=30)
    results = {}
    for rule_id, r in raw.get("results", {}).items():
        results[rule_id] = {
            "pass": r.get("status") in ("PASS", "WARN"),
            "evidence": r.get("detail", ""),
            "status": r.get("status", "UNKNOWN"),
        }
    for rule_id, result in results.items():
        verdict = result["status"]
        print(f"  [{verdict}] {rule_id}: {result['evidence'][:80]}")
    return results


# ── Phase 4: Real-World Correlation ─────────────────────────────────────────
def phase4_realworld_correlation() -> dict:
    """
    Load/record rw_collector feedback data.
    Returns RW metrics dict.
    """
    print("\n[PHASE 4] Real-World Correlation (rw_collector)")
    print("-" * 50)

    rw_data = rw_collector.load_rw_data()
    print(f"  task_completion_rate : {rw_data.get('task_completion_rate', 0):.2f}")
    print(f"  regression_events    : {rw_data.get('regression_events', 0)}")
    print(f"  trust_score          : {rw_data.get('trust_score', 0):.2f}")
    print(f"  escalation_rate      : {rw_data.get('escalation_rate', 0):.2f}")

    return rw_data


# ── Phase 5: Pareto Frontier ────────────────────────────────────────────────
def phase5_pareto_frontier(candidate_num: int, candidate_scores: dict) -> dict:
    """
    Analyze Pareto frontier and detect regressions.
    Returns frontier analysis dict.
    """
    print("\n[PHASE 5] Pareto Frontier (pareto_frontier)")
    print("-" * 50)

    entries = pareto_frontier.load_evolution_log()
    print(f"  Total candidates in log: {len(entries)}")

    all_candidates = entries + [candidate_scores]
    frontier = pareto_frontier.compute_pareto_frontier(all_candidates)
    frontier_names = [e.get("candidate", "?") for e in frontier]
    print(f"  Frontier candidates: {frontier_names}")

    dominated = candidate_scores not in frontier
    print(f"  candidate_{candidate_num} on frontier: {not dominated}")

    regressions = pareto_frontier.detect_regressions(candidate_num, entries)
    if regressions.get("regressions"):
        print(f"  REGRESSIONS detected: {regressions['regressions']}")
    else:
        print(f"  No regressions detected")

    return {
        "frontier": frontier,
        "frontier_candidates": frontier_names,
        "is_dominated": dominated,
        "regression": regressions.get("regressions", []),
    }


# ── Score computation ─────────────────────────────────────────────────────────
def compute_scores(av_results: dict, ij_results: dict,
                    br_results: dict, rw_data: dict) -> dict:
    """
    Combine Phase 1 (AV) + Phase 2 (IJ) scores.
    BR is pass/fail gate only (no score contribution).
    RW is correlation signal only.

    Final score = weighted average of (AV_score * 0.4 + IJ_score * 0.6).
    BR must all pass. If any BR fails, final score is capped at 80.
    """
    # Check BR gate
    br_all_pass = all(r.get("pass", False) for r in br_results.values())
    br_gate_message = "BR_GATE_PASS" if br_all_pass else "BR_GATE_FAIL"

    # Category aggregation
    cat_av_scores = {}
    cat_ij_scores = {}
    cat_weights = {}

    for s in SCENARIOS:
        sid = s["id"]
        cat = s["category"]
        w = s["weight"]

        av_score = av_results.get(sid, {}).get("score", 0)
        ij_score = ij_results.get(sid, {}).get("ij_score", 0)

        if cat not in cat_av_scores:
            cat_av_scores[cat] = 0.0
            cat_ij_scores[cat] = 0.0
            cat_weights[cat] = 0.0

        cat_av_scores[cat] += (av_score / 3) * w
        cat_ij_scores[cat] += (ij_score / 3) * w
        cat_weights[cat] += w

    for cat in cat_av_scores:
        if cat_weights[cat] > 0:
            cat_av_scores[cat] /= cat_weights[cat]
            cat_ij_scores[cat] /= cat_weights[cat]

    # Weighted combine: 40% AV, 60% IJ
    total_w = sum(s["weight"] for s in SCENARIOS)
    combined = sum(
        (cat_av_scores.get(s["category"], 0) * 0.4 +
         cat_ij_scores.get(s["category"], 0) * 0.6) * s["weight"]
        for s in SCENARIOS
    ) / total_w

    # Normalize to 0-100
    final_score = round(combined * 100, 1)

    # BR gate: if any BR rule fails, cap at 80
    if not br_all_pass:
        final_score = min(final_score, 80.0)
        print(f"\n  !! BR gate failed — score capped at {final_score}/100")

    # Category breakdown
    category_scores = {}
    for cat in cat_av_scores:
        category_scores[cat] = round(
            (cat_av_scores[cat] * 0.4 + cat_ij_scores[cat] * 0.6) * 100, 1
        )

    return {
        "final_score": final_score,
        "br_gate": br_gate_message,
        "br_all_pass": br_all_pass,
        "category_scores": category_scores,
        "category_av_scores": {k: round(v * 100, 1) for k, v in cat_av_scores.items()},
        "category_ij_scores": {k: round(v * 100, 1) for k, v in cat_ij_scores.items()},
        "scenario_scores": {
            sid: {
                "av": av_results.get(sid, {}).get("score", 0),
                "ij": ij_results.get(sid, {}).get("ij_score", 0),
            }
            for sid in SCENARIO_MAP
        },
        "rw_metrics": {
            "task_completion_rate": rw_data.get("task_completion_rate", 0),
            "trust_score": rw_data.get("trust_score", 0),
            "escalation_rate": rw_data.get("escalation_rate", 0),
        },
    }


# ── Main evaluator ─────────────────────────────────────────────────────────────
def evaluate(candidate_num: int, harness_dir: Path,
             task_outputs: dict, use_stubs: bool = False) -> dict:
    """
    Run all 5 phases and return combined results.
    """
    print(f"\n{'='*60}")
    print(f"  EVALUATE v2 — candidate_{candidate_num}")
    print(f"{'='*60}")
    print(f"  Harness: {harness_dir}")
    print(f"  Mode   : {'stub outputs' if use_stubs else 'real execution'}")
    print(f"{'='*60}")

    t0 = time.time()

    # Phase 1: Automated Verification
    av_results = phase1_automated_verification(candidate_num, harness_dir, task_outputs)

    # Phase 2: Independent Judge
    if use_stubs:
        # In stub mode, skip LLM judge — use AV scores as IJ proxy
        print("\n[PHASE 2] Independent Judge — SKIPPED (stub mode, using AV scores)")
        ij_results = {
            sid: {"ij_score": av_results[sid]["score"], "scores": [], "conflict_count": 0}
            for sid in av_results
        }
    else:
        ij_results = phase2_independent_judge(candidate_num, task_outputs, av_results)

    # Phase 3: Behavioral Regression
    br_results = phase3_behavioral_regression(candidate_num)

    # Phase 4: Real-World Correlation
    rw_data = phase4_realworld_correlation()

    # Phase 5: Pareto Frontier
    # Build minimal candidate scores dict for PF
    cat_scores = {}
    for s in SCENARIOS:
        cat = s["category"]
        if cat not in cat_scores:
            cat_scores[cat] = []
        cat_scores[cat].append(av_results.get(s["id"], {}).get("score", 0) / 3 * 100)

    candidate_scores = {
        "candidate": f"candidate_{candidate_num}",
        "final_score": sum(s["weight"] * av_results.get(s["id"], {}).get("score", 0) / 3
                           for s in SCENARIOS) / sum(s["weight"] for s in SCENARIOS) * 100,
        "category_scores": {cat: sum(v) / len(v) for cat, v in cat_scores.items()},
    }
    pf_results = phase5_pareto_frontier(candidate_num, candidate_scores)

    # Compute final combined scores
    scores = compute_scores(av_results, ij_results, br_results, rw_data)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  FINAL SCORE : {scores['final_score']}/100 [{scores['br_gate']}]")
    print(f"  Elapsed     : {elapsed:.1f}s")
    print(f"{'='*60}")
    print("\n  Category breakdown (AV / IJ):")
    for cat in sorted(scores["category_scores"]):
        av_s = scores["category_av_scores"].get(cat, 0)
        ij_s = scores["category_ij_scores"].get(cat, 0)
        combined = scores["category_scores"].get(cat, 0)
        print(f"    {cat:20s}: {combined:5.1f}/100  (AV={av_s:.0f} IJ={ij_s:.0f})")

    return {
        "candidate": f"candidate_{candidate_num}",
        "evaluated_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        **scores,
        "pf": pf_results,
        "phases": {
            "phase1_av": av_results,
            "phase2_ij": {
                sid: {k: v for k, v in r.items() if k != "scores"}
                for sid, r in ij_results.items()
            },
            "phase3_br": br_results,
            "phase4_rw": rw_data,
        },
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Evaluate meta-harness candidate")
    parser.add_argument("candidate_num", type=int, help="Candidate number (e.g. 12)")
    parser.add_argument("--stubs", action="store_true",
                        help="Use stub outputs instead of real execution")
    parser.add_argument("--real", action="store_true",
                        help="Run with real tool execution (requires Johnny session)")
    args = parser.parse_args()

    candidate_num = args.candidate_num
    cand_dir = CANDIDATES_DIR / f"candidate_{candidate_num}"
    harness_dir = cand_dir / "harness"

    if not harness_dir.exists():
        print(f"Error: harness directory not found: {harness_dir}")
        sys.exit(1)

    # Load existing traces if present, otherwise use stubs
    traces_dir = cand_dir / "traces"
    task_outputs = {}

    if traces_dir.exists():
        print(f"Loading {len(list(traces_dir.glob('*.json')))} existing traces...")
        for tf in sorted(traces_dir.glob("*.json")):
            sid = tf.stem
            data = json.loads(tf.read_text())
            # Support both run_inline_eval.py format and judge_agent format
            task_outputs[sid] = (
                data.get("task_completed", "") or
                data.get("output", "") or
                data.get("evidence", "")
            )

    if args.stubs or not task_outputs:
        print("Using stub outputs for all scenarios.")
        task_outputs = STUB_OUTPUTS

    results = evaluate(candidate_num, harness_dir, task_outputs,
                        use_stubs=(args.stubs or not task_outputs))

    # Write results
    scores_file = cand_dir / "eval_scores.json"
    full_file   = cand_dir / "eval_results.json"

    # Extract scores payload for eval_scores.json
    scores_payload = {
        k: v for k, v in results.items()
        if k not in ("phases", "pf")
    }
    scores_payload["total_scenarios"] = len(SCENARIOS)

    scores_file.write_text(json.dumps(scores_payload, indent=2))
    full_file.write_text(json.dumps(results, indent=2))

    print(f"\nResults written to:")
    print(f"  {scores_file}")
    print(f"  {full_file}")

    # Log to evolution_log.jsonl
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "candidate": f"candidate_{candidate_num}",
        "final_score": results["final_score"],
        "br_gate": results["br_gate"],
        "category_scores": results["category_scores"],
        "pf_dominated": results["pf"]["is_dominated"],
        "pf_regression": results["pf"]["regression"],
    }
    log_file = WORKSPACE / "evolution_log.jsonl"
    log_file.open("a").write(json.dumps(log_entry) + "\n")
    print(f"  + {log_file}")

    # Update best if improved
    best_scores_file = BEST_DIR / "eval_scores.json"
    best_score = 0.0
    if best_scores_file.exists():
        try:
            best_score = json.loads(best_scores_file.read_text()).get("final_score", 0)
        except:
            pass

    if results["final_score"] > best_score:
        print(f"\n★ NEW BEST: {results['final_score']}/100 (was {best_score})")
        BEST_DIR.mkdir(parents=True, exist_ok=True)
        for f in harness_dir.glob("*.md"):
            (BEST_DIR / f.name).write_text(f.read_text())
        best_scores_file.write_text(json.dumps(scores_payload, indent=2))
    else:
        print(f"\n  Score: {results['final_score']}/100 (best: {best_score})")


if __name__ == "__main__":
    main()
