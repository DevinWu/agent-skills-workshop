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

load_dotenv(override=True)

import anthropic
from pipeline.tools import run_tool, ALL_TOOLS

console = Console()
api_key = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

SYSTEM_PROMPT = """You are a procurement analyst assistant.
Answer questions using the tools available. Be concise."""


def _final_text(response) -> str:
    """Join every text block. stop_details is populated only when stop_reason == 'refusal'."""
    if response.stop_reason == "refusal" and response.stop_details:
        return f"[refused: {response.stop_details.category}]"
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or f"[no text — stop_reason={response.stop_reason!r}]"


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
            return _final_text(response)

        else:
            # max_tokens / stop_sequence / pause_turn / refusal.
            # Must return here: nothing was appended to messages, so looping
            # would resend the identical request forever.
            console.print(f"  [yellow]→ unexpected stop_reason {response.stop_reason!r}[/yellow]")
            return _final_text(response)


# ── Run ───────────────────────────────────────────────────────────────────

console.print(Rule("[bold]Exercise 1 — Refresher: The Agent Loop[/bold]"))
console.print("[dim]Same loop as Session 1. Tools + stop_reason. Let's move fast.[/dim]\n")

questions = [
    # Case 1 — both tools independent: Claude requests both in one go, 2 turns total
    "List all overdue invoices and tell me what our late payment policy says about them.",

    # Case 2 — chained: Claude must use the result of Turn 1 to decide Turn 2
    # It cannot search policy until it knows which vendor has the highest invoice total
    "Find the vendor with the highest total invoice amount, then search our policy for that vendor's risk level.",
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
