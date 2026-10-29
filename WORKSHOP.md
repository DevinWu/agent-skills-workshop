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

Four policy documents in `pipeline/tools.py`:
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

### What is actually happening

When you call `client.messages.create(...)`, Claude reads your question and decides it cannot answer from memory — it needs data. It responds with `stop_reason = "tool_use"` and a list of tool calls it wants to make.

Your loop intercepts this. It runs each tool, collects the results, and sends them back to Claude in the next message. Claude reads the results and now has what it needs to answer — so it responds with `stop_reason = "end_turn"` and the actual text.

Step by step:

```
Your code                         Claude
──────────────────────────────────────────────────────────
send question
                                  "I need the database"
                                  stop_reason = "tool_use"
                                  tool_use: query_database(...)
                                  tool_use: search_knowledge_base(...)
run query_database(...)
run search_knowledge_base(...)
send tool results back
                                  reads the results
                                  "Now I can answer"
                                  stop_reason = "end_turn"
                                  text: "There are 3 overdue invoices..."
return the answer
```

Two things to notice:
1. **Both tools fired in a single loop turn.** Claude requested them together — your code ran them both and sent both results back at once.
2. **Claude never touched the database directly.** It asked your code to run the query. Your code is the only thing that touches real systems.

### Why stop_reason matters

```python
if response.stop_reason == "tool_use":
    # Claude is not done — run the tools and loop again
elif response.stop_reason == "end_turn":
    # Claude is done — extract the text and return it
```

If you forget to check `stop_reason` and just return the response immediately, you get Claude's tool request back — not an answer. The loop exists entirely to handle `tool_use` turns until Claude reaches `end_turn`.

> **Presenter note:** 15 minutes. Show the output, walk through the step-by-step diagram, then ask: "what happens if stop_reason is tool_use and we just return immediately?" Let someone answer before moving on.

---

## 0:30 — Part 2: What is a Skill?

> **Key points to land:**
> - A raw agent decides its steps fresh every run — output varies
> - A skill fixes the steps in a SKILL.md file — same output every time
> - The skill body becomes the system prompt — Claude follows it like instructions
> - Skills are for repeatable, auditable workflows

### The problem with a raw agent

A raw agent is powerful but unpredictable:

```
Goal: "Check the health of vendor Eastern Parts Corp"

Run 1:  query risk rating → check invoices → answer
Run 2:  check POs → query risk → look up policy → answer  (different order)
Run 3:  query risk rating → answer  (skipped steps)
```

Three runs, three different behaviours. No guarantee of consistency.

If this is a report that goes to your CFO every Monday — you need the same sections every time.

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

Part A's system prompt says "use tools to answer." Claude decides what's relevant. For a vendor health question, it queries the database — but it may not think to search policy documents unless explicitly told.

Part B's system prompt says "follow these 4 steps EXACTLY" — step 4 is the policy search. Claude has no choice. The policy check happens every single time.

```
Part A — 2 tool calls (missed policy):        Part B — 4 tool calls (skill):
  query_database (vendor details)               query_database (vendor details)
  query_database (invoices)                     query_database (open POs)
  ✗ no policy check                             query_database (overdue invoices)
                                                search_knowledge_base ← catches the violation
```

The compliance issue — 45-day payment terms on a high-risk vendor — only surfaces in Part B.

> **Presenter note:** 30 minutes. After Part A, ask: "did it check policy?" Then run Part B. Point to the compliance violation in the Part B output — that is what a raw agent would have missed. Then show the `VENDOR_HEALTH_SKILL` string in the code and say: "this string is the skill."

---

## 1:30 — Part 3: When is a Skill Overkill?

> **Key points to land:**
> - Not everything needs a skill
> - A simple question with one tool call does not need a skill
> - Packaging for the sake of it adds complexity with no benefit
> - The test: does this workflow have multiple steps that must always happen?

### The overkill test

Ask yourself three questions before building a skill:

```
1. Does this require multiple steps that must always happen?
2. Does the output format need to be consistent every time?
3. Will this same workflow run repeatedly?
```

If any answer is **no** — a skill is probably overkill.

### The vendor-health skill — overkill for a simple question

The vendor-health skill runs 4 steps:
1. Query vendor details
2. Query open POs
3. Query overdue invoices
4. Search policy

That makes sense for a full health check.

But if the question is simply **"What is the risk rating of Eastern Parts Corp?"** — you only need step 1. The skill forces 3 unnecessary steps.

```
Question: "What is the risk rating of Eastern Parts Corp?"

With skill:   4 tool calls, full report — overkill
Without skill: 1 tool call, direct answer — correct
```

### When to use what

```
Use a raw tool call when:
  ✓ One tool call answers the question
  ✓ The steps don't need to be fixed
  ✓ You're answering a one-off question

Use a skill when:
  ✓ Multiple steps must always happen
  ✓ The output must be consistent
  ✓ The same workflow runs repeatedly
  ✓ You need auditability — you can prove what ran

A skill is overkill when:
  ✗ One tool call answers the question
  ✗ You're packaging for packaging's sake
  ✗ The workflow is exploratory and changes every time
```

> **Pop Quiz:** "When is a skill overkill?"
> - A) When the workflow has more than 3 steps
> - B) When a single tool call answers the question
> - C) When you're using more than one tool
>
> Answer: B — if one tool call solves it, the overhead of a skill adds nothing.

---

