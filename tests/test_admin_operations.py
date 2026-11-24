import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app
from app.repos.users_repo import User


class AdminOperationsTests(unittest.TestCase):
    def setUp(self):
        with patch('app.init_firebase'), patch('app.init_gateways'), patch('app.init_notification_providers'):
            self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY='admin-test', ADMIN_TELEGRAM_USER_ID='1',
                               WTF_CSRF_ENABLED=False, WEBSITE_URL='https://test.invalid')
        self.owner = User('owner', 'owner', '', {'telegramChatId': '1'}, telegram_verified_id='1')
        self.member = User('member', 'sample', '', {'telegramChatId': '2'})
        self.users = {user.id: user for user in (self.owner, self.member)}
        loader = patch('app.repos.users_repo.UsersRepo.get_by_id', side_effect=self.users.get)
        loader.start()
        self.addCleanup(loader.stop)
        self.client = self.app.test_client()

    def login(self, user):
        with self.client.session_transaction() as session:
            session['_user_id'] = user.id
            session['_fresh'] = True

    def test_all_admin_routes_require_verified_owner(self):
        paths = ('overview', 'users', 'users/member', 'trackings', 'trackings/example',
                 'logs', 'payments', 'config')
        self.login(self.member)
        with patch('app.admin_operations.get_db') as db:
            for path in paths:
                self.assertEqual(self.client.get('/admin/' + path).status_code, 403, path)
            db.assert_not_called()

    def test_admin_search_and_navigation_render_with_cursor(self):
        self.login(self.owner)
        self.assertEqual(self.client.get('/admin/').location, '/admin/overview')
        with patch('app.admin_operations.page', return_value=([{
            'id': 'member', 'username': 'sample', 'isTemporary': False,
        }], 'next')):
            response = self.client.get('/admin/users?type=regular&after=previous')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertIn(b'/admin/config', response.data)
        self.assertIn(b'after=next', response.data)
        self.assertNotIn(b'after=previous', response.data)

    def test_lock_and_password_reset_target_member_and_record_actor(self):
        self.login(self.owner)
        with patch('app.admin_operations.UsersRepo.set_suspended') as suspend, \
             patch('app.admin_operations.UsersRepo.reset_password') as reset, \
             patch('app.admin_operations.record') as record:
            self.assertEqual(self.client.post('/admin/users/owner', data={'action': 'suspend'}).status_code, 403)
            self.assertEqual(self.client.post('/admin/users/member', data={'action': 'suspend'}).status_code, 302)
            suspend.assert_called_once_with('member', True)
            record.assert_called_once_with('audit', 'suspend', 'ok', actorId='owner', userId='member')
            response = self.client.post('/admin/users/member', data={
                'action': 'reset_password', 'password': 'synthetic-password', 'confirmation': 'different',
            })
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(b'synthetic-password', response.data)
            reset.assert_not_called()

    def test_suspended_account_loses_existing_web_session(self):
        self.login(self.member)
        self.member.suspended = True
        self.assertEqual(self.client.get('/settings').status_code, 302)

    def test_tracking_row_pause_and_edit_preserve_terminal_state(self):
        self.login(self.owner)
        tracking = {'isActive': True, 'userId': 'member', 'carrierId': 'lex'}
        with patch('app.admin_operations.TrackingsRepo.get_by_id', return_value=tracking), \
             patch('app.admin_operations.TrackingsRepo.update') as update, \
             patch('app.admin_operations.record') as audit:
            response = self.client.post('/admin/trackings/example', data={
                'action': 'pause_tracking', 'from_list': '1',
            })
            self.assertEqual(response.location, '/admin/trackings')
            update.assert_called_once_with('example', {'adminPaused': True})
            audit.assert_called_once_with('audit', 'pause_tracking', 'ok', actorId='owner',
                                          trackingId='example', userId='member', carrierId='lex')
            self.client.post('/admin/trackings/example', data={
                'action': 'edit_tracking', 'alias': ' Sample ', 'note': ' Ghi chú ',
            })
            update.assert_called_with('example', {'alias': 'Sample', 'note': 'Ghi chú'})
            tracking['isActive'] = False
            self.assertEqual(self.client.post('/admin/trackings/example', data={
                'action': 'resume_tracking',
            }).status_code, 400)
            self.assertEqual(update.call_count, 2)

    def test_scheduler_skips_admin_paused_orders(self):
        from app.scheduler import refresh_all_active_trackings

        with patch('app.scheduler.TrackingsRepo.get_active_trackings', return_value=[
            {'id': 'paused', 'adminPaused': True}, {'id': 'running'},
        ]), patch('app.scheduler.TrackingService.refresh_tracking', return_value=True) as refresh, \
             patch('app.scheduler.record'):
            refresh_all_active_trackings(self.app)
        refresh.assert_called_once_with('running')

    def test_verified_payos_sdk_data_is_persisted_and_duplicate_is_not_notified(self):
        gateway = SimpleNamespace(verify_webhook=lambda _: SimpleNamespace(
            code='00', order_code=123, amount=25000,
        ))
        with patch('app.payments.routes.registry.get_gateway', return_value=gateway), \
             patch('app.payments.routes.record_payment', side_effect=[True, False]) as save, \
             patch('app.payments.routes._notify_donation_payload') as notify:
            for _ in range(2):
                self.assertEqual(self.client.post('/v1/payments/webhook', data=b'fixture').status_code, 200)
            save.assert_called_with(123, 25000, paid=True)
            notify.assert_called_once()
