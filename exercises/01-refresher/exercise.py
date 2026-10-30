"""
Exercise 1 — Refresher: The Agent Loop
========================================
A quick recap of Session 1.

The agent loop in 3 lines of logic:
  1. Send message + tools to the LLM
  2. If LLM calls a tool → run it → send result back → repeat
  3. If LLM replies with text → done

Run:  python exercises/01-refresher/exercise.py
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

SYSTEM_PROMPT = """You are a procurement analyst assistant.
Answer questions using the tools available. Be concise."""


def run_agent(question: str) -> str:
    messages = [{"role": "user", "content": question}]
    turn = 0

    while True:
        turn += 1
        console.print(f"  [dim]── Turn {turn} ──[/dim]")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=messages,
        )

        console.print(f"  [dim]stop_reason = [/dim][bold yellow]{response.stop_reason!r}[/bold yellow]")

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    console.print(f"    → [cyan]{block.name}[/cyan]  [dim](tool call inside Turn {turn})[/dim]")
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            console.print(f"  [dim]→ done (Turn {turn})[/dim]")
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text.strip()
            return ""


# ── Run ───────────────────────────────────────────────────────────────────

console.print(Rule("[bold]Exercise 1 — Refresher: The Agent Loop[/bold]"))
console.print("[dim]Same loop as Session 1. Tools + stop_reason. Let's move fast.[/dim]\n")

questions = [
    # Case 1 — both tools independent: Claude requests both in one go, 2 turns total
    "List all overdue invoices and tell me what our late payment policy says about them.",

    # Case 2 — chained: find the overdue invoice first, then look up that vendor's policy risk
    # Claude must see the invoice result before it knows which vendor policy to search for
    "Find the largest overdue invoice, then tell me what our policy says about that vendor's risk level.",
]

for q in questions:
    console.print(f"[bold cyan]Q:[/bold cyan] {q}")
    answer = run_agent(q)
    console.print(Panel(answer, border_style="green"))
    console.print()

console.print(Panel(
    "Case 1 — independent tools:  Claude requests both in Turn 1, 2 turns total\n"
    "Case 2 — chained tools:      Claude needs the first result before asking the next\n"
    "                             Each dependent query = a new turn\n\n"
    "The number of turns depends on whether Claude can plan all tool calls upfront\n"
    "or needs to see intermediate results first.\n\n"
    "✏️  Try it: uncomment the second question above and run again.\n"
    "    Which tool does it call this time — query_database or search_knowledge_base?",
    title="[bold]Key reminder[/bold]",
    border_style="yellow"
))
