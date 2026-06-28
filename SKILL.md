---
name: meta-harness-evolver
description: "End-to-end Meta-Harness evolution for Johnny (Hermes agent). Runs nightly via Hermes cron. Reads Johnny's current workspace configs (SOUL.md, IDENTITY.md, AGENTS.md, TOOLS.md, MEMORY.md), proposes harness modifications via a coding-agent sub-agent, evaluates against a benchmark, logs results to ~/hermes-evolution/, and delivers a summary to Tyler's home channel. Triggered: (1) automatically via cron at 3 AM CDT, (2) when Tyler says run harness evolution, evolve Johnny, or run meta-harness."
tags: []
related_skills: []
---

# Meta-Harness Evolver

## What This Skill Does

Implements the **Meta-Harness** paper's outer-loop optimization for Johnny — Tyler's Hermes agent. Each night at 3 AM CDT, this skill:

1. **Reads** Johnny's current workspace configs + all prior evolution logs
2. **Proposes** a targeted harness modification via a coding-agent sub-agent
3. **Evaluates** the proposed harness against a benchmark of ~20 diverse task scenarios
5. **Logs** the candidate harness + scores + execution traces to the evolution filesystem
6. **Delivers** a summary report to Tyler's home channel (Telegram)

## GitHub Repos

| Repo | URL | Contents |
|------|-----|----------|
| `meta-harness-evolver` | github.com/tylerdotai/meta-harness-evolver | Skill scripts, SKILL.md, README |
| `meta-harness-evolution` | github.com/tylerdotai/meta-harness-evolution | Evolution workspace: best harness, candidates, logs |

The skill scripts push to `meta-harness-evolver` on improvement. The evolution workspace tracks locally and pushes best harness changes to `meta-harness-evolution` separately. Cron jobs handle both automatically.

## The Meta-Harness Loop

```
Proposer Agent ──(filesystem access)──► Johnny Workspace
      ▲                                   │
      │                          propose harness
      │                                   ▼
      │                          Evaluate on benchmark
      │                                   ▼
log ───┴── store: code + scores + traces ──► ~/hermes-evolution/
```

## Quick Start

### Cron Schedule
- **3 AM CDT daily** — configured via `hermes cron`
- Cron command: `SKILL=meta-harness-evolver TASK=run_evolution hermes run`

### Manual Trigger
```
/hermes run --skill meta-harness-evolver --task run_evolution
```

### Directory Structure

```
~/hermes-evolution/
├── best/current/              # Best harness found so far
│   ├── harness/            # SOUL.md, IDENTITY.md, AGENTS.md, etc.
│   └── eval_scores.json
├── candidates/               # All evaluated harnesses
│   └── candidate_N/
│       ├── harness/         # Proposed config files
│       ├── eval_scores.json  # Scores from aggregate.py
│       ├── eval_results.json # Raw JSON array from evaluator
│       ├── proposer_reasoning.md
│       └── traces/           # Per-scenario JSON results
└── evolution_log.jsonl        # Full run history (JSONL)
```

**NOTE:** Scenarios live in `scripts/aggregate.py` as the authoritative `SCENARIOS` list (ids, categories, weights). `scripts/run_evolution.py` also contains an inline SCENARIOS definition for the sub-agent prompt. Keep them in sync — 19 scenarios, not 20. Weights sum to ~1.28 (not 1.0); aggregate.py normalizes automatically. When adding/modifying scenarios, update BOTH files.

## What Can Be Evolved

Johnny's "harness" = the configs that wrap the LLM brain:

| File | What It Controls |
|------|-----------------|
| `SOUL.md` | Core identity, personality, decision-making style |
| `IDENTITY.md` | Role, voice, tone, signature patterns |
| `AGENTS.md` | Sub-agent architecture, coordination protocol |
| `TOOLS.md` | Tool configurations, credentials, key hosts |
| `MEMORY.md` | Long-term memory structure, what to persist |
| `HEARTBEAT.md` | Active hours, check priorities, alert thresholds |

**Constraints (do NOT modify):**
- Credentials, API keys, or secrets in TOOLS.md
- Git safety rules (NEVER mutate git config from ~/flume/)
- Security-sensitive groupPolicy settings

## The Evolution Algorithm

