"""
Exercise 4 — Client (run this in a second terminal)
====================================================
Terminal 1:  python3 exercises/04-orchestration/orchestrator.py
Terminal 2:  python3 exercises/04-orchestration/client.py

Fires goals at the running orchestrator and prints the answer here.
Terminal 1 shows the routing decisions and tool calls (the orchestrator's view).
Terminal 2 shows the final answers (the caller's view).
"""

import socket
import time
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()

HOST = "localhost"
PORT = 9999

goals = [
    "Check the health of vendor Eastern Parts Corp",
    "Give me a report of all overdue invoices",
    "Run a full procurement audit",
    # ✏️  Once you've filled in skills/my-first-skill/SKILL.md,
    #     add a goal here that matches your description:
    # "???",
]


def send_goal(goal: str):
    console.print(Rule(f"[bold cyan]{goal}[/bold cyan]"))
    for attempt in range(10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                s.sendall(goal.encode())
                s.shutdown(socket.SHUT_WR)
                answer = b""
                while chunk := s.recv(4096):
                    answer += chunk
            console.print(Panel(answer.decode(), border_style="green"))
            console.print()
            return
        except ConnectionRefusedError:
            if attempt == 0:
                console.print("[dim]Waiting for orchestrator to start...[/dim]")
            time.sleep(1)
    console.print(f"[red]Could not connect to orchestrator on {HOST}:{PORT}[/red]")


console.print(Rule("[bold]Client — firing goals[/bold]"))
console.print("[dim]Answers appear here. Routing + tool calls are in Terminal 1.[/dim]\n")

for goal in goals:
    send_goal(goal)
