"""
Exercise 2 — Your First Skill
================================
A skill packages a multi-step workflow into one callable unit.

Instead of the agent deciding WHAT to do, a skill tells it exactly:
  1. What steps to follow
  2. In what order
  3. What the output should look like

The skill lives in a SKILL.md file.
The agent reads it and follows the instructions.

Part A: Run the agent WITHOUT a skill — it decides the steps itself.
Part B: Run the agent WITH a skill — the steps are fixed.

Compare the two. What's different?

Run:  python exercises/02-first-skill/exercise.py
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

load_dotenv()

import anthropic
from pipeline.tools import run_tool, ALL_TOOLS

console = Console()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

GOAL = "Check the health of our vendor Eastern Parts Corp."


def run_agent(system_prompt: str, goal: str, label: str):
    """Returns (answer, tool_calls_log)."""
    messages = [{"role": "user", "content": goal}]
    tool_calls_log = []

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
                    # Extract the most readable part of the input for display
                    inp = block.input
                    hint = inp.get("sql", inp.get("query", str(inp)))[:60]
                    entry = f"{block.name}({hint!r})"
                    tool_calls_log.append(entry)
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
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text.strip(), tool_calls_log
            return "", tool_calls_log


# ── Part A: No skill — agent decides ─────────────────────────────────────

console.print(Rule("[bold]Part A — No Skill (agent decides)[/bold]"))
console.print("[dim]Goal:[/dim]", GOAL)
console.print()

NO_SKILL_PROMPT = """You are a procurement analyst assistant.
You have tools available. Use them to answer the user's request."""

answer_a, calls_a = run_agent(NO_SKILL_PROMPT, GOAL, "no-skill")
console.print(Panel(answer_a, title="[bold]Answer (no skill)[/bold]", border_style="yellow"))
console.print()

# ── Part B: With skill — steps are fixed ─────────────────────────────────

console.print(Rule("[bold]Part B — With Skill (steps are fixed)[/bold]"))
console.print("[dim]Goal:[/dim]", GOAL)
console.print()

VENDOR_HEALTH_SKILL = """You are a procurement analyst.

Follow these steps EXACTLY to check a vendor's health:

1. Query the database for the vendor's details (risk_rating, payment_terms, country)
2. Query the database for their open purchase orders (count and total amount)
3. Query the database for any overdue invoices linked to their POs
4. Search the knowledge base for the policy on high-risk vendors

Then write a short report with:
## Vendor Profile
## Open Orders
## Overdue Invoices
## Policy Notes
## Risk Assessment (one sentence)
"""

answer_b, calls_b = run_agent(VENDOR_HEALTH_SKILL, GOAL, "skill")
console.print(Panel(answer_b, title="[bold]Answer (with skill)[/bold]", border_style="green"))
console.print()

# ── Side-by-side comparison ───────────────────────────────────────────────

console.print(Rule("[bold]Comparison[/bold]"))

max_rows = max(len(calls_a), len(calls_b))
no_skill_col = calls_a + ["—"] * (max_rows - len(calls_a))
skill_col    = calls_b + ["—"] * (max_rows - len(calls_b))

from rich.table import Table
table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
table.add_column(f"No Skill  ({len(calls_a)} tool calls)", style="yellow", width=42)
table.add_column(f"With Skill  ({len(calls_b)} tool calls)", style="green", width=42)
for a, b in zip(no_skill_col, skill_col):
    table.add_row(a, b)
console.print(table)
console.print()

missed = {"search_knowledge_base"} - {c.split("(")[0] for c in calls_a}
note = ""
if missed:
    note = f"\n[yellow]No-skill agent skipped:[/yellow] {', '.join(missed)} — policy check was missing."

console.print(Panel(
    f"Same goal. Same tools. [bold]Different behaviour.[/bold]{note}\n\n"
    "No skill: the agent [yellow]chose[/yellow] what to check — steps vary every run.\n"
    "With skill: the agent [green]followed[/green] 4 fixed steps — same output every time.\n\n"
    "A skill = consistent, repeatable, auditable behaviour.\n\n"
    "But wait — did we actually NEED a skill here?\n"
    "→ That's Exercise 3.",
    title="[bold]What you saw[/bold]",
    border_style="cyan"
))
