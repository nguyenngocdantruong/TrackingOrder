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
    def reassign_user(from_user_id, to_user_id):
        """Move all trackings from one user to another."""
        if from_user_id == to_user_id:
            return

        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION) \
            .where(filter=FieldFilter('userId', '==', from_user_id)) \
            .stream()

        for doc in docs:
            db.collection(TrackingsRepo.COLLECTION).document(doc.id).update({'userId': to_user_id})

    @staticmethod
    def get_active_trackings():
        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION).where(filter=FieldFilter('isActive', '==', True)).stream()
        return [{'id': doc.id, **doc.to_dict()} for doc in docs]

    @staticmethod
    def count_user_trackings(user_id):
        """Đếm số tracking của user"""
        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION).where(filter=FieldFilter('userId', '==', user_id)).stream()
        return sum(1 for _ in docs)

    @staticmethod
    def count_user_active_trackings(user_id):
        """Đếm số tracking đang hoạt động của user"""
        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION)\
            .where(filter=FieldFilter('userId', '==', user_id))\
            .where(filter=FieldFilter('isActive', '==', True))\
            .stream()
        return sum(1 for _ in docs)

    @staticmethod
    def count_all_trackings():
        """Đếm tổng số tracking trong hệ thống"""
        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION).stream()
        return sum(1 for _ in docs)

    @staticmethod
    def count_all_active_trackings():
        """Đếm tổng số tracking đang hoạt động trong hệ thống"""
        db = get_db()
        docs = db.collection(TrackingsRepo.COLLECTION).where(filter=FieldFilter('isActive', '==', True)).stream()
        return sum(1 for _ in docs)
