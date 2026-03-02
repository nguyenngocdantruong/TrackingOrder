import hashlib
from datetime import datetime, timezone, timedelta
from typing import List

import requests

from app.providers.base import CarrierProvider, TrackingResult, TrackingEvent, TrackingLocation


class LEXProvider(CarrierProvider):
    @property
    def id(self) -> str:
        return "lex"

    @property
    def displayName(self) -> str:
        return "LEX"

    def get_info_from_status(self, status: str) -> list:
        status = status.lower()

        STATUS_MAP = {
            "cb_pre_accept": [
                "Đang tiếp nhận",
                "LEX đã tiếp nhận đơn hàng của bạn và đang xử lý để đưa vào hệ thống vận chuyển."
            ],
            "cb_pre_delivering": [
                "Đơn hàng sắp đến kho trung chuyển",
                "Đơn hàng sắp đến kho trung chuyển"
            ],
            "cb_pre_sign": [
                "Đơn hàng đã đến kho trung chuyển",
                "Đơn hàng đã đến kho trung chuyển"
            ],
            "cb_ib_success_in_sort_center": [
                "Đơn hàng đã đến trung tâm trung chuyển",
                "Đơn hàng đã đến trung tâm trung chuyển"
            ],
            "cb_ob_success_in_sort_center": [
                "Đơn hàng đã rời khỏi trung tâm trung chuyển",
                "Đơn hàng đã rời trung tâm trung chuyển"
            ],
            "cb_handover": [
                "Đơn hàng đã đến cảng và đang chờ thông quan xuất khẩu",
                "Đơn hàng đã dến cảng và đang chờ thông quan xuất khẩu"
            ],
            "cb_uplifted": [
                "Đơn hàng đã được thông quan xuất khẩu và được nhập khẩu vào Việt Nam",
                "Đơn hàng đã được thông quan xuất khẩu và được nhập khẩu vào Việt Nam"
            ],
            "cb_submit_to_custom": [
                "Đơn hàng đã bàn giao cho đơn vị vận chuyển trong nước",
                "Đơn hàng đã bàn giao cho đơn vị vận chuyển trong nước"
            ],
            "domestic_delivered": [
                "Đã giao",
                "Kiện hàng của bạn đã được giao."
            ],
            "domestic_about_to_deliver": [
                "Kiện hàng sắp đến!",
                "Đơn vị vận chuyển sẽ giao hàng tới bạn trong khoảng 1 giờ tới. Hãy chú ý điện thoại giao hàng bạn nhé!"
            ],
            "domestic_out_for_delivery": [
                "Đang giao hàng",
                "LEX sẽ cố gắng giao đơn hàng của bạn hôm nay!"
            ],
            "domestic_package_stationed_out": [
                "Hàng Đã Rời Hub Giao Hàng",
                "Kiện hàng đã rời hub và đang vận chuyển tới địa chỉ nhận."
            ],
            "domestic_package_stationed_in": [
                "Hàng Đã Về Hub Giao Hàng",
                "Kiện hàng đã về Hub Giao Hàng và đang được xử lý để phát hàng."
            ],
            "domestic_ob_success_in_sort_center": [
                "Rời khỏi trung tâm phân phối logistics",
                "Đơn hàng của bạn đã rời khỏi trung tâm phân loại."
            ],
            "domestic_linehaul_packed": [
                "Đã Điều Phối Chuyến Trung Chuyển",
                "Kiện hàng của bạn đã được gom chuyến và xuất tuyến trung chuyển."
            ],
            "domestic_ib_success_in_sort_center": [
                "Hàng tới trung tâm phân loại",
                "Đơn hàng của bạn đã đến trung tâm phân loại của chúng tôi."
            ],
            "domestic_1st_attempt_failed": [
                "Giao Hàng Thất Bại Lần 1",
                "Chúng tôi sẽ lên lịch giao lại trong vài ngày tới."
            ]
        }

        return STATUS_MAP.get(status, [status, status])

    def supports(self, tracking_number: str) -> bool:
        return tracking_number.upper().startswith("LEX")

    def track(self, tracking_number: str) -> TrackingResult:
        url = "https://logistics.lazada.vn/api/get_package_history"
        payload = {
            "trackingNumber": tracking_number
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            
            try:
                res_data = response.json()
            except ValueError:
                raise Exception(f"LEX API returned invalid JSON. Status: {response.status_code}")

            if not res_data.get("success"):
                error_msg = res_data.get("error_msg") or res_data.get("message") or "Unknown error"
                raise Exception(f"LEX API Error: {error_msg}")

            data = res_data.get("data", {})
            timeline = data.get("timeline", [])

            events = []
            for t in timeline:
                process_time_ms = t.get("processTime")
                if process_time_ms:
                    actual_time = datetime.fromtimestamp(process_time_ms / 1000, timezone.utc)
                else:
                    actual_time = datetime.now(timezone.utc)

                status = t.get("status", "unknown")
                provider = t.get("shippingProvider", "")
                location = t.get("location", "")

                raw_str = f"{tracking_number}{status}{process_time_ms}{provider}{location}"
                event_hash = hashlib.md5(raw_str.encode()).hexdigest()

                current_location = None
                if location:
                    current_location = TrackingLocation(
                        name=location,
                        address=location,
                        lat=None,
                        lng=None
                    )

                desc = self.get_info_from_status(status)[1]
                if location:
                    desc += f" [{location}]"

                events.append(TrackingEvent(
                    eventHash=event_hash,
                    code=status,
                    name=self.get_info_from_status(status)[0],
                    descBuyer=desc,
                    descSeller=desc,
                    milestoneCode=0,
                    milestoneName=self.get_info_from_status(status)[0],
                    actualTime=actual_time,
                    currentLocation=current_location,
                    nextLocation=None,
                    raw=t
                ))

            # Sort events newest first
            events.sort(key=lambda x: x.actualTime, reverse=True)

            current_status = data.get("status", "Unknown")
            last_event_time = datetime.now(timezone.utc)
            if events:
                current_status = events[0].code or current_status
                current_status = self.get_info_from_status(current_status)[0]
                last_event_time = events[0].actualTime

            return TrackingResult(
                trackingNumber=tracking_number,
                carrierId=self.id,
                currentStatus=current_status,
                lastEventTime=last_event_time,
                events=events
            )

        except Exception as e:
            raise Exception(f"Failed to track LEX order: {str(e)}")

    def is_final_status(self, events: List[TrackingEvent]) -> bool:
        if not events:
            return False

        final_codes = ["domestic_delivered"]
        for event in events:
            if event.code in final_codes:
                return True
        return False

    def format_time(self, dt: datetime) -> str:
        if not dt:
            return "N/A"
        # LEX API timestamp is UTC milliseconds, convert to GMT+7
        if dt.tzinfo is None or dt.tzinfo == timezone.utc:
            local_dt = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7)))
        else:
            local_dt = dt.astimezone(timezone(timedelta(hours=7)))
        return local_dt.strftime("%H:%M %d/%m/%Y")
