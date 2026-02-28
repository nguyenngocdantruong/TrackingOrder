from app.firebase import get_db
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

class TrackingsRepo:
    COLLECTION = 'trackings'

    @staticmethod
    def get_by_id(tracking_id):
        db = get_db()
        doc = db.collection(TrackingsRepo.COLLECTION).document(tracking_id).get()
        return doc.to_dict() if doc.exists else None

    @staticmethod
    def get_user_trackings(user_id):
        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION).where(filter=FieldFilter('userId', '==', user_id)).order_by('createdAt', direction=firestore.Query.DESCENDING).stream()
        return [{'id': doc.id, **doc.to_dict()} for doc in docs]

    @staticmethod
    def create(tracking_data):
        db = get_db()
        tracking_data['createdAt'] = firestore.SERVER_TIMESTAMP
        update_time, doc_ref = db.collection(TrackingsRepo.COLLECTION).add(tracking_data)
        return doc_ref.id

    @staticmethod
    def update(tracking_id, update_data):
        db = get_db()
        db.collection(TrackingsRepo.COLLECTION).document(tracking_id).update(update_data)

    @staticmethod
    def delete(tracking_id):
        db = get_db()
        db.collection(TrackingsRepo.COLLECTION).document(tracking_id).delete()

    @staticmethod
    def get_active_trackings():
        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION).where(filter=FieldFilter('isActive', '==', True)).stream()
        return [{'id': doc.id, **doc.to_dict()} for doc in docs]