## 1:45 — Exercise 3: Skill vs No Skill

> **Key points to land:**
> - Same simple question, two approaches — skill vs direct
> - The skill ran 4 steps for a 1-step question
> - Direct was faster and more appropriate
> - The lesson: match the tool to the task

```bash
python3 exercises/03-routing/exercise.py
```

One question: **"What is the risk rating of Eastern Parts Corp?"**

- **With skill** — runs the full 4-step vendor-health workflow
- **Without skill** — one direct tool call, direct answer

Compare the number of tool calls and the time. The direct approach wins here.

After running, ask: for which question WOULD you use the vendor-health skill? → "Give me a full health check on Eastern Parts Corp" — that warrants all 4 steps.

> **Presenter note:** 25 minutes. After running, discuss: what's the right heuristic for when to package something as a skill? Build this list with the room.

---

## 2:10 — Part 4: The Orchestration Layer

> **Key points to land:**
> - The orchestration layer routes a goal to the right skill automatically
> - It reads skill descriptions — not bodies — to decide
> - The description on each SKILL.md is the routing signal
> - This is the same routing lesson as tool descriptions in Session 1, one level up

### What the orchestration layer does

```
Goal: "Run a full procurement audit"
       ↓
Orchestration layer scans skills/*/SKILL.md
Builds a skill index:
  - vendor-health:     Check the health of a specific vendor...
  - overdue-report:    Generate a report of all overdue invoices...
  - procurement-audit: Run a full procurement health audit...
       ↓
Router LLM reads the index, calls invoke_skill("procurement-audit")
       ↓
Orchestration layer loads procurement-audit/SKILL.md body
Injects it as the system prompt
       ↓
Skill runs with real tools — fixed steps, consistent output
```

Two phases:
1. **Routing** — router LLM reads descriptions, calls `invoke_skill`
2. **Execution** — skill body becomes system prompt, agent loop runs with real tools

### invoke_skill — a synthetic tool

`invoke_skill` is not a real tool. It never leaves the orchestration layer. When Claude calls it, the layer intercepts the call, loads the skill, and continues. Claude never knows this happened.

```
Claude calls: invoke_skill("procurement-audit")
               ↓
Orchestration layer intercepts
Loads skills/procurement-audit/SKILL.md
Sets body as system prompt
Continues the loop — Claude now follows skill instructions
```

### The description IS the routing signal

The orchestration layer gives the router LLM only the skill index — names and descriptions. Not the bodies. Claude reads descriptions and picks.

Change a description → change what gets routed there. This is the same lesson as tool descriptions in Session 1 — one level up.

```
Session 1:  tool descriptions  → route to the right TOOL
Session 2:  skill descriptions → route to the right SKILL
```

### How production orchestration services work

What you build in Exercise 4 is a faithful simplification of how real orchestration services work:

```
Workshop                          Production
────────────────────────────────────────────────────────
Skills loaded from local files    Skills loaded from S3/Redis
One model for everything          Per-skill model config in frontmatter
No tenant scoping                 Per-tenant allowlists — which skills are available
invoke_skill intercepted in code  invoke_skill intercepted by the service layer
```

The pattern is the same. The production version adds scale, multi-tenancy, and resilience.

> **Pop Quiz:** "How does the router know which skill to call?"
> - A) You hardcode the routing logic
> - B) It reads the description on each SKILL.md and picks the best match
> - C) It tries all skills and picks the best result
>
> Answer: B — same as tool descriptions in Session 1. The description is the only signal.

---

## 2:30 — Exercise 4: Orchestration in Action

> **Key points to land:**
> - Watch the skill index print — those are the descriptions the router reads
> - Each goal routes to a different skill — based entirely on description matching
> - The skill body is never shown to the router — only name and description
> - Add a new SKILL.md and it appears in the index automatically — no code change

```bash
python3 exercises/04-orchestration/exercise.py
```

### What is actually happening — two Claude calls per goal

For each goal the exercise makes **two separate API calls**:

**Call 1 — the router**

The code scans `skills/*/SKILL.md` and builds an index — just names and descriptions, no bodies:

```
- vendor-health:      Check the health of a specific vendor...
- overdue-report:     Generate a report of all overdue invoices...
- procurement-audit:  Run a full procurement health audit...
- my-first-skill:     ???
```

It gives this index to Claude as the system prompt, along with a synthetic tool called `invoke_skill`. Claude reads the goal, matches it to the best description, and calls `invoke_skill("vendor-health")`. That's it — one tool call, no loop needed.

**Call 2 — the skill executor**

The code loads `skills/vendor-health/SKILL.md`, strips the frontmatter, and uses the body as the system prompt for a full agent loop with real tools. Claude now follows the skill's fixed steps exactly as in Exercise 2.

```
Goal: "Check the health of vendor Eastern Parts Corp"
       ↓
Router call:
  system = skill index (names + descriptions only)
  tool   = invoke_skill
  Claude calls invoke_skill("vendor-health")
       ↓
Executor call:
  system = vendor-health skill body
  tools  = query_database, search_knowledge_base
  Claude follows 4 fixed steps → full report
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

Add your goal to the list in the exercise file, run again. Your skill appears in the index and gets routed to — no code change needed.

> **Presenter note:** 20 minutes. After running, open `skills/vendor-health/SKILL.md` and change the description to something vague. Run again — routing breaks. That moment lands the lesson harder than any explanation.

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
