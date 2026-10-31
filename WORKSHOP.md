# AI Agent Workshop — Session 2: From Agents to Skills

## What you will build

A procurement analyst that starts as a raw agent loop and ends as a fully orchestrated skill system — where a router automatically picks the right skill for any question, and each skill runs fixed, repeatable steps.

By the end you will understand:
- What a skill is and when to use one
- How to build a skill from scratch
- When a skill is overkill — and what to use instead
- How descriptions drive routing decisions
- How a production orchestration service wraps all of this

---

## Schedule

| Time | Section |
|---|---|
| 0:00 | Setup + intro |
| 0:15 | Exercise 1 — Refresher: the agent loop |
| 0:30 | Part 2 — What is a skill? |
| 0:50 | Exercise 2 — Build your first skill |
| 1:20 | Break (10 min) |
| 1:30 | Part 3 — When is a skill overkill? |
| 1:45 | Exercise 3 — Skill vs no skill |
| 2:10 | Part 4 — The orchestration layer |
| 2:30 | Exercise 4 — Orchestration in action |
| 2:50 | Best practices + wrap up |

---

## Setup

**Prerequisites:** Python 3.10+, Anthropic API key — get one at https://console.anthropic.com/settings/keys

**Steps:**

1. Clone the repo
   ```bash
   git clone <repo-url>
   cd agent-skills-workshop
   ```

2. Create and activate a virtual environment
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Seed the database
   ```bash
   python3 data/seed.py
   ```
   This creates `data/erp.db` — 10 vendors, 40 purchase orders, 40 invoices.

5. Add your API key

   Get a key:
   1. Go to https://console.anthropic.com/settings/keys
   2. Click **Create Key**
   3. Copy the key (starts with `sk-ant-...`)

   Add it to your `.env`:
   ```bash
   cp .env.example .env
   # open .env and set:
   # ANTHROPIC_API_KEY=sk-ant-...
   ```

6. Verify everything works
   ```bash
   python3 check_setup.py
   ```

---

## The domain — ERP Procurement

Same procurement domain as Session 1. Three tables in `data/erp.db`:

```
vendors          — supplier master: name, country, payment_terms, risk_rating
purchase_orders  — what was ordered, from whom, at what price, status
invoices         — what vendors billed us, due dates, payment status
```

Two tools in `pipeline/tools.py`:

```
query_database        — run SQL against the ERP database
search_knowledge_base — keyword search over procurement policy documents
```

Four policy documents in `data/policies/` (loaded from disk by `pipeline/tools.py`):
- Late Payment Policy
- High-Risk Vendor Policy
- Vendor Onboarding Policy
- Three-Way Match Process

> Peek at the data before the exercises:
>
> ```bash
> python3 -c "
> import sqlite3
> conn = sqlite3.connect('data/erp.db')
> for table in ['vendors', 'purchase_orders', 'invoices']:
>     print(f'\n--- {table} ---')
>     rows = conn.execute(f'SELECT * FROM {table} LIMIT 5').fetchall()
>     cols = [d[0] for d in conn.execute(f'SELECT * FROM {table} LIMIT 0').description]
>     print(' | '.join(cols))
>     for r in rows: print(' | '.join(str(v) for v in r))
> "
> ```

---

## 0:15 — Exercise 1: Refresher

> **Key points to land:**
> - Claude cannot answer data questions from memory — it needs a tool
> - `stop_reason` is the signal your code watches — it drives the entire loop
> - Every iteration: Claude thinks → your code acts → Claude thinks again
> - This loop is unchanged in Session 2 — skills just change the system prompt

```bash
python3 exercises/01-refresher/exercise.py
```

### What you will see

```
Q: List all overdue invoices and tell me what our late payment policy says.
  stop_reason = 'tool_use'
    → query_database
    → search_knowledge_base
  stop_reason = 'end_turn'
  → done
```

### Code walkthrough — open exercises/01-refresher/exercise.py

