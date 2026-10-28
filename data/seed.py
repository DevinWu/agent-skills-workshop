"""
data/seed.py — create and seed the ERP SQLite database.

Run once:  python data/seed.py
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "erp.db")


def seed():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE vendors (
        vendor_id      TEXT PRIMARY KEY,
        name           TEXT,
        country        TEXT,
        payment_terms  INTEGER,
        risk_rating    TEXT
    );

    CREATE TABLE purchase_orders (
        po_id       TEXT PRIMARY KEY,
        vendor_id   TEXT,
        material    TEXT,
        quantity    INTEGER,
        amount      REAL,
        date        TEXT,
        status      TEXT
    );

    CREATE TABLE invoices (
        invoice_id  TEXT PRIMARY KEY,
        po_id       TEXT,
        amount      REAL,
        due_date    TEXT,
        paid_date   TEXT,
        status      TEXT
    );
    """)

    vendors = [
        ("V001", "Apex Components Ltd",  "Germany", 30, "Low"),
        ("V002", "Bright Supply Co",     "USA",     45, "Low"),
        ("V003", "CoreTech Industries",  "India",   30, "Medium"),
        ("V004", "Delta Logistics GmbH", "Germany", 60, "Medium"),
        ("V005", "Eastern Parts Corp",   "China",   45, "High"),
        ("V006", "FastTrack Supplies",   "UK",      30, "Low"),
        ("V007", "Global Raw Materials", "Brazil",  60, "High"),
        ("V008", "Horizon Electronics",  "Japan",   30, "Low"),
        ("V009", "Inland Packaging Ltd", "USA",     30, "Medium"),
        ("V010", "JetStream Components", "Germany", 45, "Low"),
    ]
    c.executemany("INSERT INTO vendors VALUES (?,?,?,?,?)", vendors)

    random.seed(42)
    base_date = datetime(2024, 1, 1)
    materials = ["Steel Rods", "Circuit Boards", "Packaging Boxes", "Copper Wire", "LCD Screens"]
    pos = []
    for i in range(1, 41):
        po_id  = f"PO{i:03d}"
        vendor = random.choice(vendors)[0]
        mat    = random.choice(materials)
        qty    = random.randint(10, 500)
        amt    = round(qty * random.uniform(5, 200), 2)
        date   = (base_date + timedelta(days=random.randint(0, 270))).strftime("%Y-%m-%d")
        status = random.choice(["Open", "Open", "Closed", "Closed", "Cancelled"])
        pos.append((po_id, vendor, mat, qty, amt, date, status))
    c.executemany("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?)", pos)

    invoices = []
    for i, po in enumerate(pos, 1):
        po_id, vendor_id = po[0], po[1]
        vendor_terms = next(v[3] for v in vendors if v[0] == vendor_id)
        po_date = datetime.strptime(po[5], "%Y-%m-%d")
        due = (po_date + timedelta(days=vendor_terms)).strftime("%Y-%m-%d")
        paid_date = None
        status = "Pending"
        if po[6] == "Closed":
            roll = random.random()
            if roll < 0.7:
                paid_date = (po_date + timedelta(days=vendor_terms - random.randint(0, 5))).strftime("%Y-%m-%d")
                status = "Paid"
            elif roll < 0.85:
                paid_date = (po_date + timedelta(days=vendor_terms + random.randint(1, 30))).strftime("%Y-%m-%d")
                status = "Paid"
            else:
                status = "Overdue"
        invoices.append((f"INV{i:03d}", po_id, po[4], due, paid_date, status))
    c.executemany("INSERT INTO invoices VALUES (?,?,?,?,?,?)", invoices)

    conn.commit()
    conn.close()
    print(f"✓ Database seeded: {DB_PATH}")
    print(f"  {len(vendors)} vendors, {len(pos)} POs, {len(invoices)} invoices")


if __name__ == "__main__":
    seed()
