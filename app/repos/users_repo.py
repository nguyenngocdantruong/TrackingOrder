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
            'zaloAccountId': None,
            'zalo': {'name': None, 'chatId': None},
            'notifyEnabled': True,
            'channels': ['telegram', 'zalo']
        }
        self.settings.setdefault('zalo', {'name': None, 'chatId': None})
        if self.settings.get('zaloAccountId') and not self.settings['zalo'].get('chatId'):
            self.settings['zalo']['chatId'] = str(self.settings.get('zaloAccountId'))

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class UsersRepo:
    COLLECTION = 'users'

    @staticmethod
    def _ensure_channels(settings, *channels):
        current_channels = list(settings.get('channels') or [])
        for channel in channels:
            if channel not in current_channels:
                current_channels.append(channel)
        return current_channels

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
                'zaloAccountId': None,
                'zalo': {'name': None, 'chatId': None},
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
    def get_or_create_temp_by_zalo_account_id(zalo_account_id):
        zalo_id_str = str(zalo_account_id)
        existing = UsersRepo.get_by_zalo_account_id(zalo_id_str)
        if existing:
            if not existing.link_token:
                # ensure a fresh token so the link URL stays valid
                db = get_db()
                link_token = secrets.token_urlsafe(24)
                db.collection(UsersRepo.COLLECTION).document(existing.id).update({'linkToken': link_token})
                existing.link_token = link_token
            # Backfill Zalo contact structure if missing
            if not (existing.settings or {}).get('zalo'):
                db = get_db()
                db.collection(UsersRepo.COLLECTION).document(existing.id).update({
                    'settings.zalo.chatId': zalo_id_str,
                    'settings.zalo.name': firestore.DELETE_FIELD,
                })
                existing.settings.setdefault('zalo', {'name': None, 'chatId': zalo_id_str})
            elif not existing.settings['zalo'].get('chatId'):
                db = get_db()
                db.collection(UsersRepo.COLLECTION).document(existing.id).update({
                    'settings.zalo.chatId': zalo_id_str,
                })
                existing.settings['zalo']['chatId'] = zalo_id_str
            return existing

        db = get_db()
        suffix = secrets.token_hex(4)
        random_password = secrets.token_urlsafe(24)
        link_token = secrets.token_urlsafe(24)

        user_data = {
            'username': f'zalo_{zalo_id_str}_{suffix}',
            'password_hash': generate_password_hash(random_password),
            'createdAt': firestore.SERVER_TIMESTAMP,
            'isTemporary': True,
            'linkToken': link_token,
            'settings': {
                'telegramChatId': None,
                'zaloAccountId': zalo_id_str,
                'zalo': {'name': None, 'chatId': zalo_id_str},
                'notifyEnabled': True,
                'channels': ['zalo']
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
                'zaloAccountId': None,
                'zalo': {'name': None, 'chatId': None},
                'notifyEnabled': True,
                'channels': ['telegram', 'zalo']
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
    def get_by_zalo_account_id(zalo_account_id):
        """Get user by Zalo account ID."""
        db = get_db()
        if not zalo_account_id:
            return None

        search_paths = ['settings.zaloAccountId', 'settings.zalo.chatId']
        for path in search_paths:
            docs = db.collection(UsersRepo.COLLECTION) \
                .where(filter=FieldFilter(path, '==', str(zalo_account_id))) \
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
    def link_temp_account_zalo(zalo_account_id, username, password):
        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_account_id)
        db = get_db()
        password_hash = generate_password_hash(password)
        channels = UsersRepo._ensure_channels(user.settings or {}, 'zalo')

        db.collection(UsersRepo.COLLECTION).document(user.id).update({
            'username': username,
            'password_hash': password_hash,
            'isTemporary': False,
            'linkToken': firestore.DELETE_FIELD,
            'settings.zaloAccountId': str(zalo_account_id),
            'settings.zalo.chatId': str(zalo_account_id),
            'settings.channels': channels
        })

        updated = UsersRepo.get_by_id(user.id)
        return updated

    @staticmethod
    def attach_zalo_account(user_id, zalo_account_id):
        user = UsersRepo.get_by_id(user_id)
        if not user:
            return None

        channels = UsersRepo._ensure_channels(user.settings or {}, 'zalo')
        db = get_db()
        db.collection(UsersRepo.COLLECTION).document(user.id).update({
            'settings.zaloAccountId': str(zalo_account_id),
            'settings.zalo.chatId': str(zalo_account_id),
            'settings.channels': channels,
            'linkToken': firestore.DELETE_FIELD,
            'isTemporary': False,
        })
        return UsersRepo.get_by_id(user.id)

    @staticmethod
    def delete(user_id):
        db = get_db()
        db.collection(UsersRepo.COLLECTION).document(user_id).delete()

    @staticmethod
    def list_telegram_chat_ids():
        """Return all Telegram chat IDs configured by users."""
        db = get_db()
        chat_ids = []
        docs = db.collection(UsersRepo.COLLECTION).stream()
        for doc in docs:
            data = doc.to_dict()
            settings = data.get('settings') or {}
            chat_id = settings.get('telegramChatId')
            if chat_id:
                chat_ids.append(str(chat_id))
        return chat_ids

    @staticmethod
    def list_zalo_account_ids():
        """Return all Zalo account IDs configured by users."""
        db = get_db()
        account_ids = []
        docs = db.collection(UsersRepo.COLLECTION).stream()
        for doc in docs:
            data = doc.to_dict()
            settings = data.get('settings') or {}
            zalo_settings = settings.get('zalo') or {}
            zalo_id = zalo_settings.get('chatId') or settings.get('zaloAccountId')
            if zalo_id:
                account_ids.append(str(zalo_id))
        return list(dict.fromkeys(account_ids))

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