The entire agent loop lives in the `run_agent` function. Here it is with annotations:

```python
def run_agent(question: str) -> str:
    messages = [{"role": "user", "content": question}]
    #           ↑ start with just the user's question

    while True:
        #      ↑ loop forever — we only exit when stop_reason = "end_turn"

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            system=SYSTEM_PROMPT,   # ← who Claude is and what it can do
            tools=ALL_TOOLS,        # ← the tools Claude is allowed to call
            messages=messages,      # ← the full conversation so far
        )
        # Claude reads everything and replies — but it may not be done yet

        if response.stop_reason == "tool_use":
            # Claude wants to call one or more tools
            # It did NOT return an answer yet — we must run the tools and loop again

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = run_tool(block.name, block.input)
                    #                 ↑ query_database or search_knowledge_base
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,  # ← ties result back to the request
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            #                                ↑ send ALL tool results back together
            # now loop — Claude reads the results and replies again

        elif response.stop_reason == "end_turn":
            # Claude is done — extract the text and return it
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text.strip()
```

### Where "both tools fired in a single loop turn"

Look at this line in the output:

```
stop_reason = 'tool_use'
  → query_database
  → search_knowledge_base
stop_reason = 'end_turn'
```

`stop_reason = 'tool_use'` appeared **once** — not twice. That means Claude requested both tools in a single response. The `for block in response.content` loop ran twice (once per tool), collected both results, and sent them back together. Then Claude replied with `end_turn`.

The loop only turned **twice** total for this question — one `tool_use` turn, one `end_turn` turn.

### Why stop_reason matters

```python
if response.stop_reason == "tool_use":
    # Claude is not done — run the tools and loop again
elif response.stop_reason == "end_turn":
    # Claude is done — extract the text and return it
```

If you forget to check `stop_reason` and just return the response immediately, you get Claude's tool request back — not an answer. The loop exists entirely to handle `tool_use` turns until Claude reaches `end_turn`.

> **Presenter note:** 15 minutes. Open the file, point to `while True` and say "this is the loop." Point to `stop_reason == "tool_use"` and say "this is where tools run." Point to `stop_reason == "end_turn"` and say "this is the exit." Then run it and watch the output match exactly.

---

## 0:30 — Part 2: What is a Skill?

> **Key points to land:**
> - A raw agent decides its steps fresh every run — output varies
> - A skill fixes the steps in a SKILL.md file — same output every time
> - The skill body becomes the system prompt — Claude follows it like instructions
> - Skills are for repeatable, auditable workflows

### Why skills and not just tool chaining?

This is the first question anyone asks. Tool chaining already works — you saw it in Exercise 1. So why add skills on top?

The answer: **tool chaining is what runs inside a skill. A skill just puts a fence around it.**

Without a skill, the agent decides which tools to call and in what order — every single run:

```
Goal: "Check the health of Eastern Parts Corp"

Run 1:  query_database → query_database → end_turn
Run 2:  query_database → query_database → query_database → search_knowledge_base → end_turn
Run 3:  query_database → end_turn   ← skipped steps, missed the policy check
```

Tool chaining is flexible — great for exploration. But flexible means unpredictable. You cannot guarantee step 4 (the policy check) will always happen.

With a skill, the steps are fixed in the SKILL.md body. The agent still chains tools — but it follows your instructions, not its own judgement:

```
Goal: "Check the health of Eastern Parts Corp"

Run 1:  query_database → query_database → query_database → search_knowledge_base → end_turn
Run 2:  query_database → query_database → query_database → search_knowledge_base → end_turn
Run 3:  query_database → query_database → query_database → search_knowledge_base → end_turn
```

Same 4 steps. Every time. The policy check cannot be skipped.

```
Tool chaining alone          With a skill
──────────────────────────────────────────────────────
Agent decides the steps      You decide the steps
Steps vary every run         Steps are fixed every run
Output format varies         Output format is consistent
Hard to audit                Easy to audit — you know exactly what ran
Great for one-off questions  Right for repeated, production workflows
```

