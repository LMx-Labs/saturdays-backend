#!/usr/bin/env python3
"""Script to create recurring monthly subscription plans directly on Razorpay
using your Razorpay Key ID and Key Secret.

Usage:
    python scripts/create_razorpay_plans.py --key-id rzp_live_XXXX --key-secret YYYY
    or:
    set RAZORPAY_KEY_ID=...
    set RAZORPAY_KEY_SECRET=...
    python scripts/create_razorpay_plans.py
"""

import argparse
import os
import sys
from pathlib import Path
import httpx

RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"

PLANS_TO_CREATE = [
    {
        "tier": "BASIC",
        "name": "Saturdays Platform — Campus Starter",
        "amount_inr": 999,
        "max_orders_per_day": 40,
        "description": "₹999/month, up to 40 orders/day, 7% commission, 7-day free trial",
    },
    {
        "tier": "PROFESSIONAL",
        "name": "Saturdays Platform — Growth Multi-Store",
        "amount_inr": 2499,
        "max_orders_per_day": 100,
        "description": "₹2,499/month, up to 100 orders/day, 5% commission, 7-day free trial",
    },
    {
        "tier": "ENTERPRISE",
        "name": "Saturdays Platform — Campus Franchise",
        "amount_inr": 4999,
        "max_orders_per_day": 200,
        "description": "₹4,999/month, up to 200 orders/day, 3.5% commission, 7-day free trial",
    },
]


def load_env_file(env_path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars


def save_env_file(env_path: Path, updates: dict[str, str]) -> None:
    existing_lines = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    written_keys = set()
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                written_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in written_keys:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Saturdays plans on Razorpay")
    parser.add_argument("--key-id", help="Razorpay Key ID (rzp_live_... or rzp_test_...)")
    parser.add_argument("--key-secret", help="Razorpay Key Secret")
    parser.add_argument("--webhook-secret", help="Razorpay Webhook Secret (optional)")
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parent.parent
    env_file = backend_dir / ".env"
    existing_env = load_env_file(env_file)

    key_id = (
        args.key_id
        or os.environ.get("RAZORPAY_KEY_ID")
        or existing_env.get("RAZORPAY_KEY_ID")
    )
    key_secret = (
        args.key_secret
        or os.environ.get("RAZORPAY_KEY_SECRET")
        or existing_env.get("RAZORPAY_KEY_SECRET")
    )

    if not key_id or not key_secret:
        print("\n❌ Razorpay API credentials not found!", file=sys.stderr)
        print("Please provide them via:", file=sys.stderr)
        print("  python scripts/create_razorpay_plans.py --key-id <KEY_ID> --key-secret <KEY_SECRET>\n", file=sys.stderr)
        sys.exit(1)

    key_id = key_id.strip()
    key_secret = key_secret.strip()

    print(f"\n🚀 Connecting to Razorpay API with Key ID: {key_id[:12]}...")

    created_plans: dict[str, str] = {}

    with httpx.Client(timeout=20.0) as client:
        # First verify authentication with Razorpay
        try:
            auth_check = client.get(f"{RAZORPAY_BASE_URL}/plans", auth=(key_id, key_secret), params={"count": 1})
            if auth_check.status_code == 401:
                print("❌ Authentication failed: Invalid Key ID or Key Secret.", file=sys.stderr)
                sys.exit(1)
            auth_check.raise_for_status()
            print("✅ Authentication successful! Account verified.")
        except Exception as e:
            print(f"❌ Failed to connect to Razorpay: {e}", file=sys.stderr)
            sys.exit(1)

        for plan_info in PLANS_TO_CREATE:
            tier = plan_info["tier"]
            name = plan_info["name"]
            amount_paise = plan_info["amount_inr"] * 100
            desc = plan_info["description"]

            payload = {
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": name,
                    "amount": amount_paise,
                    "currency": "INR",
                    "description": desc,
                },
                "notes": {
                    "tier": tier,
                    "max_orders_per_day": str(plan_info["max_orders_per_day"]),
                    "platform": "saturdays",
                },
            }

            print(f"\n📦 Creating Plan: {name} (₹{plan_info['amount_inr']}/mo)...")
            try:
                resp = client.post(
                    f"{RAZORPAY_BASE_URL}/plans",
                    auth=(key_id, key_secret),
                    json=payload,
                )
                if not resp.is_success:
                    print(f"❌ Razorpay Error: {resp.status_code} - {resp.text}", file=sys.stderr)
                    continue

                data = resp.json()
                plan_id = data.get("id")
                created_plans[tier] = plan_id
                print(f"   ✓ Created successfully! Plan ID: {plan_id}")

            except Exception as exc:
                print(f"❌ Exception while creating plan {tier}: {exc}", file=sys.stderr)

    if not created_plans:
        print("\n❌ No plans were created. Please check errors above.", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 ALL PLANS CREATED ON RAZORPAY:")
    for tier, pid in created_plans.items():
        print(f"   • {tier}: {pid}")
    print("=" * 60)

    # Save to backend .env
    env_updates = {
        "RAZORPAY_KEY_ID": key_id,
        "RAZORPAY_KEY_SECRET": key_secret,
        "RAZORPAY_SIMULATE": "false",
    }
    if args.webhook_secret:
        env_updates["RAZORPAY_WEBHOOK_SECRET"] = args.webhook_secret.strip()

    if "BASIC" in created_plans:
        env_updates["RAZORPAY_PLAN_BASIC"] = created_plans["BASIC"]
    if "PROFESSIONAL" in created_plans:
        env_updates["RAZORPAY_PLAN_PROFESSIONAL"] = created_plans["PROFESSIONAL"]
    if "ENTERPRISE" in created_plans:
        env_updates["RAZORPAY_PLAN_ENTERPRISE"] = created_plans["ENTERPRISE"]

    save_env_file(env_file, env_updates)
    print(f"\n💾 Saved credentials & plan IDs to {env_file} with RAZORPAY_SIMULATE=false")
    print("✨ Your system is now live on Razorpay!")


if __name__ == "__main__":
    main()
