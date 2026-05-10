"""
Test script to verify external service connections before starting the server.

Usage:
    python scripts/test_connections.py           # test all
    python scripts/test_connections.py --sheets  # test Google Sheets only
    python scripts/test_connections.py --telegram # test Telegram only
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def _skip(msg: str) -> None:
    print(f"  ⚠️  {msg}")


# ── Google Sheets ─────────────────────────────────────────────────────────────

def test_google_sheets() -> bool:
    print("\n📊 Google Sheets")
    settings = get_settings()

    if not settings.google_service_account_json:
        _skip("GOOGLE_SERVICE_ACCOUNT_JSON is empty — skipping")
        return False
    if not settings.google_sheet_id:
        _skip("GOOGLE_SHEET_ID is empty — skipping")
        return False

    # Validate JSON structure
    try:
        info = json.loads(settings.google_service_account_json)
        required_keys = {"type", "project_id", "private_key", "client_email"}
        missing = required_keys - info.keys()
        if missing:
            _fail(f"Service account JSON missing keys: {missing}")
            return False
        _ok(f"Service account JSON valid (client_email: {info['client_email']})")
    except json.JSONDecodeError as exc:
        _fail(f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {exc}")
        return False

    # Try authenticating and opening the sheet
    try:
        from src.integrations.google_sheets import _get_worksheet
        worksheet = _get_worksheet()
        sheet_title = worksheet.spreadsheet.title
        _ok(f"Authenticated successfully")
        _ok(f"Sheet opened: '{sheet_title}' (ID: {settings.google_sheet_id})")
        _ok(f"Worksheet: '{worksheet.title}' — {worksheet.row_count} rows")
        return True
    except Exception as exc:
        _fail(f"Connection failed: {exc}")
        print()
        print("     Common causes:")
        print("     • Service account not shared on the Google Sheet")
        print(f"     • Share the sheet with: {info.get('client_email', '?')}")
        print("     • Google Sheets API not enabled in the project")
        return False


# ── Telegram ─────────────────────────────────────────────────────────────────

async def _test_telegram_async() -> bool:
    import httpx
    settings = get_settings()

    if not settings.telegram_bot_token or settings.telegram_bot_token == "your-telegram-bot-token":
        _skip("TELEGRAM_BOT_TOKEN not configured — skipping")
        return False

    token = settings.telegram_bot_token
    base = f"https://api.telegram.org/bot{token}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # getMe
        try:
            resp = await client.get(f"{base}/getMe")
            data = resp.json()
            if not data.get("ok"):
                _fail(f"getMe failed: {data.get('description', data)}")
                return False
            bot = data["result"]
            _ok(f"Bot authenticated: @{bot['username']} (id: {bot['id']})")
        except Exception as exc:
            _fail(f"Cannot reach Telegram API: {exc}")
            return False

        # getWebhookInfo
        try:
            resp = await client.get(f"{base}/getWebhookInfo")
            info = resp.json().get("result", {})
            url = info.get("url", "")
            if url:
                _ok(f"Webhook registered: {url}")
                pending = info.get("pending_update_count", 0)
                if pending:
                    _ok(f"Pending updates in queue: {pending}")
                last_err = info.get("last_error_message")
                if last_err:
                    _fail(f"Last webhook error: {last_err}")
            else:
                _skip("No webhook registered yet — start the server to register")
        except Exception as exc:
            _fail(f"getWebhookInfo failed: {exc}")

    return True


def test_telegram() -> bool:
    print("\n📱 Telegram Bot")
    return asyncio.run(_test_telegram_async())


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Test external service connections")
    parser.add_argument("--sheets", action="store_true", help="Test Google Sheets only")
    parser.add_argument("--telegram", action="store_true", help="Test Telegram only")
    args = parser.parse_args()

    run_all = not args.sheets and not args.telegram

    results: list[bool] = []

    if run_all or args.sheets:
        results.append(test_google_sheets())

    if run_all or args.telegram:
        results.append(test_telegram())

    print()
    if all(r is not False for r in results):
        print("✅ All configured connections OK")
    else:
        failures = sum(1 for r in results if r is False)
        print(f"⚠️  {failures} connection(s) failed — check messages above")
        sys.exit(1)


if __name__ == "__main__":
    main()
