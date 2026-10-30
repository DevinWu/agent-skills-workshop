"""
Exercise 3 — Predictability: Skill vs No Skill
=================================================
A skill does not just add steps — it removes unpredictability.

Without a skill, the agent decides what to check every run.
Same question. Different steps. Different output. Every time.

With a skill, the steps are fixed.
Same question. Same steps. Same output. Every time.

This exercise runs the SAME question 3 times each way so you can see it yourself.

Run:  python exercises/03-routing/exercise.py
"""

import os
import sys
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()

import anthropic
from pipeline.tools import run_tool, ALL_TOOLS

console = Console()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

GOAL = "Check the health of our vendor Eastern Parts Corp."

RAW_PROMPT = """You are a procurement analyst assistant.
Use the tools available to answer the user's request."""

_skill_path = os.path.join(os.path.dirname(__file__), "../../skills/vendor-health/SKILL.md")
_skill_content = open(_skill_path).read()
SKILL_PROMPT = re.sub(r"^---\n.*?\n---\n?", "", _skill_content, flags=re.DOTALL).strip()


def run_agent(system_prompt: str, label: str) -> list[str]:
    """Run the agent, return the list of tool names called."""
    messages = [{"role": "user", "content": GOAL}]
    tools_called = []

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            tools=ALL_TOOLS,
            messages=messages,
        )
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tools_called.append(block.name)
                    console.print(f"  [{label}] → [cyan]{block.name}[/cyan]")
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            return tools_called


RUNS = 3

# ── Without skill — run 3 times ───────────────────────────────────────────

console.print(Rule("[bold]Exercise 3 — Predictability: Skill vs No Skill[/bold]"))
console.print(f"\n[bold cyan]Goal (same every run):[/bold cyan] {GOAL}\n")
console.print(Rule("[yellow]Without skill — raw agent[/yellow]"))

raw_runs = []
for i in range(1, RUNS + 1):
    console.print(f"\n[dim]Run {i}:[/dim]")
    tools = run_agent(RAW_PROMPT, f"run-{i}")
    raw_runs.append(tools)

# ── With skill — run 3 times ──────────────────────────────────────────────

console.print()
console.print(Rule("[green]With skill — fixed steps[/green]"))

skill_runs = []
for i in range(1, RUNS + 1):
    console.print(f"\n[dim]Run {i}:[/dim]")
    tools = run_agent(SKILL_PROMPT, f"skill-{i}")
    skill_runs.append(tools)

# ── Comparison table ──────────────────────────────────────────────────────

console.print()
console.print(Rule("[bold]Same goal — what actually ran[/bold]"))

TOOL_SHORT = {"query_database": "query_db", "search_knowledge_base": "search_kb"}

table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
table.add_column("Run", width=6)
table.add_column("Without skill", style="yellow", width=40)
table.add_column("With skill", style="green", width=40)

for i in range(RUNS):
    raw  = " → ".join(TOOL_SHORT.get(t, t) for t in raw_runs[i])
    skill = " → ".join(TOOL_SHORT.get(t, t) for t in skill_runs[i])
    table.add_row(f"#{i+1}", raw, skill)

console.print(table)
console.print()

# ── Check if raw runs were consistent ────────────────────────────────────

raw_hits_policy   = all("search_knowledge_base" in r for r in raw_runs)
skill_hits_policy = all("search_knowledge_base" in r for r in skill_runs)

console.print(Panel(
    f"Without skill — policy check (search_knowledge_base) ran every time? "
    f"[bold]{'✓ yes' if raw_hits_policy else '✗ no — skipped on some runs'}[/bold]\n"
    f"With skill    — policy check ran every time? "
    f"[bold]{'✓ yes' if skill_hits_policy else '✗ no'}[/bold]\n\n"
    "A skill does not just add steps — it guarantees them.\n"
    "The raw agent may skip the policy check depending on how it interprets the question.\n"
    "The skill makes it impossible to skip.\n\n"
    "That is what makes it safe to run in production — you know exactly what ran.\n\n"
    "→ Exercise 4 shows how the orchestration layer picks the right skill automatically.",
    title="[bold]What you saw[/bold]",
    border_style="cyan"
))
