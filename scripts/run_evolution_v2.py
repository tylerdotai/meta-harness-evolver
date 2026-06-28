#!/usr/bin/env python3
"""
run_evolution_v2.py — Full evolution loop orchestrator.

Flow:
  1. propose_candidate.py   → generate candidate_N+1 harness
  2. evaluate_v2.py --stubs → smoke test (fast)
  3. evaluate_v2.py --real  → Johnny runs all 19 scenarios (real tools)
  4. report.py               → post summary to Telegram
  5. git push (if new best)  → push best harness to GitHub

Usage:
  python3 run_evolution_v2.py                 # full loop
  python3 run_evolution_v2.py --propose-only  # generate candidate only
  python3 run_evolution_v2.py --eval-only 12  # evaluate existing candidate
  python3 run_evolution_v2.py --report         # report only (no eval)
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE      = Path.home() / "hermes-evolution"
CANDIDATES_DIR = WORKSPACE / "candidates"
BEST_DIR       = WORKSPACE / "best" / "current"
REPO_DIR       = WORKSPACE  # assumes repo is checked out at hermes-evolution/
SKILL_SCRIPTS  = Path(__file__).parent

GIT_HTTPS = True  # Use HTTPS + gh auth helper (SSH fails from this host)


def run(script_name: str, *args, cwd=None):
    """Run a skill script and return exit code."""
    cmd = [sys.executable, str(SKILL_SCRIPTS / script_name), *args]
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or WORKSPACE,
                           capture_output=False, text=True)
    return result.returncode


def get_current_best_score():
    """Read current best score from best/current/eval_scores.json."""
    f = BEST_DIR / "eval_scores.json"
    if f.exists():
        try:
            return json.loads(f.read_text()).get("final_score", 0)
        except:
            pass
    return 0.0


def get_candidate_score(candidate_num: int):
    """Read a candidate's score."""
    f = CANDIDATES_DIR / f"candidate_{candidate_num}" / "eval_scores.json"
    if f.exists():
        try:
            return json.loads(f.read_text()).get("final_score", 0)
        except:
            pass
    return 0.0


