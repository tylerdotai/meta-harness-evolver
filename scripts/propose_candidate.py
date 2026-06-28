#!/usr/bin/env python3
"""
propose_candidate.py — Generate candidate_N+1 harness by mutating best.

Mutation strategies:
  1. Expand: Add a missing section (e.g., AGENTS.md if not present)
  2. Refine: Improve a weak section (low word count or low signal)
  3. Clarify: Rewrite a confusing directive
  4. Strengthen: Add more forceful/Decisive language to weak sections

Usage:
  python3 propose_candidate.py              # auto-pick best strategy
  python3 propose_candidate.py --expand    # force expand missing files
  python3 propose_candidate.py --refine    # force refine existing files
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE      = Path.home() / "hermes-evolution"
CANDIDATES_DIR = WORKSPACE / "candidates"
BEST_DIR       = WORKSPACE / "best" / "current"


def load_best_harness():
    """Load all .md files from best/current."""
    files = {}
    if BEST_DIR.exists():
        for f in sorted(BEST_DIR.glob("*.md")):
            files[f.name] = f.read_text()
    return files


def count_candidates():
    """Return next candidate number."""
    existing = sorted(CANDIDATES_DIR.glob("candidate_*"))
    if not existing:
        return 0
    nums = []
    for d in existing:
        m = re.search(r"candidate_(\d+)", d.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def list_missing_files(harness_files):
    """Return list of standard harness files NOT in harness."""
    STANDARD = ["SOUL.md", "IDENTITY.md", "USER.md", "TOOLS.md", "AGENTS.md"]
    missing = [f for f in STANDARD if f not in harness_files]
    return missing


def analyze_weak_sections(harness_files):
    """Return sections ranked by weakness (word count / signal strength)."""
    signals = {
        "SOUL.md": ["boundary", "quality", "standard", "decisive", "direct", "texas"],
        "IDENTITY.md": ["tyler", "voice", "tone", "style", "direct"],
        "USER.md": ["pref", "work", "project", "convention"],
        "TOOLS.md": ["terminal", "file", "web", "search", "delegate"],
        "AGENTS.md": ["sub-agent", "spawn", "delegate", "coordination"],
    }
    weaknesses = []
    for fname, content in harness_files.items():
        words = len(content.split())
        signal_words = sum(1 for s in signals.get(fname, []) if s in content.lower())
        weaknesses.append((fname, words, signal_words, content))
    # Sort by lowest signal density
    weaknesses.sort(key=lambda x: (x[2], x[1]))
    return weaknesses


def mutation_expand(harness_files, missing):
    """Strategy 1: Add missing standard files from templates."""
    templates = {
        "AGENTS.md": """# AGENTS.md — Agent Coordination Protocol

## Sub-Agent Spawning
- Spawn sub-agents via `delegate_task` for tasks that can run independently
- Each sub-agent gets a focused, single goal
- Do NOT spawn more than 3 sub-agents concurrently without prior justification

## Delegation Protocol
- Match task type to agent specialization (web → research agent, code → coding agent)
- Provide all context needed in the `context` parameter — do not assume the agent has prior context
- Set `role='orchestrator'` only when the task requires nested delegation

## Safety Constraints
- Sub-agents inherit the same harness constraints as the parent
- Any destructive operation (rm, git force-push, DROP DATABASE) must be confirmed before execution
- External actions (email, tweet, POST to external API) require explicit user confirmation

## Communication
- Sub-agent results are synthesized into a coherent response before returning to user
- Do not simply concatenate outputs — synthesize, prioritize, and present
""",
        "TOOLS.md": """# TOOLS.md — Available Tools

## File Operations
- `read_file(path, offset, limit)` — read a file with pagination
- `patch(path, old_string, new_string)` — targeted find-replace edit
- `write_file(path, content)` — write or overwrite a file
- `search_files(pattern, target, path)` — grep/glob across files
- `terminal(command, timeout)` — run shell commands

## Web
- `web_search(query)` — search the web
- `web_extract(urls)` — extract content from URLs

## Agent Coordination
- `delegate_task(goal, context, toolsets)` — spawn a sub-agent
- `cronjob(action, prompt, schedule)` — schedule background tasks

## Communication
- `send_message(platform, target, text)` — send to Discord/Telegram