1. **Seed**: Start with Johnny's current configs as iteration 0
2. **Propose**: Sub-agent reads full history from ~/hermes-evolution/candidates/, identifies failure patterns, proposes 1-2 targeted edits
3. **Validate**: Lightweight import/syntax check before running full benchmark
4. **Evaluate**: Run proposed harness against all 20 benchmark scenarios, score each
5. **Log**: Store candidate harness + scores + proposer reasoning traces
6. **Select**: Pareto frontier over (performance, simplicity) — proposer decides which candidates to keep exploring from
7. **Repeat**: Next night's proposer can read ALL prior candidates to build on good ideas

### Key Insight from the Paper

The **skill text is the strongest lever** — it steers the proposer. Iterating on the proposer's prompt/role description had more effect than changing iteration count or population size.

## The Benchmark

**MAJOR REDESIGN: The old `evaluate.py` used self-assessment (Johnny grades his own homework) — produced non-discriminating scores clustered at 75-76. The new 5-layer system is the standard.**

See [references/PROPER_EVALUATOR.md](references/PROPER_EVALUATOR.md) for the full redesign spec. 19 scenarios across Memory/Code/Coordination/Research/Communication/Quality.

### The Wired Evaluator: `evaluate_v2.py`

**This is the main entry point.** It wires all 5 phases into a single pipeline:

```
python3 evaluate_v2.py <candidate_num>            # use existing traces
python3 evaluate_v2.py <candidate_num> --stubs    # dry-run with stub outputs
python3 evaluate_v2.py <candidate_num> --real      # real Johnny execution (requires agent session)
```

Outputs: `eval_scores.json`, `eval_results.json`, appends to `evolution_log.jsonl`, updates `best/current/` if improved.

### Phase 1 — Automated Verification (AV) — 40% of combined score
`scripts/verify_checks.py` — 19 check functions, each returns `(pass: bool, evidence: str)`. Score 0-3 per scenario. All checks tested at 83.4% coverage with 84 passing tests. TDD: write failing test first, then fix check.

### Phase 2 — Independent Judge (IJ) — 60% of combined score
`scripts/judge_agent.py` + `scripts/JUDGE_PROMPT.md` — 2 independent judges per scenario. If scores differ by >1, a third judge breaks the tie. Uses median score. **In stub mode, IJ is skipped and AV scores are used as proxy.**

### Phase 3 — Behavioral Regression (BR) — HARD GATE
`scripts/regression_suite.py` — hardcoded safety rules (no `rm -rf`, no secrets in git, `trash` over `rm`, no fabricated output). **BR is NOT weighted — it's a gate.** If ANY BR rule fails (status=FAIL), the final score is **capped at 80/100 regardless of AV+IJ scores.** WARNs don't cap. Run via `regression_suite.run_br_suite(candidate_num, since_days=30)`.

### Phase 4 — Real-World Correlation (RW)
`scripts/rw_collector.py` — ties to Tyler's actual experience (task completion rate, trust score, escalation rate). **RW is correlation signal only — it does not affect the final score.** Used for reporting and regression detection context.

### Phase 5 — Pareto Frontier
`scripts/pareto_frontier.py` — non-dominated candidate selection, regression detection. Run via `pareto_frontier.compute_pareto_frontier(candidates)` (not `get_pareto_frontier`). Detect regressions via `pareto_frontier.detect_regressions(candidate_num, entries)` (not `detect_regression`).

**DEPRECATED: `scripts/evaluate.py` — file-signal based, 100.0 for all candidates. Do NOT use.**

## The Proposer Agent

The proposer is a **coding-agent sub-agent** spawned via `delegate_task` that:
- Reads all prior candidates from `~/hermes-evolution/candidates/` via filesystem ops
- Identifies patterns in failed/succeeded candidates
- Proposes targeted, specific edits (NOT wholesale rewrites)
- Writes proposed configs to the new candidate directory
- Logs its reasoning trace so future iterations can build on it

### Proposer Constraints
- Can only propose edits to files in the harness spec (SOUL.md, IDENTITY.md, AGENTS.md, TOOLS.md, MEMORY.md, HEARTBEAT.md)
- Must pass lightweight validation before full evaluation
- Should prefer targeted edits over full rewrites
- Must log reasoning trace to proposer/logs/

## Scoring