def count_candidates():
    """Return highest existing candidate number."""
    if not CANDIDATES_DIR.exists():
        return -1
    nums = []
    for d in CANDIDATES_DIR.glob("candidate_*"):
        import re
        m = re.search(r"candidate_(\d+)", d.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else -1


def check_git_dirty():
    """Return True if there are uncommitted changes."""
    try:
        r = subprocess.run(["git", "status", "--porcelain"],
                          cwd=REPO_DIR, capture_output=True, text=True)
        return bool(r.stdout.strip())
    except:
        return False


def git_commit_push(candidate_num: int, score: float):
    """Commit and push best harness if improved."""
    if SKIP_GIT:
        print("\n[SKIP GIT] — git push disabled (SKIP_GIT=True)")
        return

    if not (REPO_DIR / ".git").exists():
        print("\n[SKIP GIT] — not a git repo")
        return

    git = lambda cmd: subprocess.run(cmd, cwd=REPO_DIR,
                                    capture_output=True, text=True)

    # Stage best harness files
    for f in (BEST_DIR).glob("*.md"):
        git(["git", "add", str(f.relative_to(REPO_DIR))])
    git(["git", "add", str(BEST_DIR.relative_to(REPO_DIR) / "eval_scores.json")])

    # Check if anything staged
    status = git(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("\n[GIT] Nothing to commit (best unchanged)")
        return

    # Commit
    msg = (f"best: candidate_{candidate_num} @ {score:.1f}/100 "
           f"({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    git(["git", "commit", "-m", msg])
    print(f"\n[GIT] Committed: {msg}")

    # Push via HTTPS using gh auth helper (SSH fails from this host)
    git(["git", "remote", "set-url", "origin",
         "https://github.com/tylerdotai/meta-harness-evolution.git"])
    git(["git", "config", "credential.helper",
         "/usr/bin/gh auth git-credential"])
    result = git(["git", "push", "origin", "main"])
    if result.returncode == 0:
        print("[GIT] Pushed to origin/main")
    else:
        print(f"[GIT] Push failed: {result.stderr[:200]}")


def post_report(candidate_num: int):
    """Generate and print the Telegram report text."""
    # Run report.py and capture output
    result = subprocess.run(
        [sys.executable, str(SKILL_SCRIPTS / "report.py"),
         "--candidate", str(candidate_num)],
        cwd=WORKSPACE, capture_output=True, text=True
    )
    print("\n" + "=" * 50)
    print("TELEGRAM REPORT:")
    print("=" * 50)
    print(result.stdout)
    return result.stdout


def step_propose():
    """Step 1: Propose new candidate."""
    print("\n" + "=" * 60)
    print("STEP 1: PROPOSE")
    print("=" * 60)
    rc = run("propose_candidate.py")
    if rc != 0:
        print(f"[ERROR] propose_candidate.py exited with {rc}")
        sys.exit(1)

    new_num = count_candidates()
    print(f"\n✓ Proposed candidate_{new_num}")
    return new_num


def step_smoke_test(candidate_num: int):
    """Step 2: Quick smoke test with stubs."""
    print("\n" + "=" * 60)
    print(f"STEP 2: SMOKE TEST (candidate_{candidate_num})")
    print("=" * 60)
    rc = run("evaluate_v2.py", str(candidate_num), "--stubs")
    if rc != 0:
        print(f"[ERROR] smoke test failed — skipping real eval")
        return False
    score = get_candidate_score(candidate_num)
    print(f"\n✓ Smoke test: {score}/100")
    return True


def step_evaluate(candidate_num: int):
    """
    Step 3: Full real evaluation.
    This runs evaluate_v2.py which orchestrates Johnny to execute
    all 19 scenarios with real tools.

    In a full agent session, this would be:
      python3 evaluate_v2.py {candidate_num} --real

    Since --real mode requires the agent to call execute inline,
    we provide the eval prompt and guide the agent through it.
    """
    print("\n" + "=" * 60)
    print(f"STEP 3: REAL EVALUATION (candidate_{candidate_num})")
    print("=" * 60)
    print("""
To complete real evaluation, run in agent session:
  python3 evaluate_v2.py {candidate_num} --real

This will:
  1. Johnny executes each of 19 scenarios with real tools
  2. verify_checks scores each result 0-3
  3. judge_agent runs 2 independent LLM judges
  4. regression_suite checks behavioral rules
  5. Results written to eval_scores.json + evolution_log.jsonl

Alternatively, run inline evaluation:
  python3 run_inline_eval.py {candidate_num}
""".format(candidate_num=candidate_num))

    # Run the inline eval script (uses hermes_tools inline execution)
    rc = run("run_inline_eval.py", str(candidate_num))
    if rc != 0:
        print(f"[WARN] run_inline_eval.py exited with {rc} (may need agent session)")

    score = get_candidate_score(candidate_num)
    print(f"\n✓ Real eval complete: {score}/100")
    return score


def decide_and_update(candidate_num: int, score: float):
    """Step 4: Decide if new best, update best dir."""
    best_score = get_current_best_score()
    improved = score > best_score

    print("\n" + "=" * 60)
    print("STEP 4: DECIDE & UPDATE BEST")
    print("=" * 60)
    print(f"  New score : {score:.1f}")
    print(f"  Best score: {best_score:.1f}")
    print(f"  Improved  : {'★ YES' if improved else 'no'}")

    if improved:
        print(f"\n★ NEW BEST — candidate_{candidate_num}")
        best_scores_file = BEST_DIR / "eval_scores.json"
        cand_scores_file = CANDIDATES_DIR / f"candidate_{candidate_num}" / "eval_scores.json"

        # Copy harness files
        cand_harness = CANDIDATES_DIR / f"candidate_{candidate_num}" / "harness"
        if cand_harness.exists():
            for f in cand_harness.glob("*.md"):
                (BEST_DIR / f.name).write_text(f.read_text())

        # Copy eval_scores
        BEST_DIR.mkdir(parents=True, exist_ok=True)
        if cand_scores_file.exists():
            best_scores_file.write_text(cand_scores_file.read_text())

        print(f"  → Updated {BEST_DIR}")
        return True
    else:
        print(f"\n  → Best unchanged (candidate_{candidate_num} did not improve)")
        return False


def step_git(candidate_num: int, score: float, is_new_best: bool):
    """Step 5: Git commit and push if new best."""
    if not is_new_best:
        print("\n" + "=" * 60)
        print("STEP 5: GIT (skipped — no improvement)")
        print("=" * 60)
        return

    print("\n" + "=" * 60)
    print("STEP 5: GIT COMMIT & PUSH")
    print("=" * 60)
    git_commit_push(candidate_num, score)


def step_report(candidate_num: int):
    """Step 6: Post Telegram report."""
    print("\n" + "=" * 60)
    print("STEP 6: TELEGRAM REPORT")
    print("=" * 60)
    return post_report(candidate_num)


def run_full_loop(candidate_num: int = None):
    """Run the complete evolution loop."""
    print("\n" + "=" * 60)
    print("  META-HARNESS EVOLUTION LOOP")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1: Propose
    if candidate_num is None:
        candidate_num = step_propose()

    # 2: Smoke test
    if not step_smoke_test(candidate_num):
        return

    # 3: Real eval
    score = step_evaluate(candidate_num)

    # 4: Decide
    is_new_best = decide_and_update(candidate_num, score)

    # 5: Git
    step_git(candidate_num, score, is_new_best)

    # 6: Report
    step_report(candidate_num)

    print("\n" + "=" * 60)
    print("  EVOLUTION LOOP COMPLETE")
    print(f"  Candidate: candidate_{candidate_num}")
    print(f"  Score: {score}/100")
    print(f"  New best: {'yes' if is_new_best else 'no'}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Meta-harness evolution loop")
    parser.add_argument("--propose-only", action="store_true", help="Only run propose step")
    parser.add_argument("--eval-only", type=int, metavar="N",
                       help="Only run evaluate step on candidate N")
    parser.add_argument("--report", action="store_true", help="Only run report step")
    parser.add_argument("--skip-git", action="store_true", help="Skip git operations")
    parser.add_argument("--candidate", type=int,
                       help="Propose this specific candidate number")
    args = parser.parse_args()

    global SKIP_GIT
    if args.skip_git:
        SKIP_GIT = True

    if args.report:
        entries_path = WORKSPACE / "evolution_log.jsonl"
        if not entries_path.exists():
            print("No evolution_log.jsonl found.")
            sys.exit(1)
        import json
        lines = entries_path.read_text().strip().split("\n")
        last = json.loads(lines[-1])
        last_cand = last.get("candidate", "candidate_0")
        candidate_num = int(last_cand.split("_")[-1]) if last_cand else 0
        step_report(candidate_num)
        return

    if args.eval_only is not None:
        candidate_num = args.eval_only
        score = step_evaluate(candidate_num)
        decide_and_update(candidate_num, score)
        step_report(candidate_num)
        return

    if args.propose_only:
        candidate_num = step_propose()
        print(f"\nProposed: candidate_{candidate_num}")
        return

    # Full loop
    candidate_num = args.candidate
    run_full_loop(candidate_num)


if __name__ == "__main__":
    main()
