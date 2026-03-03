from flask_login import UserMixin
from app.firebase import get_db
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

class User(UserMixin):
    def __init__(self, user_id, username, password_hash, settings=None, is_temporary=False, link_token=None):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.is_temporary = is_temporary
        self.link_token = link_token
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
            return User(
                doc.id,
                data['username'],
                data['password_hash'],
                data.get('settings'),
                data.get('isTemporary', False),
                data.get('linkToken')
            )
        return None

    @staticmethod
    def get_by_username(username):
        db = get_db()
        docs = db.collection(UsersRepo.COLLECTION).where(filter=FieldFilter('username', '==', username)).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            return User(
                doc.id,
                data['username'],
                data['password_hash'],
                data.get('settings'),
                data.get('isTemporary', False),
                data.get('linkToken')
            )
        return None

    @staticmethod
    def get_by_telegram_chat_id(chat_id):
        db = get_db()
        candidates = [str(chat_id)]
        try:
            candidates.append(int(chat_id))
        except (TypeError, ValueError):
            pass

        for candidate in candidates:
            docs = db.collection(UsersRepo.COLLECTION) \
                .where(filter=FieldFilter('settings.telegramChatId', '==', candidate)) \
                .limit(1) \
                .stream()
            for doc in docs:
                data = doc.to_dict()
                return User(
                    doc.id,
                    data['username'],
                    data['password_hash'],
                    data.get('settings'),
                    data.get('isTemporary', False),
                    data.get('linkToken')
                )
        return None

    @staticmethod
    def get_or_create_temp_by_telegram_chat_id(chat_id):
        chat_id_str = str(chat_id)
        existing = UsersRepo.get_by_telegram_chat_id(chat_id_str)
        if existing:
            return existing

        db = get_db()
        suffix = secrets.token_hex(4)
        random_password = secrets.token_urlsafe(24)
        link_token = secrets.token_urlsafe(24)

        user_data = {
            'username': f'tg_{chat_id_str}_{suffix}',
            'password_hash': generate_password_hash(random_password),
            'createdAt': firestore.SERVER_TIMESTAMP,
            'isTemporary': True,
            'linkToken': link_token,
            'settings': {
                'telegramChatId': chat_id_str,
                'notifyEnabled': True,
                'channels': ['telegram']
            }
        }

        update_time, doc_ref = db.collection(UsersRepo.COLLECTION).add(user_data)
        return User(
            doc_ref.id,
            user_data['username'],
            user_data['password_hash'],
            user_data['settings'],
            True,
            link_token
        )

    @staticmethod
    def link_temp_account(chat_id, username, password):
        user = UsersRepo.get_or_create_temp_by_telegram_chat_id(chat_id)
        db = get_db()
        password_hash = generate_password_hash(password)

        db.collection(UsersRepo.COLLECTION).document(user.id).update({
            'username': username,
            'password_hash': password_hash,
            'isTemporary': False,
            'linkToken': firestore.DELETE_FIELD,
            'settings.telegramChatId': str(chat_id)
        })

        updated = UsersRepo.get_by_id(user.id)
        return updated

    @staticmethod
    def create(username, password):
        db = get_db()
        password_hash = generate_password_hash(password)
        user_data = {
            'username': username,
            'password_hash': password_hash,
            'createdAt': firestore.SERVER_TIMESTAMP,
            'isTemporary': False,
            'settings': {
                'telegramChatId': None,
                'notifyEnabled': True,
                'channels': ['telegram']
            }
        }
        # App-level unique check is done in routes/services
        update_time, doc_ref = db.collection(UsersRepo.COLLECTION).add(user_data)
        return User(doc_ref.id, username, password_hash, user_data['settings'], False, None)

    @staticmethod
    def update_settings(user_id, settings):
        db = get_db()
        db.collection(UsersRepo.COLLECTION).document(user_id).update({
            'settings': settings
        })

    @staticmethod
    def count_all_users():
        """Đếm tổng số user trong hệ thống"""
        db = get_db()
        docs = db.collection(UsersRepo.COLLECTION).stream()
        return sum(1 for _ in docs)

    @staticmethod
    def get_user_created_date(user_id):
        """Lấy ngày tạo tài khoản của user"""
        db = get_db()
        doc = db.collection(UsersRepo.COLLECTION).document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            created_at = data.get('createdAt')
            if created_at:
                return created_at.strftime('%d/%m/%Y') if hasattr(created_at, 'strftime') else str(created_at)
        return 'N/A'