## Development
- Use `trash` over `rm` — no plain `rm`
- Always run lint/typecheck/tests before pushing
- Handle errors explicitly — no silent catches
""",
    }
    for fname in missing:
        if fname in templates:
            harness_files[fname] = templates[fname]
            print(f"  + Added {fname} (expand strategy)")
    return harness_files


def mutation_refine(harness_files, weaknesses):
    """Strategy 2: Improve weakest sections."""
    refinements = {
        "SOUL.md": lambda c: _refine_soul(c),
        "IDENTITY.md": lambda c: _refine_identity(c),
        "TOOLS.md": lambda c: _refine_tools(c),
        "AGENTS.md": lambda c: _refine_agents(c),
    }
    for fname, words, signal, content in weaknesses:
        if fname in refinements and words < 200:
            harness_files[fname] = refinements[fname](content)
            print(f"  ~ Refined {fname} (was {words} words, signal={signal})")
    return harness_files


def _refine_soul(content):
    """Add missing sections to SOUL.md."""
    if "boundary" not in content.lower() and "red line" not in content.lower():
        content += "\n\n## Boundaries (Non-Negotiable)\n- Never commit secrets, API keys, .env files\n- Never force-push to main or master\n- External actions (email, tweet, external POST) require explicit confirmation\n"
    if "quality" not in content.lower():
        content += "\n\n## Quality Bar\n- All code must pass lint and typecheck before commit\n- Tests are non-negotiable for new functionality\n- Handle errors explicitly — silent catches are unacceptable\n"
    if "decisive" not in content.lower() and "direct" not in content.lower():
        content += "\n\n## Voice\n- Be precise and direct. Say what you mean. Don't be a corporate drone or sycophant.\n"
    return content


def _refine_identity(content):
    if "direct" not in content.lower() and "decisive" not in content.lower():
        content += "\n\n## Communication Style\n- Direct and confident. No hedging, no filler words.\n- Prefer real proof over assertions. Don't validate incorrect premises.\n"
    return content


def _refine_tools(content):
    if "trash" not in content.lower():
        content += "\n\n## File Deletion\n- Use `trash` over `rm` — never plain `rm` for file deletion\n- Never `rm -rf` under any circumstances\n"
    return content


def _refine_agents(content):
    if "confirm" not in content.lower() and "destructive" not in content.lower():
        content += "\n\n## Safety\n- Destructive operations require explicit user confirmation\n- External actions (email, API POSTs) require user confirmation before executing\n"
    return content


def save_candidate(candidate_num, harness_files):
    """Write harness files to new candidate directory."""
    cand_dir = CANDIDATES_DIR / f"candidate_{candidate_num}"
    harness_dir = cand_dir / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    for fname, content in harness_files.items():
        (harness_dir / fname).write_text(content)

    # Write metadata
    meta = {
        "candidate": f"candidate_{candidate_num}",
        "proposed_at": datetime.now().isoformat(),
        "files": list(harness_files.keys()),
        "word_counts": {f: len(c.split()) for f, c in harness_files.items()},
    }
    (cand_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return cand_dir


def main():
    parser = argparse.ArgumentParser(description="Propose a new candidate harness")
    parser.add_argument("--expand", action="store_true", help="Force expand missing files")
    parser.add_argument("--refine", action="store_true", help="Force refine weak sections")
    parser.add_argument("--strategy", choices=["expand", "refine", "auto"], default="auto")
    args = parser.parse_args()

    harness_files = load_best_harness()
    if not harness_files:
        print("Error: No best harness found at best/current/")
        sys.exit(1)

    print(f"\nProposing new candidate based on {len(harness_files)} best harness files")
    print("=" * 60)

    # Analyze
    missing = list_missing_files(harness_files)
    weaknesses = analyze_weak_sections(harness_files)

    print(f"  Missing files: {missing}")
    if weaknesses:
        print(f"  Weakest sections:")
        for fname, words, signal, _ in weaknesses[:3]:
            print(f"    {fname}: {words} words, signal={signal}")

    # Mutate
    if args.strategy == "expand" or (args.strategy == "auto" and missing):
        strategy = "expand"
        harness_files = mutation_expand(harness_files, missing)
        harness_files = mutation_refine(harness_files, weaknesses)

    elif args.strategy == "refine" or (args.strategy == "auto" and weaknesses):
        strategy = "refine"
        harness_files = mutation_refine(harness_files, weaknesses)

    else:
        strategy = "auto"
        print("  Best harness is complete — applying minimal refinement")
        harness_files = mutation_refine(harness_files, weaknesses[:2])

    # Save
    candidate_num = count_candidates()
    cand_dir = save_candidate(candidate_num, harness_files)

    print(f"\n✓ Created {cand_dir}")
    print(f"  Strategy: {strategy}")
    print(f"  Files: {list(harness_files.keys())}")
    print(f"\nNext: python3 evaluate_v2.py {candidate_num} --stubs")
    print(f"       python3 evaluate_v2.py {candidate_num} --real")


if __name__ == "__main__":
    main()
