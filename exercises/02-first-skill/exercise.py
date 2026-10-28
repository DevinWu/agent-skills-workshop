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


def run_agent(system_prompt: str, goal: str, label: str) -> str:
    messages = [{"role": "user", "content": goal}]
    iterations = 0

    while True:
        iterations += 1
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
                    console.print(f"  [{label}] → [cyan]{block.name}[/cyan]({block.input})")
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
                    return block.text.strip()
            return ""


# ── Part A: No skill — agent decides ─────────────────────────────────────

console.print(Rule("[bold]Part A — No Skill (agent decides)[/bold]"))

NO_SKILL_PROMPT = """You are a procurement analyst assistant.
You have tools available. Use them to answer the user's request."""

answer_a = run_agent(NO_SKILL_PROMPT, GOAL, "no-skill")
console.print(Panel(answer_a, title="[bold]Answer (no skill)[/bold]", border_style="yellow"))
console.print()

# ── Part B: With skill — steps are fixed ─────────────────────────────────

console.print(Rule("[bold]Part B — With Skill (steps are fixed)[/bold]"))

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

answer_b = run_agent(VENDOR_HEALTH_SKILL, GOAL, "skill")
console.print(Panel(answer_b, title="[bold]Answer (with skill)[/bold]", border_style="green"))

# ── What to observe ───────────────────────────────────────────────────────

console.print(Panel(
    "Part A: the agent decided what to check — it may have missed steps.\n"
    "Part B: the skill forced EXACTLY 4 steps, always, every time.\n\n"
    "A skill = consistent, repeatable, auditable behaviour.\n"
    "The agent's job is no longer 'figure out what to do' — it's 'follow the steps'.\n\n"
    "But wait — did we actually NEED a skill here?\n"
    "→ That's Exercise 3.",
    title="[bold]What you saw[/bold]",
    border_style="cyan"
))