**Skills do not replace tool chaining. They control it.**

### What a skill looks like

A skill is a markdown file — `SKILL.md` — with two parts:

```
---
name: vendor-health
description: Check the health of a specific vendor. Use when the user asks
             about a single vendor's status, risk, or invoice history.
---

You are a procurement analyst.

Follow these steps EXACTLY:

1. Query the database for the vendor's details (risk_rating, payment_terms)
2. Query the database for their open purchase orders
3. Query the database for any overdue invoices
4. Search the knowledge base for the high-risk vendor policy

Then write a report with:
## Vendor Profile
## Open Orders
## Overdue Invoices
## Policy Notes
## Risk Assessment
```

Two parts:
- **Frontmatter** (`---`) — name and description. The description is the routing signal.
- **Body** — the fixed steps Claude must follow. This becomes the system prompt.

### How a skill runs

```
Goal: "Check the health of Eastern Parts Corp"
       ↓
Skill body loaded → injected as system prompt
       ↓
Claude follows steps 1, 2, 3, 4 — in that order — every time
       ↓
Same report structure — every time
```

Claude is no longer deciding what to do. It is following your instructions.

### Skill vs raw agent

| | Raw Agent | Skill |
|---|---|---|
| Steps | Claude decides every run | Fixed by you in SKILL.md |
| Output | Varies | Always the same structure |
| Use when | Exploration, one-off questions | Production, repeatable workflows |
| Auditability | Low | High — you know exactly what ran |

> **Pop Quiz:** "You run the same procurement audit every Monday. Should you use a raw agent or a skill?"
> - A) Raw agent — more flexible
> - B) Skill — fixed steps, consistent output
> - C) It doesn't matter
>
> Answer: B — repeatability and consistency are exactly what skills give you.

---

## 0:50 — Exercise 2: Build Your First Skill

> **Key points to land:**
> - Part A: raw agent — steps vary, may miss things
> - Part B: skill — exactly 4 steps, always, same output structure
> - The only difference is the system prompt — that IS the skill
> - A skill does not change the loop — it changes what Claude is told to do

```bash
python3 exercises/02-first-skill/exercise.py
```

**Part A** — no skill. The agent decides what to check. Watch which tool calls it makes.

**Part B** — with skill. The skill forces exactly 4 steps. Count them. Same structure every time.

### What is actually happening

Both parts run the exact same agent loop. The only difference is the `system` parameter:

```python
# Part A — no skill
client.messages.create(
    system="You are a procurement analyst. Use tools to answer.",
    ...
)

# Part B — with skill
client.messages.create(
    system=VENDOR_HEALTH_SKILL,  # ← the skill body goes here
    ...
)
```

The skill body is just a string. When Claude reads it as the system prompt, it follows the numbered steps instead of deciding for itself. That is the entire mechanism — there is no special "skill mode" in the API.

### Why Part A misses the policy check

Part A's answer looks good — it found the overdue invoice, listed the POs, flagged the high-risk rating. Claude is not dumb. It wrote smart SQL and got real data.

But it never called `search_knowledge_base`. So it never read `data/policies/high-risk-vendor-policy.txt`, which contains: *"Payment terms cannot exceed 30 days for High-risk vendors."* The database only stores the 45-day terms — it has no rule that says that's a violation. That rule lives in the policy file. Without step 4, Claude never sees it, never makes the comparison, never flags the issue.

The skill is not about making Claude smarter. It is about making step 4 non-negotiable.

```
Part A — 2 tool calls (missed policy):        Part B — 4 tool calls (skill):
  query_database (vendor details)               query_database (vendor details)
  query_database (invoices)                     query_database (open POs)
  ✗ no policy check                             query_database (overdue invoices)
                                                search_knowledge_base ← catches the violation
```

The compliance issue — 45-day payment terms on a high-risk vendor — only surfaces in Part B.

