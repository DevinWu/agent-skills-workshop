"""
Exercise 4 — The Orchestration Layer
=======================================
How does the agent know WHICH skill to call?

The orchestration layer:
  1. Scans skills/*/SKILL.md — reads name + description from each
  2. Builds a skill index and gives it to the router LLM
  3. Router LLM reads descriptions and calls invoke_skill("best-match")
  4. Orchestrator loads that skill's body, runs the agent loop with real tools

The description on each SKILL.md IS the routing signal.
Change the description → change what gets called.

This is exactly how production orchestration services work.

Run:  python exercises/04-orchestration/exercise.py
"""

import os
import sys
import re
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

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "../../skills")


# ── Load skills ───────────────────────────────────────────────────────────

def load_skills() -> list[dict]:
    skills = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, entry, "SKILL.md")
        if not os.path.isfile(path):
            continue
        content = open(path).read()
        fm = {}
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            for line in match.group(1).splitlines():
                idx = line.find(":")
                if idx != -1:
                    fm[line[:idx].strip()] = line[idx + 1:].strip()
        body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL).strip()
        skills.append({
            "name": fm.get("name", entry),
            "description": fm.get("description", entry),
            "body": body,
        })
    return skills


# ── Router ────────────────────────────────────────────────────────────────

INVOKE_SKILL_SCHEMA = {
    "name": "invoke_skill",
    "description": "Invoke the single best matching skill to handle the request. ALWAYS call this first.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skill":  {"type": "string", "description": "Name of the skill to invoke"},
            "reason": {"type": "string", "description": "Why this skill matches"},
        },
        "required": ["skill", "reason"],
    },
}


def route(goal: str, skills: list[dict]) -> tuple[str, str]:
    index = "\n".join(f"- {s['name']}: {s['description']}" for s in skills)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=f"You are a skill router.\n\nAvailable skills:\n{index}\n\nCall invoke_skill immediately.",
        tools=[INVOKE_SKILL_SCHEMA],
        messages=[{"role": "user", "content": goal}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "invoke_skill":
            return block.input["skill"], block.input.get("reason", "")
    return "", ""


# ── Skill executor ────────────────────────────────────────────────────────

def execute_skill(skill_body: str, goal: str, skill_name: str) -> str:
    messages = [{"role": "user", "content": goal}]
    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=skill_body,
            tools=ALL_TOOLS,
            messages=messages,
        )
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    console.print(f"  [{skill_name}] → [cyan]{block.name}[/cyan]")
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


# ── Run three different goals ─────────────────────────────────────────────

console.print(Rule("[bold]Exercise 4 — The Orchestration Layer[/bold]"))

skills = load_skills()
index_display = "\n".join(f"  - {s['name']}: {s['description'][:60]}..." for s in skills)
console.print(Panel(f"Loaded {len(skills)} skills:\n{index_display}", title="Skill Index", border_style="dim"))
console.print()

goals = [
    "Check the health of vendor Eastern Parts Corp",
    "Give me a report of all overdue invoices",
    "Run a full procurement audit",
    # ✏️  Once you've filled in skills/my-first-skill/SKILL.md,
    #     add a goal here that matches your description and run again:
    # "???",
]

for goal in goals:
    console.print(f"[bold cyan]Goal:[/bold cyan] {goal}")
    skill_name, reason = route(goal, skills)
    console.print(f"  → routed to [bold green]{skill_name}[/bold green] — {reason}")

    skill = next((s for s in skills if s["name"] == skill_name), None)
    if not skill:
        console.print(f"  [red]Skill '{skill_name}' not found[/red]")
        continue

    answer = execute_skill(skill["body"], goal, skill_name)
    console.print(Panel(answer, title=f"[bold]{skill_name}[/bold]", border_style="green"))
    console.print()

console.print(Panel(
    "The router LLM reads DESCRIPTIONS — not skill bodies — to pick the right skill.\n"
    "The description IS the routing signal.\n\n"
    "Change a description → change what gets routed there.\n"
    "This is the same pattern production orchestration services use at scale.\n\n"
    "Key difference in production:\n"
    "  - Skills loaded from object storage (S3/Redis), not local files\n"
    "  - Per-tenant allowlists control which skills are available\n"
    "  - Router model and skill model can be configured independently\n"
    "  - invoke_skill is a synthetic tool — intercepted by the service, never leaves it",
    title="[bold]How orchestration works[/bold]",
    border_style="cyan"
))

console.print(Panel(
    "✏️  Your turn — open  skills/my-first-skill/SKILL.md\n\n"
    "Replace every ??? with real content:\n"
    "  1. Give it a description that clearly says WHEN to use it\n"
    "  2. Write 1-2 steps (query_database or search_knowledge_base)\n"
    "  3. Give the report section a name\n\n"
    "Then run this exercise again.\n"
    "Your skill will appear in the index automatically — no code change needed.\n\n"
    "Try asking a goal that matches your description and watch it get routed there.",
    title="[bold yellow]Try it yourself[/bold yellow]",
    border_style="yellow"
))
