from __future__ import annotations

import logging
import re

from langchain_core.tools import tool

from src.integrations.google_sheets import append_order

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"^(0|\+84)[0-9]{9}$")


def _validate_phone(phone: str) -> bool:
    """Return True if *phone* matches a valid Vietnamese phone number format."""
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    return bool(_PHONE_RE.match(cleaned))


@tool
def create_order(
    customer_name: str,
    phone_number: str,
    product: str,
    note: str = "",
) -> str:
    """Save a customer order to Google Sheets after collecting their information.

    Call this tool ONLY after you have confirmed ALL required fields with the customer.
    Always validate the phone number format before calling.

    Args:
        customer_name: Full name of the customer (e.g., "Nguyễn Văn An").
        phone_number: Vietnamese phone number — 10 digits starting with 0
                      or +84 followed by 9 digits (e.g., "0901234567").
        product: Product(s) the customer wants to order or inquire about.
        note: Any additional notes (optional).

    Returns:
        Confirmation message to show the customer, or an error message if
        the phone number is invalid.
    """
    if not _validate_phone(phone_number):
        logger.warning("Invalid phone number format: %s", phone_number)
        return (
            f"❌ Số điện thoại '{phone_number}' không hợp lệ. "
            "Vui lòng nhập lại số điện thoại 10 chữ số (bắt đầu bằng 0)."
        )

    try:
        append_order(
            name=customer_name.strip(),
            phone=phone_number.strip(),
            product=product.strip(),
            note=note.strip(),
        )
        logger.info(
            "Order created — customer: %s, phone: %s, product: %s",
            customer_name,
            phone_number,
            product,
        )
        return (
            f"✅ Đơn hàng đã được ghi nhận thành công!\n\n"
            f"**Thông tin đơn hàng:**\n"
            f"- Tên: {customer_name}\n"
            f"- SĐT: {phone_number}\n"
            f"- Sản phẩm: {product}\n"
            f"{'- Ghi chú: ' + note if note else ''}\n\n"
            "Nhân viên TechGear sẽ liên hệ với bạn trong vòng **30 phút** "
            "(trong giờ làm việc 8:00–22:00). Cảm ơn bạn đã tin tưởng TechGear! 🙏"
        )
    except Exception as exc:
        logger.exception("Failed to save order to Google Sheets: %s", exc)
        return (
            "❌ Có lỗi xảy ra khi lưu đơn hàng. Vui lòng thử lại sau "
            "hoặc liên hệ hotline **1800-TECHGEAR** để được hỗ trợ."
        )
