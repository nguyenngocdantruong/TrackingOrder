import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

UNITS_PATH = Path(__file__).resolve().parent.parent / "resources" / "cutoff_electric_units.json"


def slugify(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFD", value)
    without_diacritics = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    lowered = without_diacritics.lower()
    collapsed = re.sub(r"[^a-z0-9]+", "_", lowered)
    return collapsed.strip("_")


@lru_cache(maxsize=1)
def load_units() -> List[Dict[str, Any]]:
    if not UNITS_PATH.exists():
        return []
    return json.loads(UNITS_PATH.read_text(encoding="utf-8"))


def _find_province(province_id: str) -> Optional[Dict[str, Any]]:
    return next((p for p in load_units() if p.get("id") == province_id), None)


def _find_child(province: Dict[str, Any], district_id: str) -> Optional[Dict[str, Any]]:
    children = province.get("child") or []
    for child in children:
        if child.get("id") == district_id or slugify(child.get("name", "")) == district_id:
            return child
    return None


@dataclass
class PowerOutageItem:
    heading: Optional[str]
    power_company: Optional[str]
    date: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    area: Optional[str]
    reason: Optional[str]
    status: Optional[str]
    time_raw: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "heading": self.heading,
            "power_company": self.power_company,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "area": self.area,
            "reason": self.reason,
            "status": self.status,
            "time_raw": self.time_raw,
        }


@dataclass
class PowerOutageResult:
    province: Dict[str, Any]
    district: Optional[Dict[str, Any]]
    url: str
    items: List[PowerOutageItem]
    not_found: bool = False

    def content_hash(self) -> str:
        payload = {
            "url": self.url,
            "not_found": self.not_found,
            "items": [item.to_dict() for item in self.items],
        }
        return hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()


class LichCupDienProvider:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    @staticmethod
    def resolve_area(
        province_id: str, district_id: Optional[str]
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], str]:
        province = _find_province(province_id)
        if not province:
            raise ValueError(f"Province id '{province_id}' not found")

        if not district_id:
            return province, None, province["url"]

        district = _find_child(province, district_id)
        if not district:
            raise ValueError(
                f"District id '{district_id}' not found for province '{province_id}'"
            )
        return province, district, district["url"]

    def fetch_html(self, url: str) -> str:
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_detail_block(block) -> PowerOutageItem:
        data: Dict[str, Optional[str]] = {
            "heading": None,
            "power_company": None,
            "date": None,
            "start_time": None,
            "end_time": None,
            "area": None,
            "reason": None,
            "status": None,
            "time_raw": None,
        }

        heading = block.find_previous("h3", class_="tab-items-title-bold")
        if heading:
            data["heading"] = heading.get_text(" ", strip=True)

        for wrapper in block.select(".new_lcd_wrapper"):
            title_el = wrapper.select_one(".title_item_lcd_wrapper")
            value_el = wrapper.select_one(".item_content_lcd_wrapper")
            title = title_el.get_text(strip=True) if title_el else ""
            value_text = value_el.get_text(" ", strip=True) if value_el else ""

            if title.startswith("Điện lực"):
                data["power_company"] = value_text
            elif title.startswith("Ngày"):
                data["date"] = value_text
            elif title.startswith("Thời gian"):
                times = wrapper.select(".item_lcd_time")
                if times:
                    start = times[0].get_text(strip=True)
                    end = times[1].get_text(strip=True) if len(times) > 1 else ""
                    data["start_time"] = start
                    if end:
                        data["end_time"] = end
                else:
                    data["time_raw"] = value_text
            elif title.startswith("Khu vực"):
                data["area"] = value_text
            elif title.startswith("Lý do"):
                data["reason"] = value_text
            elif title.startswith("Trạng thái"):
                data["status"] = value_text

        return PowerOutageItem(**data)

    @classmethod
    def _parse_schedule(cls, html: str) -> Tuple[List[PowerOutageItem], bool]:
        soup = BeautifulSoup(html, "html.parser")
        not_found = bool(soup.select_one(".no-dt"))
        blocks = soup.select(".lcd_detail_wrapper")
        items = [cls._parse_detail_block(block) for block in blocks]
        return items, not_found

    def fetch_schedule(
        self, province_id: str, district_id: Optional[str] = None
    ) -> PowerOutageResult:
        province, district, url = self.resolve_area(province_id, district_id)

        html = self.fetch_html(url)
        items, not_found = self._parse_schedule(html)

        return PowerOutageResult(
            province=province,
            district=district,
            url=url,
            items=items,
            not_found=not_found,
        )

    def fetch_schedule_by_url(self, url: str) -> PowerOutageResult:
        html = self.fetch_html(url)
        items, not_found = self._parse_schedule(html)
        return PowerOutageResult(
            province={"id": None, "name": None},
            district=None,
            url=url,
            items=items,
            not_found=not_found,
        )
