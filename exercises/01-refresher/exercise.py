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

    while True:
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
                    console.print(f"    → [cyan]{block.name}[/cyan]")
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            console.print(f"  [dim]→ done[/dim]")
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text.strip()
            return ""


# ── Run ───────────────────────────────────────────────────────────────────

console.print(Rule("[bold]Exercise 1 — Refresher: The Agent Loop[/bold]"))
console.print("[dim]Same loop as Session 1. Tools + stop_reason. Let's move fast.[/dim]\n")

questions = [
    # Needs two tool calls — first checks overdue invoices, then looks up vendor policy
    "List all overdue invoices and tell me what our late payment policy says about them.",
    # TODO: uncomment the line below and run again — what tool does the agent call?
    # "What is our policy for high-risk vendors?",
]

for q in questions:
    console.print(f"[bold cyan]Q:[/bold cyan] {q}")
    answer = run_agent(q)
    console.print(Panel(answer, border_style="green"))
    console.print()

console.print(Panel(
    "stop_reason = 'tool_use'  → LLM wants to call a tool\n"
    "stop_reason = 'end_turn'  → LLM is done, return the answer\n\n"
    "This loop is the foundation everything else builds on.\n\n"
    "✏️  Try it: uncomment the second question above and run again.\n"
    "    Which tool does it call this time — query_database or search_knowledge_base?",
    title="[bold]Key reminder[/bold]",
    border_style="yellow"
))
