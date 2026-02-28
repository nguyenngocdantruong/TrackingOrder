from flask_login import UserMixin
from app.firebase import get_db
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, user_id, username, password_hash, settings=None):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.settings = settings or {
            'telegramChatId': None,
            'notifyEnabled': True,
            'channels': ['telegram']
        }

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class UsersRepo:
    COLLECTION = 'users'

    @staticmethod
    def get_by_id(user_id):
        db = get_db()
        doc = db.collection(UsersRepo.COLLECTION).document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            return User(doc.id, data['username'], data['password_hash'], data.get('settings'))
        return None

    @staticmethod
    def get_by_username(username):
        db = get_db()
        docs = db.collection(UsersRepo.COLLECTION).where(filter=FieldFilter('username', '==', username)).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            return User(doc.id, data['username'], data['password_hash'], data.get('settings'))
        return None

    @staticmethod
    def create(username, password):
        db = get_db()
        password_hash = generate_password_hash(password)
        user_data = {
            'username': username,
            'password_hash': password_hash,
            'createdAt': firestore.SERVER_TIMESTAMP,
            'settings': {
                'telegramChatId': None,
                'notifyEnabled': True,
                'channels': ['telegram']
            }
        }
        # App-level unique check is done in routes/services
        update_time, doc_ref = db.collection(UsersRepo.COLLECTION).add(user_data)
        return User(doc_ref.id, username, password_hash, user_data['settings'])

    @staticmethod
    def update_settings(user_id, settings):
        db = get_db()
        db.collection(UsersRepo.COLLECTION).document(user_id).update({
            'settings': settings
        })
