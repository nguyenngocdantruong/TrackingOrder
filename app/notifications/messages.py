"""Readable Telegram notification formatting shared by live and test messages."""
from html import escape

from app.tracking.stages import STAGE_LABELS


STAGE_ICONS = {
    'preparing': '📝',
    'picked_up': '📥',
    'in_transit': '🚚',
    'at_delivery_station': '🏢',
    'out_for_delivery': '🛵',
    'delivered': '🎉',
}


def _escaped(value, limit):
    return escape(str(value or '')[:limit])


def format_shipment_notification(*, stage, tracking_name, tracking_number,
                                 carrier, occurred_at, event_name, details,
                                 completed=False, status_label=None):
    """Render Telegram HTML with escaped provider/user supplied values."""
    icon = STAGE_ICONS.get(stage, '📦')
    label = status_label or STAGE_LABELS.get(stage, 'Cập nhật vận đơn')
    lines = [
        f"{icon} <b>CẬP NHẬT VẬN ĐƠN</b>",
        f"📦 <b>{_escaped(tracking_name or tracking_number, 100)}</b>",
        f"🔢 Mã vận đơn: <code>{_escaped(tracking_number, 100)}</code>",
        f"🏷 Đơn vị: {_escaped(carrier, 80)}",
        '',
        f"📍 <b>Trạng thái: {_escaped(label, 160)}</b>",
        f"🕒 Thời gian: {_escaped(occurred_at, 100)}",
    ]
    if event_name:
        lines.append(f"📋 Sự kiện: {_escaped(event_name, 200)}")
    if details:
        lines.extend(['', f"ℹ️ {_escaped(details, 1200)}"])
    if completed:
        lines.extend(['', '🏁 <b>Đơn hàng đã hoàn tất. Ngừng theo dõi.</b>'])
    return '\n'.join(lines)


def build_test_shipment_notification(stage):
    """Create an explicitly synthetic message for the admin test control."""
    return format_shipment_notification(
        stage=stage,
        tracking_name='Đơn hàng thử nghiệm',
        tracking_number='TEST-2026-0001',
        carrier='Nhà vận chuyển mẫu',
        occurred_at='20/11/2026 12:00 UTC',
        event_name='Sự kiện minh họa',
        details='Đây là tin nhắn thử nghiệm từ trang quản trị. Không phải vận đơn thật.',
        completed=stage == 'delivered',
    )