> **Important:** In this exercise we hardcoded the skill — the code explicitly loads `skills/vendor-health/SKILL.md` and uses it. There is no routing. We told the code exactly which skill to use. Exercise 4 is where the router LLM reads all skills and picks the right one automatically based on the goal.

> **Presenter note:** 30 minutes. After Part A, ask: "did it check policy?" Then run Part B. Point to the compliance violation in the Part B output — that is what a raw agent would have missed. Then say: "we hardcoded this skill — Exercise 4 is where the routing happens automatically."

---

## 1:30 — Part 3: When is a Skill Overkill?

> **Key points to land:**
> - A skill removes the agent's freedom — freedom means no guarantees
> - Without a skill you cannot prove the policy check ran — with a skill you can
> - Auditability is the production argument for skills, not just consistency
> - Overkill = adding that guarantee when you don't need it

### What Anthropic says

From Anthropic's guide on building effective agents:

> "Workflows offer predictability and consistency for well-defined tasks, whereas agents are the better option when flexibility and model-driven decision-making are needed."

> "Find the simplest solution possible, and only increase complexity when needed."

A skill IS a workflow — it fixes the steps and removes the agent's freedom to decide. That is exactly what you want when you need to guarantee a step ran. It is exactly what you do NOT need for a one-off question.

### The real production argument: auditability

Predictability is the surface benefit. The deeper reason skills exist in production is **auditability**.

Without a skill:
> "Did the vendor health report check policy compliance?"
> "I think so — the agent usually does."

With a skill:
> "Did the vendor health report check policy compliance?"
> "Yes. Step 4 is the policy check. It cannot be skipped."

Your compliance team, your CFO, your auditor — they do not accept "I think so." A skill lets you say exactly what ran, every time.

### When to use what

```
Use a raw agent when:
  ✓ The task is exploratory or one-off
  ✓ One or two tool calls answer the question
  ✓ You need flexibility — steps should adapt to the question

Use a skill when:
  ✓ Multiple steps must always happen in the same order
  ✓ The output format must be consistent every time
  ✓ You need to prove what ran — compliance, audit, production
  ✓ The same workflow runs repeatedly

A skill is overkill when:
  ✗ One tool call answers the question
  ✗ You're packaging for the sake of it
  ✗ Nobody needs to audit what ran
```

> **Pop Quiz:** "When is a skill overkill?"
> - A) When the workflow has more than 3 steps
> - B) When a single tool call answers the question and nobody needs to audit it
> - C) When you're using more than one tool
>
> Answer: B — Anthropic's principle: find the simplest solution. If one tool call solves it and auditability is not a requirement, a skill adds complexity with no benefit.

---

## 1:45 — Exercise 3: When is a Skill Overkill?

> **Key points to land:**
> - A skill forces ALL its steps — even when the question doesn't need them
> - Simple question + skill = wasted tool calls, no extra value
> - The direct approach wins for simple questions — one call, same answer
> - A skill is only worth it when ALL the steps are needed every time

```bash
python3 exercises/03-routing/exercise.py
```

One simple question: **"What is the risk rating of Eastern Parts Corp?"**

- **With skill** — forces all 4 vendor-health steps every time
- **Direct** — one `query_database` call, done

Watch the tool call count. The direct approach gets the same answer in one call. The skill ran 3 extra steps that added nothing for this question.

