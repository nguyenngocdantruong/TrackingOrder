import datetime
import hashlib
from typing import Dict, List, Optional
from flask import current_app

from app.notifications.service import NotificationService
from app.power_outage.provider import LichCupDienProvider, PowerOutageResult, PowerOutageItem, load_units
from app.repos.power_outage_repo import PowerOutageRepo
from app.repos.users_repo import UsersRepo


class PowerOutageService:
    @staticmethod
    def list_units() -> List[Dict]:
        return load_units()

    @staticmethod
    def list_subscriptions(user_id: str) -> List[Dict]:
        return PowerOutageRepo.list_for_user(user_id)

    @staticmethod
    def add_subscription(user, province_id: str, district_id: Optional[str] = None) -> Dict:
        provider = LichCupDienProvider()

        try:
            province, district, url = provider.resolve_area(province_id, district_id)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        existing = PowerOutageRepo.get_existing(user.id, province_id, district_id)
        if existing:
            return {"success": False, "error": "Bạn đã đăng ký khu vực này rồi."}

        subscription = {
            "userId": user.id,
            "provinceId": province["id"],
            "provinceName": province.get("name"),
            "districtId": district.get("id") if district else "",
            "districtName": district.get("name") if district else None,
            "url": url,
            "lastHash": None,
        }

        sub_id = PowerOutageRepo.create(subscription)
        subscription["id"] = sub_id

        PowerOutageService._send_initial_update(subscription, user, provider)

        return {"success": True, "subscription_id": sub_id}

    @staticmethod
    def remove_subscription(user, subscription_id: str) -> Dict:
        subscription = PowerOutageRepo.get_by_id(subscription_id)
        if not subscription or subscription.get("userId") != user.id:
            return {"success": False, "error": "Không tìm thấy đăng ký."}

        PowerOutageRepo.delete(subscription_id)
        return {"success": True}

    @staticmethod
    def _render_messages(subscription: Dict, result: PowerOutageResult) -> List[str]:
        messages: List[str] = []
        seen: set[str] = set()
        if not result.items:
            return messages

        area_label = subscription.get("districtName") or subscription.get("provinceName")
        province_name = subscription.get("provinceName")
        district_name = subscription.get("districtName")

        for item in result.items:
            header = ["⚡️ *Lịch cắt điện mới*"]
            if area_label:
                header.append(f"📍 Khu vực: *{area_label}*")
            if province_name:
                header.append(f"🗺️ Tỉnh/TP: {province_name}")
            if district_name:
                header.append(f"🏘️ Quận/Huyện: {district_name}")

            time_parts: List[str] = []
            if item.start_time and item.end_time:
                time_parts.append(f"🕒 {item.start_time} - {item.end_time}")
            elif item.time_raw:
                time_parts.append(f"🕒 {item.time_raw}")
            elif item.start_time:
                time_parts.append(f"🕒 {item.start_time}")

            body: List[str] = []
            body.append(f"📅 {item.date or 'Ngày không rõ'}")
            body.extend(time_parts)
            if item.area:
                body.append(f"📌 Khu vực: {item.area}")
            if item.power_company:
                body.append(f"🏢 Điện lực: {item.power_company}")
            if item.reason:
                body.append(f"🛠️ Lý do: {item.reason}")
            if item.status:
                body.append(f"✅ Trạng thái: {item.status}")

            footer = f"🔗 Xem thêm: {subscription.get('url')}"
            message = "\n".join(header + body + [footer])
            if message not in seen:
                seen.add(message)
                messages.append(message)

        return messages

    @staticmethod
    def _fingerprint_item(item: PowerOutageItem) -> str:
        # Build a stable, lowercased signature so we can detect “already sent” items.
        parts = [
            item.date or "",
            item.start_time or "",
            item.end_time or "",
            item.time_raw or "",
            item.area or "",
            item.power_company or "",
            item.reason or "",
            item.status or "",
        ]
        normalized = "|".join(p.strip().lower() for p in parts)
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _notify_user(subscription: Dict, result: PowerOutageResult, user) -> bool:
        messages = PowerOutageService._render_messages(subscription, result)
        if not messages:
            return False

        sent = False
        for msg in messages:
            NotificationService.send_to_user(user, msg, parse_mode="Markdown")
            sent = True
        return sent

    @staticmethod
    def check_and_notify_all() -> int:
        provider = LichCupDienProvider()
        subscriptions = PowerOutageRepo.list_all()
        if not subscriptions:
            return 0

        user_cache: Dict[str, Optional[object]] = {}
        result_cache: Dict[str, PowerOutageResult] = {}
        sent_count = 0

        for sub in subscriptions:
            cache_key = sub.get("url")
            if cache_key in result_cache:
                result = result_cache[cache_key]
            else:
                try:
                    raw_result = provider.fetch_schedule(
                        sub.get("provinceId"), sub.get("districtId") or None
                    )
                    filtered_items = PowerOutageService._filter_future_items(raw_result.items)
                    result = PowerOutageResult(
                        province=raw_result.province,
                        district=raw_result.district,
                        url=raw_result.url,
                        items=filtered_items,
                        not_found=raw_result.not_found,
                    )
                    result_cache[cache_key] = result
                except Exception as exc:  # pragma: no cover - network errors
                    if current_app:
                        current_app.logger.error(
                            "PowerOutage fetch failed for %s: %s", cache_key, exc
                        )
                    continue

            fingerprints = [PowerOutageService._fingerprint_item(item) for item in result.items]
            seen_items_list = sub.get("seenItems") or []
            seen_items = set(seen_items_list)
            new_items: List[PowerOutageItem] = []
            new_fps: List[str] = []
            for item, fp in zip(result.items, fingerprints):
                if fp in seen_items:
                    continue
                new_items.append(item)
                new_fps.append(fp)

            # If nothing new, just touch state and move on.
            full_hash = result.content_hash()
            if not new_items:
                merged = PowerOutageService._merge_seen(seen_items_list, fingerprints)
                PowerOutageRepo.touch_state(sub.get("id"), full_hash, merged)
                continue

            user = user_cache.get(sub.get("userId"))
            if user is None:
                user = UsersRepo.get_by_id(sub.get("userId"))
                user_cache[sub.get("userId")] = user

            if not user:
                continue

            # Only send new items to avoid bot spam/limits.
            result_with_new = PowerOutageResult(
                province=result.province,
                district=result.district,
                url=result.url,
                items=new_items,
                not_found=result.not_found,
            )

            notified = PowerOutageService._notify_user(sub, result_with_new, user)
            merged = PowerOutageService._merge_seen(list(seen_items.union(new_fps)), fingerprints)
            PowerOutageRepo.touch_state(sub.get("id"), full_hash, merged)
            if notified:
                sent_count += 1

        return sent_count

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
        if not value:
            return None
        value = value.strip()
        today = datetime.date.today()
        formats_with_year = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]
        formats_no_year = ["%d/%m", "%d-%m", "%d.%m"]

        for fmt in formats_with_year:
            try:
                return datetime.datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        for fmt in formats_no_year:
            try:
                parsed = datetime.datetime.strptime(value, fmt)
                candidate = parsed.replace(year=today.year).date()
                # if date already passed this year, assume next year
                if candidate < today:
                    candidate = candidate.replace(year=today.year + 1)
                return candidate
            except ValueError:
                continue

        # Fallback: extract day/month[/year] digits from strings like "20 tháng 3 năm 2026"
        import re
        numbers = re.findall(r"\d+", value)
        if len(numbers) >= 2:
            day = int(numbers[0])
            month = int(numbers[1])
            year = int(numbers[2]) if len(numbers) >= 3 else today.year
            try:
                candidate = datetime.date(year, month, day)
                if len(numbers) == 2 and candidate < today:
                    candidate = datetime.date(year + 1, month, day)
                return candidate
            except ValueError:
                return None

        return None

    @staticmethod
    def _filter_future_items(items: List[PowerOutageItem]) -> List[PowerOutageItem]:
        today = datetime.date.today()
        filtered: List[PowerOutageItem] = []
        for item in items:
            dt = PowerOutageService._parse_date(item.date)
            if dt and dt >= today:
                filtered.append(item)
        return filtered

    @staticmethod
    def _send_initial_update(subscription: Dict, user, provider: LichCupDienProvider) -> None:
        try:
            raw_result = provider.fetch_schedule(
                subscription.get("provinceId"), subscription.get("districtId") or None
            )
            filtered_items = PowerOutageService._filter_future_items(raw_result.items)
            result = PowerOutageResult(
                province=raw_result.province,
                district=raw_result.district,
                url=raw_result.url,
                items=filtered_items,
                not_found=raw_result.not_found,
            )

            if filtered_items:
                PowerOutageService._notify_user(subscription, result, user)

            fingerprints = [PowerOutageService._fingerprint_item(item) for item in filtered_items]
            merged = PowerOutageService._merge_seen([], fingerprints)
            PowerOutageRepo.touch_state(subscription.get("id"), result.content_hash(), merged)
        except Exception as exc:  # pragma: no cover - network errors
            if current_app:
                current_app.logger.error(
                    "PowerOutage initial fetch failed for %s: %s",
                    subscription.get("id"),
                    exc,
                )

    @staticmethod
    def _merge_seen(existing: List[str], current_fps: List[str]) -> List[str]:
        # Keep a bounded, deterministic list to avoid unbounded Firestore doc growth.
        MAX_SEEN = 200
        merged: List[str] = list(existing)
        existing_set = set(existing)
        for fp in current_fps:
            if fp not in existing_set:
                merged.append(fp)
                existing_set.add(fp)
        if len(merged) > MAX_SEEN:
            merged = merged[-MAX_SEEN:]
        return merged
