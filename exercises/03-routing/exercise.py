"""
Exercise 3 — When is a Skill Overkill?
=========================================
Not everything needs a skill.

This exercise shows the same question answered two ways:
  A) With the vendor-health skill (4 forced steps)
  B) With a single tool call

The question: "What is the risk rating of Eastern Parts Corp?"

One answer is thorough. One is direct. Which one does the user actually need?

A skill is overkill when:
  - The answer needs ONE tool call
  - The steps don't need to be fixed
  - There is no repeated workflow to package

Run:  python exercises/03-routing/exercise.py
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
import time

load_dotenv()

import anthropic
from pipeline.tools import run_tool, ALL_TOOLS

console = Console()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

QUESTION = "What is the risk rating of Eastern Parts Corp?"


def run_agent(system_prompt: str, question: str, label: str) -> tuple[str, int, float]:
    messages = [{"role": "user", "content": question}]
    tool_calls = 0
    start = time.time()

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
                    tool_calls += 1
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
            elapsed = time.time() - start
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text.strip(), tool_calls, elapsed
            return "", tool_calls, elapsed


# ── With skill (4 forced steps) ───────────────────────────────────────────

console.print(Rule("[bold]Exercise 3 — When is a Skill Overkill?[/bold]"))
console.print(f"\n[bold cyan]Question:[/bold cyan] {QUESTION}\n")

VENDOR_HEALTH_SKILL = """You are a procurement analyst.

Follow these steps EXACTLY:
1. Query the database for the vendor's details (risk_rating, payment_terms, country)
2. Query the database for their open purchase orders
3. Query the database for any overdue invoices
4. Search the knowledge base for high-risk vendor policy

Then write a report with sections: Vendor Profile, Open Orders, Overdue Invoices, Policy Notes, Risk Assessment."""

console.print(Rule("[dim]With vendor-health skill[/dim]"))
answer_skill, calls_skill, time_skill = run_agent(VENDOR_HEALTH_SKILL, QUESTION, "skill")
console.print(Panel(answer_skill, title=f"[bold]Skill answer ({calls_skill} tool calls, {time_skill:.1f}s)[/bold]", border_style="yellow"))
console.print()

# ── Without skill (agent decides) ────────────────────────────────────────

SIMPLE_PROMPT = """You are a procurement analyst assistant.
Answer the question using the minimum tool calls needed. Be direct and concise."""

console.print(Rule("[dim]Without skill (direct)[/dim]"))
answer_direct, calls_direct, time_direct = run_agent(SIMPLE_PROMPT, QUESTION, "direct")
console.print(Panel(answer_direct, title=f"[bold]Direct answer ({calls_direct} tool call, {time_direct:.1f}s)[/bold]", border_style="green"))

# ── The lesson ────────────────────────────────────────────────────────────

console.print(Panel(
    f"Skill:  {calls_skill} tool calls, {time_skill:.1f}s — thorough but heavy for this question\n"
    f"Direct: {calls_direct} tool call,  {time_direct:.1f}s — answered the actual question\n\n"
    "A skill adds value when:\n"
    "  ✓ The workflow has multiple steps that must always happen\n"
    "  ✓ The output format must be consistent\n"
    "  ✓ The same workflow runs repeatedly\n\n"
    "A skill is overkill when:\n"
    "  ✗ One tool call answers the question\n"
    "  ✗ The steps don't need to be fixed\n"
    "  ✗ You're packaging for the sake of it\n\n"
    "→ Exercise 4 shows how the orchestration service routes to the RIGHT skill.",
    title="[bold]Skill vs No Skill[/bold]",
    border_style="cyan"
))
