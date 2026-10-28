"""
pipeline/tools.py — two tools the agent can call.

  query_database        — run SQL against the ERP database
  search_knowledge_base — keyword search over procurement policy docs
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/erp.db")

POLICIES = [
    {
        "title": "Late Payment Policy",
        "text": "Invoices overdue by more than 30 days must be escalated to the finance team. A penalty of 2% per month applies. Vendors with 3+ overdue invoices are flagged for review.",
    },
    {
        "title": "High-Risk Vendor Policy",
        "text": "Vendors rated High risk require dual approval for any PO above $10,000. Quarterly audits are mandatory. Payment terms cannot exceed 30 days for High-risk vendors.",
    },
    {
        "title": "Vendor Onboarding Policy",
        "text": "New vendors must provide tax registration, insurance certificate, and bank details. A risk assessment is conducted before the first PO is raised. Onboarding takes 5-10 business days.",
    },
    {
        "title": "Three-Way Match Process",
        "text": "All invoices must be matched against the PO and goods receipt before payment. Mismatches above 5% are held for manual review. Automatic payment runs every Friday.",
    },
]


# ── Tool 1: Query Database ────────────────────────────────────────────────

def query_database(sql: str) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if not sql.strip().upper().startswith("SELECT"):
            return "Error: only SELECT queries are allowed."
        c.execute(sql)
        rows = c.fetchall()
        conn.close()
        if not rows:
            return "No results found."
        headers = rows[0].keys()
        lines = [" | ".join(str(h) for h in headers)]
        lines.append("-" * len(lines[0]))
        for row in rows[:20]:
            lines.append(" | ".join(str(row[h]) for h in headers))
        if len(rows) > 20:
            lines.append(f"... ({len(rows) - 20} more rows)")
        return "\n".join(lines)
    except Exception as e:
        return f"Database error: {e}"


QUERY_DATABASE_SCHEMA = {
    "name": "query_database",
    "description": """Query the ERP procurement database.
Use for questions about purchase orders, vendors, invoices, amounts, counts, status.

Tables:
  vendors         (vendor_id, name, country, payment_terms, risk_rating)
  purchase_orders (po_id, vendor_id, material, quantity, amount, date, status)
  invoices        (invoice_id, po_id, amount, due_date, paid_date, status)

Status values: 'Open', 'Closed', 'Cancelled', 'Paid', 'Overdue', 'Pending'
Risk values:   'Low', 'Medium', 'High'""",
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "A valid SQL SELECT statement"}
        },
        "required": ["sql"],
    },
}


# ── Tool 2: Search Knowledge Base ─────────────────────────────────────────

def search_knowledge_base(query: str) -> str:
    query_lower = query.lower()
    results = []
    for doc in POLICIES:
        if any(word in doc["title"].lower() or word in doc["text"].lower()
               for word in query_lower.split()):
            results.append(f"[{doc['title']}]\n{doc['text']}")
    if not results:
        return "No relevant policy found."
    return "\n\n---\n\n".join(results[:2])


SEARCH_KB_SCHEMA = {
    "name": "search_knowledge_base",
    "description": """Search internal procurement policy documents.
Use for questions about policies, rules, procedures, payment terms, vendor requirements.

Examples:
  - 'What is our late payment policy?'
  - 'What are the rules for high-risk vendors?'
  - 'How does vendor onboarding work?'""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"}
        },
        "required": ["query"],
    },
}


# ── Dispatch ──────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "query_database":      query_database,
    "search_knowledge_base": search_knowledge_base,
}

ALL_TOOLS = [QUERY_DATABASE_SCHEMA, SEARCH_KB_SCHEMA]


def run_tool(name: str, inputs: dict) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    return fn(**inputs)
