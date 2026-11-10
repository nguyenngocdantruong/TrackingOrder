import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import create_app
from app.repos.users_repo import User

class MasterLoginTests(unittest.TestCase):
    def setUp(self):
        with patch('app.init_firebase'), patch('app.init_gateways'), patch('app.init_notification_providers'):
            self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, MASTER_PASSWORD='master-test-秘密')
        self.user = User('account-1', 'owner', generate_password_hash('ordinary-password'))
        self.client = self.app.test_client()

    def attempt(self, password, existing=True):
        with patch('app.auth.routes.UsersRepo.get_by_username', return_value=self.user if existing else None):
            result = self.client.post('/auth/login', data={'username': 'owner', 'password': password})
        with self.client.session_transaction() as session:
            identity = session.get('_user_id')
        return result, identity

    def test_master_logs_into_existing_account(self):
        result, identity = self.attempt('master-test-秘密')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(identity, self.user.id)
        self.assertTrue(self.user.verify_password('ordinary-password'))

    def test_normal_password_still_works(self):
        self.assertEqual(self.attempt('ordinary-password')[1], self.user.id)

    def test_wrong_password_rejected(self):
        self.assertIsNone(self.attempt('wrong')[1])

    def test_unknown_username_rejected(self):
        self.assertIsNone(self.attempt('master-test-秘密', existing=False)[1])

    def test_empty_master_disabled(self):
        self.app.config['MASTER_PASSWORD'] = ''
        self.assertIsNone(self.attempt('')[1])
        self.assertIsNone(self.attempt('master-test-秘密')[1])

    def test_missing_master_disabled(self):
        self.app.config.pop('MASTER_PASSWORD')
        self.assertIsNone(self.attempt('master-test-秘密')[1])

    def test_csrf_still_required(self):
        self.app.config['WTF_CSRF_ENABLED'] = True
        self.assertIsNone(self.attempt('master-test-秘密')[1])

if __name__ == '__main__':
    unittest.main()