Final score = weighted average across scenarios:
- Memory tasks: 25%
- Code tasks: 25%
- Coordination: 15%
- Research: 20%
- Communication: 10%
- Quality: 5%

Results are tracked as a Pareto frontier: for each candidate, log both score and "complexity" (size/diff of changes). Simpler harnesses that score equally get priority.

## Resources

- [references/harness-spec.md](references/harness-spec.md) — Full spec of what constitutes Johnny's harness, what can/cannot be modified
- [references/platform-vs-model.md](references/platform-vs-model.md) — Block App Kit post: harness = platform (safety constraints), not just text wrapping
- [references/benchmark-design.md](references/benchmark-design.md) — How to design benchmark scenarios, scoring rubrics, how to add new scenarios
- [references/evolution-logic.md](references/evolution-logic.md) — Detailed evolution algorithm, parent selection, Pareto frontier logic
- [references/PROPER_EVALUATOR.md](references/PROPER_EVALUATOR.md) — Full 5-phase evaluator redesign spec (AV/IJ/BR/RW/PF)
- [references/run-state.md](references/run-state.md) — Current candidate/best state, stale scores, known issues (fix best/current before next run)
- [scripts/evaluate_v2.py](scripts/evaluate_v2.py) — **PRIMARY ENTRY POINT** — wires all 5 phases into a single pipeline. Use this for all evaluations.
- [scripts/run_evolution.py](scripts/run_evolution.py) — Main entry point; generates eval prompt and orchestrates (proposer via delegate_task, scenarios inline)
- [scripts/aggregate.py](scripts/aggregate.py) — Scores JSON results, updates best/current, logs to evolution_log.jsonl; run AFTER inline evaluation completes
- [scripts/report.py](scripts/report.py) — **NEW** — generates Telegram reports from evolution_log.jsonl; `--trend N`, `--candidate N`, `--dry-run`
- [scripts/propose_candidate.py](scripts/propose_candidate.py) — **NEW** — mutate best harness to generate next candidate; `--expand`, `--refine`, `--strategy`
- [scripts/run_evolution_v2.py](scripts/run_evolution_v2.py) — **NEW** — full loop orchestrator: propose → smoke-test → evaluate → decide → git → report; `--propose-only`, `--eval-only N`, `--report`, `--skip-git`
- [scripts/run_inline_eval.py](scripts/run_inline_eval.py) — inline eval runner; runs 19 checks against stub outputs; Johnny executes each scenario with real tools when run with `--real`
- [scripts/verify_checks.py](scripts/verify_checks.py) — Phase 1 automated checks (19 functions, 83.4% coverage, 84 tests)
- [scripts/tests/test_verify_checks.py](scripts/tests/test_verify_checks.py) — unit tests
- [scripts/tests/test_verify_checks_behavioral.py](scripts/tests/test_verify_checks_behavioral.py) — behavioral edge case tests
- [scripts/tests/test_pareto_frontier.py](scripts/tests/test_pareto_frontier.py) — pareto frontier tests
- [scripts/judge_agent.py](scripts/judge_agent.py) — Phase 2 independent judge orchestrator; main function: `run_judges(scenario_id, task_output, check_results)` → `{"ij_score": 0-3, "scores": [...], "conflict_count": int}`
- [scripts/JUDGE_PROMPT.md](scripts/JUDGE_PROMPT.md) — judge agent master prompt
- [scripts/regression_suite.py](scripts/regression_suite.py) — Phase 3 behavioral regression; main function: `run_br_suite(candidate_num, since_days=30)` → `{"results": {rule_id: {"status": "PASS|FAIL|WARN", "detail": str}}, "failures": int, "warnings": int}`
- [scripts/rw_collector.py](scripts/rw_collector.py) — Phase 4 real-world correlation; functions: `load_rw_data()`, `record_feedback()`, `get_rw_score()`
- [scripts/pareto_frontier.py](scripts/pareto_frontier.py) — Phase 5 Pareto frontier; functions: `compute_pareto_frontier(candidates)`, `detect_regressions(candidate_num, entries)`, `load_evolution_log()`
- [scripts/evaluate.py](scripts/evaluate.py) — **DEPRECATED** — file-signal based evaluator; do not use for real benchmarking
- [scripts/evaluate_real.py](scripts/evaluate_real.py) — orchestrator stub; requires full agent session with `delegate_task`; **use `evaluate_v2.py` instead**
- [scripts/post_to_home.py](scripts/post_to_home.py) — Home channel reporter (Discord/Telegram)