**Verify it yourself** — the answer was always just a column in the database:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/erp.db')
rows = conn.execute('SELECT * FROM vendors LIMIT 5').fetchall()
cols = [d[0] for d in conn.execute('SELECT * FROM vendors LIMIT 0').description]
print(' | '.join(cols))
for r in rows: print(' | '.join(str(v) for v in r))
"
```

Look at the `risk_rating` column — it's right there. No policy lookup needed. No invoice check. One `SELECT` was always enough.

After running, ask the room: "So when WOULD you use the skill?" → When you need all 4 steps — the full health check with policy compliance. Not for a simple lookup.

> **Presenter note:** 25 minutes. After running, discuss: what's the right heuristic? Build the rule with the room — multiple steps that must always happen = skill. One tool call, no audit = direct.

---

## 2:10 — Part 4: The Orchestrator-Workers Pattern

> **Key points to land:**
> - This is Anthropic's **orchestrator-workers** pattern — a central LLM delegates to worker LLMs
> - The orchestrator reads skill descriptions and routes the goal to the right skill (worker)
> - Each skill is a worker — it receives the goal and executes fixed steps
> - The description on each SKILL.md is the routing signal — same lesson as tool descriptions, one level up

### Anthropic's definition

From Anthropic's guide on building effective agents:

> "Orchestrator-workers: a central LLM that delegates to worker LLMs dynamically."

That is exactly what Exercise 4 builds:

```
Orchestrator LLM                    Worker (skill)
─────────────────────────────────────────────────────────
Reads goal                          Receives goal
Reads skill index (descriptions)    Follows fixed steps
Calls invoke_skill("vendor-health") Runs query_database × 3
                                    Runs search_knowledge_base
                                    Returns structured report
```

Two phases:
1. **Routing** — orchestrator LLM reads descriptions, picks the right skill
2. **Execution** — skill body becomes the worker's system prompt, runs with real tools

### The full picture

```
Goal: "Run a full procurement audit"
       ↓
