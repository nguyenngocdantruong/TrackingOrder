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
            res_data = response.json()

            if not res_data.get("success"):
                raise Exception("LEX API Error: Request was not successful")

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

                desc = status
                if provider:
                    desc += f" - {provider}"
                if location:
                    desc += f" @ {location}"

                events.append(TrackingEvent(
                    eventHash=event_hash,
                    code=status,
                    name=status,
                    descBuyer=desc,
                    descSeller=desc,
                    milestoneCode=0,
                    milestoneName=status,
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