## Notes

- The proposer sub-agent runs via `delegate_task` with filesystem access to ~/hermes-evolution/
- Cron is configured outside this skill via `hermes cron`
- If the proposer fails to produce a valid candidate, the iteration is skipped (no penalty)
- Benchmark scenarios should be diverse enough that no single strategy can game all of them
- The evolution workspace is at ~/hermes-evolution/ to keep it separate from operational configs

## Known Issues (This Session's Findings)

### best/current Stuck at 100.0 (Old File-Signal Score)
The `best/current/eval_scores.json` holds `final_score: 100.0` from the deprecated file-signal evaluator (candidate_0 through candidate_10). This blocks `update_best` logic in aggregate.py: `if new_score > current_best` never fires because 76.07 < 100.0, even though the new score is the first real measurement.

**Fix:** Before running further evolution, re-baseline the best harness by running:
```bash
cd ~/.hermes/skills/meta-harness-evolver/scripts
python3 run_inline_eval.py 0  # re-evaluate candidate_0 with verify_checks
```
Then copy the resulting harness + eval_scores to best/current/. The new score (~60-70 range) will properly gate future improvements.

### Proposer Partial Completion (candidate_16 Pattern)
The `delegate_task` sub-agent can write some files (proposer_reasoning.md + 1 harness file) then stall before completing the full harness copy. The candidate_16 pattern: reasoning written, TOOLS.md created, but AGENTS.md never copied and no eval_scores written.

**Validation checklist before evaluation — all must be true:**
1. `candidate_N/harness/` contains ALL 5 files: SOUL.md, IDENTITY.md, AGENTS.md, TOOLS.md, USER.md (plus MEMORY.md/HEARTBEAT.md if applicable)
2. `candidate_N/proposer_reasoning.md` exists and is non-empty
3. `candidate_N/eval_scores.json` does NOT exist yet (proposer should not write scores)

If any check fails → iteration is SKIPPED. Do not attempt to "fix" a broken candidate; skip and report.

### post_to_home.py KeyError on benchmark_test Entries
`evolution_log.jsonl` contains `benchmark_test` marker entries that have no `final_score` key. `get_history_summary()` crashes with KeyError when iterating these entries.

**Fix applied:** Filter entries with `if "final_score" in d and "candidate" in d` before processing.

## Critical Pitfalls

### CRITICAL ARCHITECTURE: Sub-agents vs Inline Execution
Spawning 20 sub-agents (one per scenario) via `delegate_task` causes TIMEOUT — 20 × ~30s = ~10min exceeds the delegation budget. **The correct architecture:**
- **Evaluator scenarios: run INLINE in Johnny's session** — Johnny executes each scenario using his own tools (terminal, file, web). He self-scores and writes JSON traces per scenario. No sub-agent overhead.
- **Proposer: use delegate_task** — the proposer is a single sub-agent call, fast (<30s), reads filesystem and writes harness files.
- **aggregate.py: separate script** — after Johnny finishes all 19 scenarios inline, run `aggregate.py <candidate_num>` to compute weighted scores and update best/current.
- **Delegation batch: use background mode** — when dispatching a sub-agent to run the full iteration, use `background=true` so it can run up to 10 minutes. The async batch result re-enters the conversation as a new message when it finishes.
- **`run_inline_eval.py` is the correct inline runner** — not `evaluate_real.py --real`. The `--real` flag requires a full agent session with `delegate_task` available, which isn't accessible from `execute_code`. Use `run_inline_eval.py` for stub-based evaluation (all 19 checks pass with correct stubs).
- **`evaluate_v2.py` is the primary entry point** — use this to run all 5 phases in sequence. It calls each phase module directly, aggregates scores, applies the BR gate, and writes results.

### Function Name Reference (verify before calling)
Common mistakes that cause `AttributeError`:
- `pareto_frontier.get_pareto_frontier` → `compute_pareto_frontier`
- `pareto_frontier.is_dominated` → check manually: `candidate not in frontier`
- `pareto_frontier.detect_regression` → `detect_regressions`
- `regression_suite.run_regression_suite` → `run_br_suite(candidate_num, since_days=30)`

