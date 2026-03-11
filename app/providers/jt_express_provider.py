import hashlib
import html
import re
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

import requests

from app.providers.base import CarrierProvider, TrackingEvent, TrackingResult


class JTExpressProvider(CarrierProvider):
    _TRACKING_PATTERN = re.compile(r"^(?P<bill>[A-Za-z0-9]+)-(?P<phone>\d{4})$")

    @property
    def id(self) -> str:
        return "jt_express"

    @property
    def displayName(self) -> str:
        return "J&T Express"

    def supports(self, tracking_number: str) -> bool:
        if not tracking_number:
            return False
        return bool(self._TRACKING_PATTERN.match(tracking_number.strip()))

    def _split_tracking_input(self, tracking_number: str) -> Tuple[str, str]:
        match = self._TRACKING_PATTERN.match((tracking_number or "").strip())
        if not match:
            raise Exception("Mã J&T không hợp lệ. Định dạng đúng: <ma-van-don>-<4-so-cuoi-sdt> (ví dụ: 842594172358-9880).")
        return match.group("bill"), match.group("phone")

    def _parse_event_time(self, date_text: str, time_text: str) -> datetime:
        # J&T page shows local VN time, parse as GMT+7
        local_tz = timezone(timedelta(hours=7))
        date_text = (date_text or "").strip()
        time_text = (time_text or "").strip()

        if not date_text and not time_text:
            return datetime.now(local_tz)

        if not date_text:
            date_text = datetime.now(local_tz).strftime("%Y-%m-%d")
        if not time_text:
            time_text = "00:00:00"

        try:
            parsed = datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")
            return parsed.replace(tzinfo=local_tz)
        except ValueError:
            return datetime.now(local_tz)

    def _status_from_description(self, description: str) -> Tuple[str, str, int, str]:
        text = (description or "").lower()

        if any(k in text for k in ["đã giao", "giao thành công", "phát thành công", "delivered"]):
            return "DELIVERED", "Đã giao", 980, "Completed"
        if any(k in text for k in ["đã hủy", "hủy", "hoàn hàng", "cancel"]):
            return "CANCELLED", "Đã hủy", 990, "Cancelled"
        if any(k in text for k in ["đang chuyển", "đã được chuyển", "về hub", "rời hub", "trung chuyển"]):
            return "IN_TRANSIT", "Đang vận chuyển", 300, "In Transit"
        if any(k in text for k in ["đã nhận hàng", "tiếp nhận", "đăng ký"]):
            return "PICKED_UP", "Đã nhận hàng", 200, "Picked Up"

        return "PROCESSING", "Đang xử lý", 100, "Processing"

    def track(self, tracking_number: str) -> TrackingResult:
        bill_code, cellphone = self._split_tracking_input(tracking_number)
        url = "https://jtexpress.vn/vi/tracking"
        params = {
            "type": "track",
            "billcode": bill_code,
            "cellphone": cellphone,
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://jtexpress.vn/vi/tracking?type=track",
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
        except Exception as e:
            raise Exception(f"Không thể kết nối J&T Express: {str(e)}")

        response_text = response.text

        if "tab-content" not in response_text:
            raise Exception("Không tìm thấy dữ liệu vận đơn J&T (có thể sai mã vận đơn hoặc 4 số cuối SĐT).")

        item_pattern = re.compile(
            r'<div class="result-vandon-item[^>]*>\s*'
            r'<div class="flex flex-col[^>]*>.*?name="time-outline".*?<span[^>]*>\s*(?P<time>[^<]+)\s*</span>.*?'
            r'name="calendar-clear-outline".*?<span[^>]*>\s*(?P<date>[^<]+)\s*</span>.*?</div>\s*'
            r'<div>\s*(?P<desc>.*?)\s*</div>\s*</div>',
            re.S,
        )

        rows = list(item_pattern.finditer(response_text))
        if not rows:
            raise Exception("Không tìm thấy lịch sử vận đơn J&T")

        events: List[TrackingEvent] = []
        for idx, row in enumerate(rows):
            time_text = row.group("time").strip()
            date_text = row.group("date").strip()
            description_html = row.group("desc")
            description = re.sub(r"<[^>]+>", " ", description_html)
            description = html.unescape(re.sub(r"\s+", " ", description)).strip()

            event_time = self._parse_event_time(
                date_text,
                time_text,
            )

            code, name, milestone_code, milestone_name = self._status_from_description(description)
            raw_str = f"{bill_code}{cellphone}{idx}{event_time.isoformat()}{description}"
            event_hash = hashlib.md5(raw_str.encode("utf-8")).hexdigest()

            events.append(
                TrackingEvent(
                    eventHash=event_hash,
                    code=code,
                    name=name,
                    descBuyer=description,
                    descSeller=description,
                    milestoneCode=milestone_code,
                    milestoneName=milestone_name,
                    actualTime=event_time,
                    currentLocation=None,
                    nextLocation=None,
                    raw={
                        "date": date_text,
                        "time": time_text,
                        "description": description,
                    },
                )
            )

        events.sort(key=lambda x: x.actualTime, reverse=True)
        latest = events[0]

        return TrackingResult(
            trackingNumber=tracking_number,
            carrierId=self.id,
            currentStatus=latest.name,
            lastEventTime=latest.actualTime,
            events=events,
        )

    def is_final_status(self, events: List[TrackingEvent]) -> bool:
        if not events:
            return False

        final_codes = {"DELIVERED", "CANCELLED"}
        for event in events:
            if event.code in final_codes:
                return True
        return False

    def format_time(self, dt: datetime) -> str:
        if not dt:
            return "N/A"

        vn_tz = timezone(timedelta(hours=7))
        if dt.tzinfo is None:
            local_dt = dt.replace(tzinfo=vn_tz)
        else:
            local_dt = dt.astimezone(vn_tz)

        return local_dt.strftime("%H:%M %d/%m/%Y")
