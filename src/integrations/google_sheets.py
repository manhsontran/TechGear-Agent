from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache

import gspread
from google.oauth2.service_account import Credentials

from src.config import get_settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Column headers — must match the sheet's first row exactly
HEADERS = ["Timestamp", "Tên KH", "SĐT", "Sản phẩm", "Ghi chú", "Trạng thái"]


@lru_cache(maxsize=1)
def _get_worksheet() -> gspread.Worksheet:
    """Build authenticated gspread client and return the first worksheet."""
    settings = get_settings()

    if not settings.google_service_account_json:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set. "
            "Please provide a service account JSON string in your .env file."
        )

    service_account_info = json.loads(settings.google_service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(creds)

    spreadsheet = client.open_by_key(settings.google_sheet_id)
    worksheet = spreadsheet.sheet1

    # Ensure header row exists
    existing_values = worksheet.row_values(1)
    if existing_values != HEADERS:
        worksheet.insert_row(HEADERS, index=1)
        logger.info("Initialized Google Sheet header row.")

    return worksheet


def append_order(
    name: str,
    phone: str,
    product: str,
    note: str = "",
) -> None:
    """Append a new order row to the Google Sheet."""
    worksheet = _get_worksheet()
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    row = [timestamp, name, phone, product, note, "Mới"]
    worksheet.append_row(row, value_input_option="USER_ENTERED")
    logger.info(
        "Order appended to Google Sheet — Name: %s, Phone: %s, Product: %s",
        name,
        phone,
        product,
    )
