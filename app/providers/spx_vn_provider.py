import requests
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List
from app.providers.base import CarrierProvider, TrackingResult, TrackingEvent, TrackingLocation

class SPXVNProvider(CarrierProvider):
    @property
    def id(self) -> str:
        return "shopee_express_vn"

    @property
    def displayName(self) -> str:
        return "Shopee Express VN"

    def supports(self, tracking_number: str) -> bool:
        return tracking_number.upper().startswith("SPXVN")

    def track(self, tracking_number: str) -> TrackingResult:
        url = "https://spx.vn/shipment/order/open/order/get_order_info"
        params = {
            "spx_tn": tracking_number,
            "language_code": "vi"
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://spx.vn/"
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            res_data = response.json()

            if res_data.get("retcode") != 0:
                raise Exception(f"SPX API Error: {res_data.get('message', 'Unknown error')}")

            data = res_data.get("data", {})
            tracking_info = data.get("sls_tracking_info", {})
            records = tracking_info.get("records", [])

            events = []
            for r in records:
                # Unix timestamp to datetime
                actual_time = datetime.fromtimestamp(r.get("actual_time"), timezone.utc)

                # Generate a unique hash for the event
                raw_str = f"{tracking_number}{r.get('tracking_code')}{r.get('actual_time')}{r.get('description')}"
                event_hash = hashlib.md5(raw_str.encode()).hexdigest()

                # Parse locations
                curr_loc = r.get("current_location", {})
                current_location = None
                if curr_loc.get("location_name") or curr_loc.get("full_address"):
                    current_location = TrackingLocation(
                        name=curr_loc.get("location_name"),
                        address=curr_loc.get("full_address"),
                        lat=float(curr_loc.get("lat")) if curr_loc.get("lat") else None,
                        lng=float(curr_loc.get("lng")) if curr_loc.get("lng") else None
                    )

                next_loc = r.get("next_location", {})
                next_location = None
                if next_loc.get("location_name") or next_loc.get("full_address"):
                    next_location = TrackingLocation(
                        name=next_loc.get("location_name"),
                        address=next_loc.get("full_address"),
                        lat=float(next_loc.get("lat")) if next_loc.get("lat") else None,
                        lng=float(next_loc.get("lng")) if next_loc.get("lng") else None
                    )

                events.append(TrackingEvent(
                    eventHash=event_hash,
                    code=r.get("tracking_code", ""),
                    name=r.get("tracking_name", ""),
                    descBuyer=r.get("buyer_description", r.get("description", "")),
                    descSeller=r.get("seller_description", r.get("description", "")),
                    milestoneCode=r.get("milestone_code", 0),
                    milestoneName=r.get("milestone_name", "Unknown"),
                    actualTime=actual_time,
                    currentLocation=current_location,
                    nextLocation=next_location,
                    raw=r
                ))

            # Sort events newest first
            events.sort(key=lambda x: x.actualTime, reverse=True)

            current_status = "Unknown"
            last_event_time = datetime.now(timezone.utc)
            if events:
                current_status = events[0].milestoneName
                last_event_time = events[0].actualTime

            return TrackingResult(
                trackingNumber=tracking_number,
                carrierId=self.id,
                currentStatus=current_status,
                lastEventTime=last_event_time,
                events=events
            )

        except Exception as e:
            # For a production app, you might want more graceful error handling
            raise Exception(f"Failed to track SPX order: {str(e)}")

    def is_final_status(self, events: List[TrackingEvent]) -> bool:
        if not events:
            return False

        # Newest event is at index 0 (if sorted)
        # However, to be safe, we check if any event indicates completion
        final_codes = ["F980"]
        for event in events:
            if event.code in final_codes:
                return True
        return False

    def format_time(self, dt: datetime) -> str:
        if not dt:
            return "N/A"
        # SPX returns UTC, convert to GMT+7
        if dt.tzinfo is None or dt.tzinfo == timezone.utc:
            local_dt = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7)))
        else:
            local_dt = dt.astimezone(timezone(timedelta(hours=7)))
        return local_dt.strftime("%H:%M %d/%m/%Y")