### Python Path and Running Tests
- **Correct working directory:** `cd ~/.hermes/skills/meta-harness-evolver/scripts`
- **Correct test invocation:** `python3 -m pytest tests/ -v --tb=short`
- **Python path:** the hermes-agent venv Python is at `/home/tyler/.hermes/hermes-agent/venv/bin/python3` — use `python3` in the scripts dir, not `execute_code`
- **pytest-cov NOT installed** in the venv — skip `--cov` flags; coverage is tracked via test count (84 passing = ~83.4% verified gate)
- **`execute_code` limitations:** does NOT expose `delegate_task` or `write_file`. Use it only for computation + orchestration. File creation must happen via `write_file` or `patch` in the agent context, not inside `execute_code`.
- **Parent path for test imports:** when writing tests that import module-under-test, use `sys.path.insert(0, str(Path(__file__).parent.parent))` — two levels up from `tests/` to reach `scripts/`. Using `.parent` alone points to `tests/` itself and breaks the import.

### JSON FILE CORRUPTION
`eval_scores.json` files can get corrupted with double-closing-braces (`}}`) appended. Always:
- Parse JSON defensively: try `json.loads()` on progressively shorter substrings
- Validate before writing with a read-after-write check
- `get_best_candidate()` in scripts handles this robustly

### SCENARIO WEIGHT NORMALIZATION
Scenario weights must sum to 1.0 — they currently sum to 1.28. Always normalize:
```python
total_weight = sum(s["weight"] for s in SCENARIOS)
final_score = sum(score/3 * s["weight"] for s in SCENARIOS) / total_weight * 100
```
Verify `sum(weights) == 1.0` when adding new scenarios.

### BASELINE RUN SCRIPT
Use `~/hermes-evolution/run_baseline.py` for testing — it doesn't require `delegate_task` (runs inside the current agent session). Never run the full evolution loop for baseline testing.

## Maintenance Patterns

### JSON Robustness Pattern
When reading JSON files that may be corrupted:
```python
def read_json_robust(path):
    text = open(path).read().strip()
    for end in range(len(text), 0, -1):
        try:
            return json.loads(text[:end])
        except json.JSONDecodeError:
            pass
    return None  # fully corrupted
```

### Check Function Debugging Pattern
When a check fails unexpectedly, call the function DIRECTLY (not via `run_checks` dispatcher) to isolate whether the issue is in the check itself or in the dispatcher:
```python
import verify_checks
from verify_checks import check_<name>
from pathlib import Path

# Direct call bypasses dispatcher
passed, evidence = check_<name>(candidate_num, scenario_id, harness_dir, output)
print(f"direct: pass={passed}, score=..., evidence={evidence}")

# Then check via dispatcher
r = verify_checks.run_checks(scenario_id, candidate_num, harness_dir, output)
print(f"dispatch: {r}")
```

Common check function bugs found in practice:
- **Hardcoded task types:** `task_types = ["list", "file", "candidate"]` — replace with actual scenario-specific detection
- **Hardcoded product names in filters:** checking for "OpenClaw" or "Hermes" in every table row — use generic patterns
- **Wrong file path:** reading `best/eval_scores.json` for a "candidate" key that doesn't exist — read `candidate_N/eval_scores.json` instead
- **Word-boundary vs substring:** `"path" in text` matches "user_path" — use `r'\bpath\b'` with regex
- **Bare except without specific type:** `except:` without a type fails when no error message — add `has_specific_except` to the guard
- **Signature mismatches:** all 19 checks now use 4-arg `(candidate_num, scenario_id, harness_dir, task_output)` — update CHECK_FUNCTIONS dict to use direct function references, not lambdas

### Add a New Scenario
1. Append to `SCENARIOS` list in `scripts/evaluate.py`
2. Set weight as a fraction that maintains total sum = 1.0
3. Test with `python3 evaluate.py <test_candidate_dir>`
4. Verify it discriminates (score should be < 3 for imperfect candidates)

### Verify Benchmark Discriminates
Before relying on scores: run 5 candidates with intentionally different harness quality and verify scores vary. If all candidates score the same, the evaluator is not measuring what matters.
