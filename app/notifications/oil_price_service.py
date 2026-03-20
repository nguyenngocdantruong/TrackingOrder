import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app.notifications.service import NotificationService
from app.repos.users_repo import UsersRepo


class OilPriceService:
    @staticmethod
    def fetch_latest(app=None) -> Dict:
        app_ctx = app or current_app
        if not app_ctx:
            raise RuntimeError("App context required to fetch oil prices")

        url = app_ctx.config.get("OIL_PRICE_URL")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        date_input = soup.find("input", {"id": "vn_today"})
        date_value = date_input.get("value") if date_input else None

        petro_table = soup.find("table", {"class": "table-petro"})
        pvoil_table = soup.find("table", {"class": "table-pvoil"})

        return {
            "date": date_value,
            "petrolimex": OilPriceService._parse_table(petro_table),
            "pvoil": OilPriceService._parse_table(pvoil_table),
            "source": url,
        }

    @staticmethod
    def _parse_table(table) -> List[Dict]:
        if not table:
            return []

        rows = []
        tbody = table.find("tbody")
        if not tbody:
            return rows

        for tr in tbody.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all("td")]
            if len(cells) < 4:
                continue

            name = cells[0]
            change_today = OilPriceService._parse_number(cells[1])
            change_prev = OilPriceService._parse_number(cells[2])
            price = OilPriceService._parse_number(cells[3])

            rows.append(
                {
                    "name": name,
                    "change_today": change_today,
                    "change_prev": change_prev,
                    "price": price,
                }
            )

        return rows

    @staticmethod
    def _parse_number(text: str) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"([+-]?\d[\d,]*)", text)
        if not match:
            return None
        cleaned = match.group(1).replace(",", "")
        try:
            return int(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _fmt_delta(value: Optional[int]) -> str:
        if value is None:
            return "N/A"
        arrow = "▲" if value > 0 else ("▼" if value < 0 else "➖")
        sign = "+" if value > 0 else ""
        color_dot = "🔴" if value > 0 else ("🟢" if value < 0 else "⚪")
        return f"{color_dot} {arrow} {sign}{value:,} đ"

    @staticmethod
    def _fmt_price(value: Optional[int]) -> str:
        if value is None:
            return "N/A"
        return f"{value:,} đ/lít"

    @staticmethod
    def build_message(data: Dict) -> Optional[str]:
        if not data:
            return None

        date_label = data.get("date") or datetime.now().strftime("%Y-%m-%d")

        def section(title: str, items: List[Dict]) -> List[str]:
            if not items:
                return []
            lines = [f"*{title}*:"]
            for item in items:
                price_text = OilPriceService._fmt_price(item.get('price'))
                delta_today = OilPriceService._fmt_delta(item.get('change_today'))
                delta_prev = OilPriceService._fmt_delta(item.get('change_prev'))
                lines.append(
                    f"- {item.get('name')}: `{price_text}`\n"
                    f"  • Hôm nay: {delta_today}\n"
                    f"  • Kỳ trước: {delta_prev}"
                )
            return lines

        message_lines: List[str] = [
            f"📢 *Giá xăng dầu Hà Nội* ({date_label})",
            "",
        ]
        message_lines += section("⛽ Petrolimex", data.get("petrolimex") or [])
        if data.get("petrolimex"):
            message_lines.append("")
        message_lines += section("🛢️ PVOIL", data.get("pvoil") or [])
        source_url = data.get("source")
        if source_url:
            message_lines.append("")
            message_lines.append(f"Nguồn: {source_url}")

        return "\n".join([line for line in message_lines if line is not None])

    @staticmethod
    def _filter_data_for_user(data: Dict, suppliers: List[str], product_map: Dict) -> Dict:
        if not data:
            return {}

        suppliers_set = set(suppliers or [])

        def filter_items(key: str) -> List[Dict]:
            if key not in suppliers_set:
                return []
            items = data.get(key) or []
            if key in product_map:
                selected_names = product_map.get(key) or []
                if not selected_names:
                    return []
                selected_name_set = set(selected_names)
                return [item for item in items if item.get('name') in selected_name_set]
            return items

        return {
            "date": data.get("date"),
            "source": data.get("source"),
            "petrolimex": filter_items("petrolimex"),
            "pvoil": filter_items("pvoil"),
        }

    @staticmethod
    def notify_all(app=None) -> int:
        app_ctx = app or current_app
        if not app_ctx:
            raise RuntimeError("App context required to notify users")

        data = OilPriceService.fetch_latest(app_ctx)

        users = UsersRepo.list_all_users()
        notified = 0
        for user in users:
            settings = user.settings or {}
            if not settings.get('oilNotifyEnabled', True):
                continue

            suppliers = settings.get('oilSuppliers') or ['petrolimex', 'pvoil']
            product_map = settings.get('oilProducts') or {}
            filtered_data = OilPriceService._filter_data_for_user(data, suppliers, product_map)

            if not ((filtered_data.get('petrolimex') or filtered_data.get('pvoil'))):
                continue

            message = OilPriceService.build_message(filtered_data)
            if not message:
                continue

            results = NotificationService.send_to_user(user, message, parse_mode="Markdown")
            if results:
                notified += 1

        if current_app:
            current_app.logger.info("[OIL PRICE] Sent notifications to %s users", notified)
        return notified


__all__ = ["OilPriceService"]
