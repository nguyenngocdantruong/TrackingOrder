from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class TrackingLocation:
    name: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

@dataclass
class TrackingEvent:
    eventHash: str
    code: str
    name: str
    descBuyer: str
    descSeller: str
    milestoneCode: int
    milestoneName: str
    actualTime: datetime
    currentLocation: Optional[TrackingLocation] = None
    nextLocation: Optional[TrackingLocation] = None
    raw: Optional[dict] = None

    def to_dict(self):
        return {
            'eventHash': self.eventHash,
            'code': self.code,
            'name': self.name,
            'descBuyer': self.descBuyer,
            'descSeller': self.descSeller,
            'milestoneCode': self.milestoneCode,
            'milestoneName': self.milestoneName,
            'actualTime': self.actualTime,
            'currentLocation': vars(self.currentLocation) if self.currentLocation else None,
            'nextLocation': vars(self.nextLocation) if self.nextLocation else None,
            'raw': self.raw
        }

@dataclass
class TrackingResult:
    trackingNumber: str
    carrierId: str
    currentStatus: str
    lastEventTime: datetime
    events: List[TrackingEvent] = field(default_factory=list)

class CarrierProvider(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    @abstractmethod
    def displayName(self) -> str:
        pass

    @abstractmethod
    def supports(self, tracking_number: str) -> bool:
        pass

    @abstractmethod
    def track(self, tracking_number: str) -> TrackingResult:
        pass

    @abstractmethod
    def is_final_status(self, events: List[TrackingEvent]) -> bool:
        """Return True if the tracking has reached a terminal state (Delivered/Cancelled)."""
        pass

    def format_time(self, dt: datetime) -> str:
        """Format datetime for display, specific to each carrier's context."""
        if not dt:
            return "N/A"
        # Default implementation: assuming we want to show it in a standard format
        # Carriers can override this to adjust timezones (e.g. UTC to GMT+7)
        return dt.strftime("%H:%M %d/%m/%Y")
