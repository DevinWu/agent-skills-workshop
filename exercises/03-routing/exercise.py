"""
Exercise 3 — When is a Skill Overkill?
========================================
A skill forces fixed steps — great when you need all of them.
But what if the question only needs one tool call?

This exercise runs the SAME simple question two ways:
  - With the vendor-health skill  → forces 4 steps every time
  - Without a skill (direct)      → one tool call, direct answer

Watch the tool calls. Then ask: was the skill worth it here?

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

load_dotenv(override=True)

import anthropic
from pipeline.tools import run_tool, ALL_TOOLS

console = Console()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# A simple question — one tool call is all it needs
SIMPLE_QUESTION = "What is the risk rating of Eastern Parts Corp?"

# The skill is designed for a full health check — it will force 4 steps
SKILL_GOAL = "Check the health of Eastern Parts Corp"

RAW_PROMPT = """You are a procurement analyst assistant.
Use the tools available to answer the user's request."""

_skill_path = os.path.join(os.path.dirname(__file__), "../../skills/vendor-health/SKILL.md")
_skill_content = open(_skill_path).read()
SKILL_PROMPT = re.sub(r"^---\n.*?\n---\n?", "", _skill_content, flags=re.DOTALL).strip()


def _final_text(response) -> str:
    """Join every text block. stop_details is populated only when stop_reason == 'refusal'."""
    if response.stop_reason == "refusal" and response.stop_details:
        return f"[refused: {response.stop_details.category}]"
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or f"[no text — stop_reason={response.stop_reason!r}]"


def run_agent(system_prompt: str, label: str, goal: str) -> tuple[list[str], str]:
    """Run the agent, return (tool names called, final answer)."""
    messages = [{"role": "user", "content": goal}]
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
                    inp = block.input
                    hint = inp.get("sql", inp.get("query", ""))[:80]
                    console.print(f"  [{label}] → [cyan]{block.name}[/cyan]  [dim]{hint}[/dim]")
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            return tools_called, _final_text(response)

        else:
            # max_tokens / stop_sequence / pause_turn / refusal.
            # Must return here: nothing was appended to messages, so looping
            # would resend the identical request forever.
            console.print(f"  [{label}] [yellow]→ unexpected stop_reason {response.stop_reason!r}[/yellow]")
            return tools_called, _final_text(response)


console.print(Rule("[bold]Exercise 3 — When is a Skill Overkill?[/bold]"))
console.print(f"\n[bold cyan]Question:[/bold cyan] {SIMPLE_QUESTION}\n")
console.print("[dim]This only needs one tool call. Watch what happens when we force a skill.[/dim]\n")

# ── With skill ────────────────────────────────────────────────────────────

console.print(Rule("[green]With skill — vendor-health (4 fixed steps)[/green]"))
skill_tools, skill_answer = run_agent(SKILL_PROMPT, "skill", SKILL_GOAL)

console.print(Panel(skill_answer, title="[bold]Answer (with skill)[/bold]", border_style="green"))
console.print()

# ── Direct — no skill ─────────────────────────────────────────────────────

console.print(Rule("[yellow]Direct — no skill (agent decides)[/yellow]"))
raw_tools, raw_answer = run_agent(RAW_PROMPT, "direct", SIMPLE_QUESTION)

console.print(Panel(raw_answer, title="[bold]Answer (direct)[/bold]", border_style="yellow"))
console.print()

# ── Comparison ────────────────────────────────────────────────────────────

console.print(Rule("[bold]Comparison[/bold]"))

TOOL_SHORT = {"query_database": "query_db", "search_knowledge_base": "search_kb"}

table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
table.add_column("", width=16)
table.add_column("With skill", style="green", width=36)
table.add_column("Direct", style="yellow", width=36)

table.add_row(
    "Tool calls",
    " → ".join(TOOL_SHORT.get(t, t) for t in skill_tools),
    " → ".join(TOOL_SHORT.get(t, t) for t in raw_tools),
)
table.add_row("Count", str(len(skill_tools)), str(len(raw_tools)))

console.print(table)
console.print()

console.print(Panel(
    f"The question was: \"{SIMPLE_QUESTION}\"\n\n"
    f"Direct: {len(raw_tools)} tool call — clean, precise answer.\n"
    f"Skill:  {len(skill_tools)} tool calls — full health report nobody asked for.\n\n"
    "The skill is not wrong — it ran the right steps for a full health check.\n"
    "But the question only needed one thing: the risk rating.\n\n"
    "Rule of thumb:\n"
    "  ✓ Use a skill  — multiple steps must always happen, output must be consistent\n"
    "  ✗ Skip a skill — one tool call answers it, no audit requirement\n\n"
    "→ Part 3 covers when to use which.",
    title="[bold]What you saw[/bold]",
    border_style="cyan"
))

# ── Verify it yourself — the answer is just a column ─────────────────────

console.print()
console.print(Rule("[dim]Why only 1 call was needed[/dim]"))
console.print(
    "[dim]risk_rating is just a column in the vendors table.\n"
    "Run this and look at the vendors table — the answer is right there:\n\n"
    "  python3 -c \"\n"
    "  import sqlite3\n"
    "  conn = sqlite3.connect('data/erp.db')\n"
    "  rows = conn.execute('SELECT * FROM vendors LIMIT 5').fetchall()\n"
    "  cols = [d[0] for d in conn.execute('SELECT * FROM vendors LIMIT 0').description]\n"
    "  print(' | '.join(cols))\n"
    "  for r in rows: print(' | '.join(str(v) for v in r))\n"
    "  \"[/dim]"
)
