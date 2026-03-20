from typing import Dict, List, Optional
from datetime import datetime

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.firebase import get_db


class PowerOutageRepo:
    COLLECTION = "power_outage_subscriptions"

    @staticmethod
    def _doc_to_dict(doc) -> Dict:
        data = doc.to_dict() or {}
        return {"id": doc.id, **data}

    @staticmethod
    def list_for_user(user_id: str) -> List[Dict]:
        db = get_db()
        docs = (
            db.collection(PowerOutageRepo.COLLECTION)
            .where(filter=FieldFilter("userId", "==", user_id))
            .stream()
        )
        return [PowerOutageRepo._doc_to_dict(doc) for doc in docs]

    @staticmethod
    def list_all() -> List[Dict]:
        db = get_db()
        docs = db.collection(PowerOutageRepo.COLLECTION).stream()
        return [PowerOutageRepo._doc_to_dict(doc) for doc in docs]

    @staticmethod
    def get_by_id(subscription_id: str) -> Optional[Dict]:
        db = get_db()
        doc = db.collection(PowerOutageRepo.COLLECTION).document(subscription_id).get()
        return PowerOutageRepo._doc_to_dict(doc) if doc.exists else None

    @staticmethod
    def get_existing(user_id: str, province_id: str, district_id: Optional[str]):
        db = get_db()
        query = db.collection(PowerOutageRepo.COLLECTION).where(
            filter=FieldFilter("userId", "==", user_id)
        )
        query = query.where(filter=FieldFilter("provinceId", "==", province_id))
        query = query.where(filter=FieldFilter("districtId", "==", district_id or ""))
        docs = query.limit(1).stream()
        for doc in docs:
            return PowerOutageRepo._doc_to_dict(doc)
        return None

    @staticmethod
    def create(subscription: Dict) -> str:
        db = get_db()
        subscription.setdefault("createdAt", firestore.SERVER_TIMESTAMP)
        subscription.setdefault("updatedAt", firestore.SERVER_TIMESTAMP)
        update_time, doc_ref = db.collection(PowerOutageRepo.COLLECTION).add(subscription)
        return doc_ref.id

    @staticmethod
    def update(subscription_id: str, data: Dict):
        db = get_db()
        data["updatedAt"] = firestore.SERVER_TIMESTAMP
        db.collection(PowerOutageRepo.COLLECTION).document(subscription_id).update(data)

    @staticmethod
    def delete(subscription_id: str):
        db = get_db()
        db.collection(PowerOutageRepo.COLLECTION).document(subscription_id).delete()

    @staticmethod
    def touch_state(subscription_id: str, last_hash: str, seen_items: Optional[List[str]] = None):
        payload = {
            "lastHash": last_hash,
            "lastCheckedAt": datetime.utcnow().isoformat(),
        }
        if seen_items is not None:
            payload["seenItems"] = seen_items
        PowerOutageRepo.update(subscription_id, payload)
