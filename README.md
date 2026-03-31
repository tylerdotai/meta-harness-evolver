# ⚡ Meta-Harness Evolver

**An OpenClaw agent skill that implements the Meta-Harness paper for autonomous self-improvement.**

> *"The harness around a fixed LLM can produce a 6× performance gap on the same benchmark."* — [Meta-Harness Paper](https://yoonholee.com/meta-harness/)

This skill runs a nightly outer-loop optimization for Hoss (or any OpenClaw agent) — reading prior execution traces, proposing targeted harness modifications, evaluating against a benchmark, and iterating.

---

## What Is This?

Meta-Harness is an outer-loop system that searches over **harness code** — the configuration files that wrap an LLM (prompts, context management, memory, tools). Unlike text optimizers that compress feedback to scalar scores, Meta-Harness gives a coding agent **full filesystem access** to all prior candidates' source, scores, and execution traces.

**Key insight:** The richest signal isn't a score — it's the **execution trace**. The proposer reads what actually happened, traces failures to root causes, and proposes targeted edits.

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  Proposer Agent ──(filesystem access)──► ~/hoss-evolution/
│         ▲                                           │
│         │                               propose harness
│         │                                           ▼
│         │                               Evaluate on benchmark
│         │                                           ▼
│  log ───┴── store: code + scores + traces ──► candidates/
└─────────────────────────────────────────────────────────┘
```

Each night at 3 AM CDT:

1. **Read** — Proposer reads all prior candidates from the evolution filesystem
2. **Propose** — Identifies failure patterns, proposes 1 targeted harness edit
3. **Validate** — Lightweight syntax/constraint check
4. **Evaluate** — Run benchmark (~20 diverse scenarios)
5. **Log** — Store candidate + scores + proposer reasoning traces
6. **Post** — Summary posted to Discord #research channel

---

## What Can Be Evolved

Hoss's "harness" = all configs wrapping the LLM brain:

| File | What It Controls |
|------|-----------------|
| `SOUL.md` | Core identity, personality, decision-making style |
| `IDENTITY.md` | Role, voice, tone, signature patterns |
| `AGENTS.md` | Sub-agent architecture, coordination protocol |
| `TOOLS.md` | Tool configurations, credentials, key hosts |
| `MEMORY.md` | Long-term memory structure |
| `HEARTBEAT.md` | Active hours, check priorities, alert thresholds |

---

## Installation

### Prerequisites

- OpenClaw installed and configured
- Python 3.8+
- `gh` CLI authenticated (`gh auth login`)

### Setup

```bash
# 1. Install the skill
git clone https://github.com/tylerdotai/meta-harness-evolver.git
cd meta-harness-evolver
openclaw skill install ./meta-harness-evolver

# 2. Create the evolution workspace
mkdir -p ~/hoss-evolution/{candidates,best/current,benchmark/scenarios,proposer/logs}
touch ~/hoss-evolution/evolution_log.jsonl

# 3. Seed iteration 0 (current Hoss configs)
mkdir -p ~/hoss-evolution/candidates/candidate_0/harness
cp ~/.openclaw/workspace/SOUL.md ~/hoss-evolution/candidates/candidate_0/harness/
cp ~/.openclaw/workspace/IDENTITY.md ~/hoss-evolution/candidates/candidate_0/harness/
cp ~/.openclaw/workspace/AGENTS.md ~/hoss-evolution/candidates/candidate_0/harness/
cp ~/.openclaw/workspace/TOOLS.md ~/hoss-evolution/candidates/candidate_0/harness/
cp ~/.openclaw/workspace/HEARTBEAT.md ~/hoss-evolution/candidates/candidate_0/harness/

# 4. Configure cron (3 AM CDT daily)
openclaw cron add \
  --name "meta-harness-evolution" \
  --schedule "0 3 * * *" \
  --timezone "America/Chicago" \
  --command "SKILL=meta-harness-evolver TASK=run_evolution openclaw run"
```

---

## Directory Structure

```
~/hoss-evolution/
├── candidates/              # All evaluated candidates
│   └── candidate_N/
│       ├── harness/          # Proposed config files
│       ├── eval_scores.json # Benchmark scores
│       ├── traces/           # Execution traces
│       └── proposer_reasoning.md
├── best/
│   └── current/              # Best harness found so far
│       ├── harness/
│       └── eval_scores.json
├── benchmark/
│   └── scenarios/            # ~20 diverse eval scenarios
└── evolution_log.jsonl       # Full run history
```

---

## Benchmark

The default benchmark has **20 scenarios** across 6 categories:

| Category | Weight | Examples |
|----------|--------|---------|
| Memory | 25% | Recall from logs, update MEMORY.md, synthesize across files |
| Code | 25% | Write scripts, debug, security review |
| Research | 20% | Web search + synthesize, fetch and summarize |
| Coordination | 15% | Spawn sub-agents, handle failures |
| Communication | 10% | Draft messages, handle pushback |
| Quality | 5% | Spot broken links, catch inconsistencies |

Each scenario is scored 0-3 (fail / partial / pass / excellent). Final score = weighted average × 100.

---

## The Proposer Agent

The proposer is a **coding-agent sub-agent** that:
- Reads all prior candidates via filesystem ops (grep, cat)
- Identifies patterns in success/failure
- Proposes **1 targeted edit** — not a wholesale rewrite
- Logs its reasoning trace for next iteration

Key constraint: **the skill text is the strongest lever**. Iterating on the proposer's role description had more effect than iteration count or population size.

---

## The Meta-Harness Paper

> *"Meta-Harness improves over Agentic Context Engineering (ACE) by 7.7 points while using 4× fewer context tokens."*

This skill implements the core ideas from:

**Meta-Harness: End-to-End Optimization of Model Harnesses**  
Yoonho Lee, Roshen Nair, Qizheng Zhang, Omar Khattab, Kangwook Lee, Chelsea Finn  
Stanford / MIT / KRAFTON  

- [Paper](https://yoonholee.com/meta-harness/paper.pdf)
- [Project Page](https://yoonholee.com/meta-harness/)
- [Artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact)

---

## Adapting for Your Agent

This skill is built for Hoss (an OpenClaw agent), but the framework is agent-agnostic:

1. **Update `references/harness-spec.md`** — define what files constitute YOUR agent's harness
2. **Update benchmark scenarios** — `scripts/evaluate.py` SCENARIOS list — test what matters for your agent
3. **Adjust weights** — if coordination matters more than code for your use case
4. **Update proposer prompt** — `scripts/run_evolution.py` proposer_task — describe your agent's context

---

## Example Discord Output

```
⚡ Meta-Harness Evolution — Nightly Report

Candidate: candidate_7
Score: 72.3/100 🔺 +3.1 vs best
Proposer: ✅ Success

What Changed:
  ~ SOUL.md (+12 lines)
  ~ HEARTBEAT.md (+3 lines)

Proposer's Reasoning:
  "candidate_5 and candidate_6 both failed on memory_2
   (updating MEMORY.md). Their HEARTBEAT.md didn't prioritize
   memory health checks. Added memory consistency validation."

Recent History:
  • candidate_6: 69.2
  • candidate_5: 68.1
  • candidate_4: 71.0
```

---

## References

- [Harness Spec](references/harness-spec.md) — What files make up an agent's harness
- [Benchmark Design](references/benchmark-design.md) — How to build/extend the eval suite
- [Evolution Logic](references/evolution-logic.md) — Algorithm details, Pareto frontier, proposer patterns

---

## Contributing

Issues and PRs welcome. If you adapt this for a different agent framework, we'd love to hear about it — open an issue or drop a note in the discussion.

---

## License

MIT — do what you want with it.