Orchestrator scans skills/*/SKILL.md — builds index of names + descriptions
(workshop: rebuilt every run from disk — production: loaded once at startup from S3/Redis)
       ↓
Orchestrator LLM reads index, calls invoke_skill("procurement-audit")
       ↓
Worker starts: procurement-audit/SKILL.md body loaded as system prompt
Worker runs fixed steps with real tools — query_database, search_knowledge_base
       ↓
Structured report returned
```

### invoke_skill — a synthetic tool

`invoke_skill` is not a real tool — it never goes to a database or an API. It is just a signal to `orchestrator.py`. When the orchestrator LLM calls it, the code catches it, looks up the matching skill, loads its body, and runs `execute_skill()`. That's the entire mechanism:

```python
# orchestrator.py — what actually happens when invoke_skill is called
skill_name, reason = route(goal, skills)          # LLM picks the skill
skill = next(s for s in skills if s["name"] == skill_name)
answer = execute_skill(skill["body"], goal)        # worker runs with real tools
```

The orchestrator LLM never sees the skill body. It only sees names and descriptions.

### The description IS the routing signal

The orchestrator only sees the skill index — names and descriptions. Not the bodies.

```
Session 1:  tool descriptions  → route to the right TOOL
Session 2:  skill descriptions → route to the right SKILL (worker)
```

Change a description → change what gets routed there.

### Workshop vs production

```
Workshop                          Production
────────────────────────────────────────────────────────
Skills loaded from local files    Skills loaded from S3/Redis
One model for everything          Per-skill model config in frontmatter
No tenant scoping                 Per-tenant allowlists — which skills available
invoke_skill intercepted in code  invoke_skill intercepted by service layer
```

The pattern is identical. Production adds scale, multi-tenancy, and resilience.

> **Pop Quiz:** "What is the orchestrator's job?"
> - A) Run all the tool calls
> - B) Read skill descriptions and delegate to the right worker skill
> - C) Execute the fixed steps in the skill body
>
> Answer: B — the orchestrator delegates, it does not execute. The worker (skill) executes.

---

## 2:30 — Exercise 4: Orchestrator-Workers in Action

> **Key points to land:**
> - Watch the skill index — those are the descriptions the orchestrator reads
> - Each goal routes to a different worker skill — based entirely on description matching
> - The skill body is never shown to the orchestrator — only name and description
> - Add a new SKILL.md and it appears in the index automatically — no code change

```bash
# Terminal 1 — boot the orchestrator (keep this running)
python3 exercises/04-orchestration/orchestrator.py

# Terminal 2 — fire goals at it
python3 exercises/04-orchestration/client.py
```

Watch Terminal 1. The orchestrator boots, loads all skills into memory, and waits. When you run the client in Terminal 2, goals arrive one by one — the orchestrator routes each one and executes the right skill. Answers come back to Terminal 2.

### How it all connects

```
BOOT  (orchestrator.py starts — Terminal 1)
─────────────────────────────────────────────────────────────
skills/vendor-health/SKILL.md      ──┐
skills/overdue-report/SKILL.md     ──┼──▶  Skill Index (name + description only)
skills/procurement-audit/SKILL.md  ──┤     bodies stay on disk until needed
skills/my-first-skill/SKILL.md     ──┘

Listening on localhost:9999...

─────────────────────────────────────────────────────────────
GOAL ARRIVES  (client.py sends — Terminal 2)
─────────────────────────────────────────────────────────────

  "Check the health of vendor Eastern Parts Corp"
                        │
                        ▼
            ┌───────────────────────┐
            │   Orchestrator LLM    │  ← sees Skill Index + invoke_skill tool
            │                       │
            │  invoke_skill(        │
            │    "vendor-health"    │
            │  )                    │
            └───────────┬───────────┘
                        │  intercepted — never leaves the service
                        ▼
            ┌───────────────────────┐
            │   Worker LLM          │  ← system = vendor-health body
            │                       │
            │  Turn 1: tool_use     │  query_database × 3
            │  Turn 2: tool_use     │  search_knowledge_base
            │  Turn 3: end_turn     │  → structured report
            └───────────┬───────────┘
                        │
                        ▼
              answer sent back to client (Terminal 2)
```

### What is actually happening — multiple Claude calls per goal

For each goal the exercise makes at least **two API calls** — one to route, then one or more to execute:

**Call 1 — the router (always exactly one call)**

The orchestrator passes the prebuilt index to Claude as the system prompt, along with `invoke_skill`. Claude reads the goal, matches it to the best description, and calls `invoke_skill("vendor-health")`. One call, no loop.

**Call 2+ — the skill executor (one call per turn in the agent loop)**

The code loads `skills/vendor-health/SKILL.md`, strips the frontmatter, and uses the body as the system prompt for a full agent loop with real tools. Each tool_use turn is a separate API call — vendor-health needs 4 tool calls across multiple turns.

```
Goal: "Check the health of vendor Eastern Parts Corp"
       ↓
Router call (1 API call):
  system = skill index (names + descriptions only)
  tool   = invoke_skill
  Claude calls invoke_skill("vendor-health")
       ↓
Executor loop (multiple API calls):
  system = vendor-health skill body
  tools  = query_database, search_knowledge_base
  Turn 1: tool_use → query_database × 3
  Turn 2: tool_use → search_knowledge_base
  Turn 3: end_turn → full report
```

### Why the body is never shown to the router

The router only needs to pick the right skill — it does not need to know what the skill does step by step. Giving it the body would just add noise and cost tokens.

The body is loaded only when the skill is actually executed. This is why changing a description changes routing, but changing a body never does.

Three goals — each routes to a different skill:
1. "Check the health of vendor Eastern Parts Corp" → `vendor-health`
2. "Give me a report of all overdue invoices" → `overdue-report`
3. "Run a full procurement audit" → `procurement-audit`

### Try it yourself

Open `skills/my-first-skill/SKILL.md` — replace every `???`:

1. **description** — write exactly when this skill should be called
2. **steps** — one or two `query_database` or `search_knowledge_base` calls
3. **report section** — give it a heading

Add your goal to the goals list in `client.py`, restart both terminals. Your skill appears in the orchestrator's index automatically — no other code change needed.

> **Presenter note:** 20 minutes. After the demo, open `skills/vendor-health/SKILL.md` and change the description to something vague. Restart the orchestrator, run the client again — routing breaks. That moment lands the lesson harder than any explanation.

---

## 2:50 — Best Practices

> **Key points to land:**
> - Write descriptions like routing rules — specific, unambiguous
> - Skills for repeated workflows, raw tools for one-off questions
> - One skill, one job — don't build a skill that does everything

### Skill description best practices

**1. Say exactly when to use it**

```markdown
# Bad — too vague, could match anything
description: Helps with vendor questions

# Good — specific trigger condition
description: Check the health of a specific vendor — risk rating, open orders,
             overdue invoices, and policy notes. Use when the user asks about
             a single vendor's status or health.
```

**2. Say when NOT to use it**

```markdown
description: Generate a report of all overdue invoices grouped by vendor.
             Use when asked for overdue invoices or a payment overview
             ACROSS all vendors. Do NOT use for a single vendor — use
             vendor-health for that.
```

**3. Name skills as actions**

```
# Bad — sounds like a noun
vendor_data

# Good — clear action
check-vendor-health, generate-overdue-report, run-procurement-audit
```

### Skill body best practices

**1. Number the steps explicitly**

Claude follows numbered instructions reliably. Unnumbered prose is interpreted loosely.

```markdown
Follow these steps EXACTLY:

1. Query the database for overdue invoices grouped by vendor
2. Query the database for the risk rating of each vendor
3. Search the knowledge base for the late payment policy
```

**2. Fix the output format**

Tell Claude exactly what sections to produce:

```markdown
Then write a report with:
## Overdue Invoice Summary
## Vendor Risk Breakdown
## Policy Reminder
## Recommended Actions
```

**3. Keep it focused**

One skill, one workflow. If a skill does too much, split it.

### Agent loop best practices

**1. Always handle unexpected stop_reason**

```python
if response.stop_reason == "tool_use":
    # run the tool
elif response.stop_reason == "end_turn":
    # return the answer
else:
    return f"Unexpected stop reason: {response.stop_reason}"
```

**2. Return errors to Claude, not exceptions**

```python
def query_database(sql):
    try:
        # run query
    except Exception as e:
        return f"Database error: {e}"  # Claude reads this and recovers
        # NOT: raise e  ← this crashes the loop
```

---

## 2:55 — Wrap Up

### What you built today

```
data/erp.db                      — 10 vendors, 40 POs, 40 invoices
pipeline/tools.py                — query_database, search_knowledge_base

Exercise 1 — refresher           — agent loop recap, same two stop_reason values
Exercise 2 — first skill         — raw agent vs skill, same goal, different behaviour
Exercise 3 — skill overkill      — when a skill is too much, direct tool wins
Exercise 4 — orchestration       — router picks the right skill from descriptions

skills/vendor-health/SKILL.md    — single vendor health check
skills/overdue-report/SKILL.md   — all overdue invoices report
skills/procurement-audit/SKILL.md— full procurement audit
```

### Interview cheatsheet

| Question | Answer |
|---|---|
| "What is a skill?" | A SKILL.md file with fixed steps that become the system prompt — guarantees consistent, repeatable output |
| "When do you use a skill?" | When a workflow has multiple steps that must always happen in the same order with the same output format |
| "When is a skill overkill?" | When one tool call answers the question — packaging adds complexity with no benefit |
| "How does the router know which skill to call?" | It reads the description on each SKILL.md — same as tool descriptions, one level up |
| "What is invoke_skill?" | A synthetic tool — intercepted by the orchestration layer, never leaves it. Claude calls it to signal which skill to run |
| "How is this different from a raw agent?" | Raw agent decides steps every run. Skill follows fixed steps every run. Same loop underneath — only the system prompt changes |

### The full picture

```
Session 1 ✓   LLM → Tool → Loop → Agent
Session 2 ✓   Agent → Skill → Orchestration layer
```

```
Raw LLM call
  ↓ add tools
Tool-calling loop
  ↓ autonomous goal
Agent
  ↓ fix the steps
Skill
  ↓ route automatically
Orchestration layer
```

Each step adds one thing. Nothing is thrown away.

---
