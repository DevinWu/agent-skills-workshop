"""
Exercise 4 — Orchestrator (run this first)
===========================================
Terminal 1:  python3 exercises/04-orchestration/orchestrator.py
Terminal 2:  python3 exercises/04-orchestration/client.py

The orchestrator boots up, loads all skills into memory, then listens on
localhost:9999 for goals from the client. Each goal is routed to the right
worker skill automatically based on description matching.
"""

import os
import sys
import re
import socket
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
HOST = "localhost"
PORT = 9999


# ── Load skills into memory ───────────────────────────────────────────────

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


def route(goal: str, index: str) -> tuple[str, str]:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=f"You are a skill router.\n\nAvailable skills:\n{index}\n\n.",
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
                    console.print(f"  [dim][{skill_name}][/dim] → [cyan]{block.name}[/cyan]")
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


# ── Boot ──────────────────────────────────────────────────────────────────

console.print(Rule("[bold]Orchestrator — booting up[/bold]"))
console.print("[dim]Scanning skills/ directory...[/dim]")

skills = load_skills()
skill_index = "\n".join(f"- {s['name']}: {s['description']}" for s in skills)

console.print()
for s in skills:
    console.print(f"  [green]✓[/green] loaded [bold]{s['name']}[/bold]")
    console.print(f"    [dim]{s['description']}[/dim]")

console.print()
console.print(Panel(
    skill_index,
    title=f"[bold]Skill Index — {len(skills)} workers in memory[/bold]",
    border_style="green"
))
console.print()

# ── Listen for goals ──────────────────────────────────────────────────────

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.listen(1)

console.print(f"[bold green]Listening on {HOST}:{PORT}[/bold green] — waiting for goals from client...")
console.print("[dim]Run:  python3 exercises/04-orchestration/client.py[/dim]\n")

while True:
    conn, _ = sock.accept()
    with conn:
        data = b""
        while chunk := conn.recv(4096):
            data += chunk
        goal = data.decode().strip()
        if not goal:
            continue

        console.print(Rule(f"[cyan]{goal}[/cyan]"))
        console.print("[dim]Routing...[/dim]")

        skill_name, reason = route(goal, skill_index)
        console.print(f"  [dim]invoke_skill([/dim][bold green]\"{skill_name}\"[/bold green][dim])[/dim]  — {reason}")

        skill = next((s for s in skills if s["name"] == skill_name), None)
        if not skill:
            error = f"No skill named '{skill_name}' — check descriptions"
            console.print(f"  [red]{error}[/red]")
            conn.sendall(error.encode())
            continue

        console.print(f"  [dim]Worker [{skill_name}] starting...[/dim]")
        answer = execute_skill(skill["body"], goal, skill_name)
        console.print(Panel(answer, title=f"[bold]{skill_name}[/bold]", border_style="green"))
        console.print()
        conn.sendall(answer.encode())
