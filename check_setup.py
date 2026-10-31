"""
check_setup.py — verify everything is ready before the workshop.

Run:  python check_setup.py
"""

import sys
import os

console_width = 60
print("=" * console_width)
print("  Agent Skills Workshop — Setup Check")
print("=" * console_width)

errors = []
warnings = []

# Python version
if sys.version_info < (3, 10):
    errors.append(f"Python 3.10+ required (you have {sys.version_info.major}.{sys.version_info.minor})")
else:
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}")

# Packages
missing = []
for pkg in ["anthropic", "dotenv", "rich"]:
    try:
        __import__(pkg)
        print(f"✓ {pkg}")
    except ImportError:
        missing.append(pkg)
        errors.append(f"Missing package: {pkg} — run: pip install -r requirements.txt")

# API key — verified against the API, not just checked for presence.
# override=True so .env wins over a stale ANTHROPIC_API_KEY exported by your shell.
if "dotenv" not in missing:
    from dotenv import load_dotenv
    load_dotenv(override=True)
api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key or api_key == "your-api-key-here":
    errors.append("ANTHROPIC_API_KEY not set — copy .env.example to .env and add your key")
elif "anthropic" in missing:
    print(f"⚠ ANTHROPIC_API_KEY set ({api_key[:8]}...) — not verified, anthropic is missing")
else:
    import anthropic
    try:
        anthropic.Anthropic(api_key=api_key, max_retries=1).models.list(limit=1)
        print(f"✓ ANTHROPIC_API_KEY valid ({api_key[:8]}...)")
    except anthropic.AuthenticationError:
        errors.append(
            f"ANTHROPIC_API_KEY rejected ({api_key[:8]}...) — the key is invalid or revoked. "
            "Get a fresh one at https://console.anthropic.com/settings/keys"
        )
    except anthropic.PermissionDeniedError:
        errors.append(f"ANTHROPIC_API_KEY ({api_key[:8]}...) lacks permission for this workspace")
    except anthropic.APIConnectionError:
        warnings.append("Could not reach the API to verify the key — check your network")
    except anthropic.APIStatusError as e:
        warnings.append(f"Could not verify the key — API returned {e.status_code}")

# Database
db_path = os.path.join(os.path.dirname(__file__), "data/erp.db")
if not os.path.exists(db_path):
    print("⚠ Database not found — seeding now...")
    import subprocess
    subprocess.run([sys.executable, "data/seed.py"])
else:
    print("✓ Database ready")

# Skills
skills_dir = os.path.join(os.path.dirname(__file__), "skills")
skill_count = sum(
    1 for d in os.listdir(skills_dir)
    if os.path.isfile(os.path.join(skills_dir, d, "SKILL.md"))
)
print(f"✓ {skill_count} skills found")

print("=" * console_width)
if warnings:
    for w in warnings:
        print(f"  ⚠ {w}")
if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
else:
    print("All good. Ready to start!")
