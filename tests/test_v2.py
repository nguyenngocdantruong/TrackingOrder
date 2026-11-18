import hashlib
import hmac
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit
from werkzeug.security import generate_password_hash

from app import create_app
from app.admin import GROUPS, create_admin_link, revision
from app.api.webhooks import generate_api_key, generate_webhook_secret, sign_webhook_payload
from app.providers.base import TrackingEvent, TrackingLocation, TrackingResult
from app.repos.users_repo import User
from dotenv import dotenv_values


class PrimaryUIAndPartnerAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env_file = Path(self.tmp.name) / '.env'
        self.conf_file = Path(self.tmp.name) / 'config.conf'
        self.env_file.write_text("PAYOS_API_KEY='keep-v2-secret'\nEXTRA_VAR='stay'\n", encoding='utf-8')
        self.conf_file.write_text("POLL_INTERVAL_SECONDS='300'\n", encoding='utf-8')

        self.env_patch = patch.dict(
            os.environ,
            ENV_FILE=str(self.env_file),
            CONF_FILE=str(self.conf_file),
            MANAGED_RESTART='0',
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

        with patch('app.init_firebase'), patch('app.init_gateways'), patch('app.init_notification_providers'):
            self.app = create_app()

        self.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            SECRET_KEY='v2-test-secret',
            ADMIN_TELEGRAM_USER_ID='777888',
            MASTER_PASSWORD='master-v2-password',
            WEBSITE_URL='http://localhost',
        )

        self.raw_api_key, self.api_key_hash, self.api_key_prefix = generate_api_key()
        self.wh_secret = generate_webhook_secret()

        self.user = User(
            'u-v2',
            'alice',
            generate_password_hash('secret123'),
            settings={
                'telegramChatId': '777888',
                'zaloAccountId': '999111',
                'zalo': {'name': None, 'chatId': '999111', 'enabled': True},
                'notifyEnabled': True,
                'telegramEnabled': True,
                'zaloEnabled': True,
                'channels': ['telegram', 'zalo'],
            },
            is_temporary=False,
            telegram_verified_id='777888',
            partner_api={
                'apiKeyHash': self.api_key_hash,
                'apiKeyPrefix': self.api_key_prefix,
                'webhookUrl': 'http://127.0.0.1:9999/hook',
                'webhookSecret': self.wh_secret,
                'webhookEnabled': True,
                'webhookEvents': ['tracking.created', 'tracking.updated', 'tracking.completed'],
            },
        )

        self.sample_tracking = {
            'id': 'trk-100',
            'userId': 'u-v2',
            'trackingNumber': 'SPXVN0123456789',
            'carrierId': 'spx_vn',
            'alias': 'Tai nghe chống ồn',
            'externalRef': 'ORD-55',
            'isActive': True,
            'currentStatus': 'Đang vận chuyển',
            'lastCheckedAt': datetime(2026, 11, 18, 6, 30, tzinfo=timezone.utc),
            'events': [
                {
                    'eventHash': 'ev1',
                    'code': 'IN_TRANSIT',
                    'name': 'Rời kho trung chuyển',
                    'descBuyer': 'Đơn hàng đang trên đường tới trạm phát.',
                    'actualTime': datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc),
                    'currentLocation': {'address': 'TP. Hồ Chí Minh'},
                }
            ],
        }

        self.user_loader_patch = patch(
            'app.repos.users_repo.UsersRepo.get_by_id',
            side_effect=lambda uid: self.user if uid == 'u-v2' else None,
        )
        self.user_loader_patch.start()
        self.addCleanup(self.user_loader_patch.stop)

        self.api_lookup_patch = patch(
            'app.repos.users_repo.UsersRepo.get_by_partner_api_key_hash',
            side_effect=lambda h: self.user if h == self.api_key_hash else None,
        )
        self.api_lookup_patch.start()
        self.addCleanup(self.api_lookup_patch.stop)

        self.client = self.app.test_client()

    def login_session(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = 'u-v2'
            sess['_fresh'] = True

    def test_legacy_v1_routes_live_under_v1(self):
        self.assertEqual(self.client.get('/v1').status_code, 200)
        self.assertEqual(self.client.get('/v1/').status_code, 200)
        self.assertEqual(self.client.get('/v1/auth/login').status_code, 200)
        self.assertEqual(self.client.get('/v1/auth/register').status_code, 200)
        self.assertEqual(self.client.get('/v1/payments/support').status_code, 200)

        unauth_v1_dash = self.client.get('/v1/dashboard')
        self.assertEqual(unauth_v1_dash.status_code, 302)
        self.assertIn('/v1/auth/login', unauth_v1_dash.headers['Location'])

    def test_primary_root_and_v2_compatibility_redirects(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertEqual(self.client.get('/docs/api').status_code, 200)
        self.assertEqual(self.client.get('/auth/login').status_code, 200)
        self.assertEqual(self.client.get('/auth/register').status_code, 200)
        self.assertEqual(self.client.get('/payments/support').status_code, 200)

        r_v2 = self.client.get('/v2/dashboard?tab=active')
        self.assertEqual(r_v2.status_code, 302)
        self.assertEqual(r_v2.headers['Location'], '/dashboard?tab=active')

        for protected in ('/dashboard', '/tracking/add?q=SPXVN123', '/settings', '/developers', '/admin/'):
            res = self.client.get(protected)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/auth/login', res.headers['Location'])
            self.assertNotIn('/v1/', res.headers['Location'])

    def test_register_renders_validation_errors(self):
        with patch('app.auth.forms.UsersRepo.get_by_username', return_value=self.user):
            res = self.client.post(
                '/auth/register',
                data={'username': 'alice', 'password': 'abc', 'confirm_password': 'xyz'},
            )
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Tên đăng nhập đã tồn tại', html)
        self.assertIn('role="alert"', html)

    def test_primary_dashboard_add_detail_refresh_delete(self):
        self.login_session()
        with patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]):
            dash = self.client.get('/dashboard')
            self.assertEqual(dash.status_code, 200)
            self.assertIn('SPXVN0123456789', dash.get_data(as_text=True))

        add_get = self.client.get('/tracking/add?q=SPXVN999999')
        self.assertEqual(add_get.status_code, 200)
        self.assertIn('SPXVN999999', add_get.get_data(as_text=True))

        with patch('app.v2.routes.TrackingService.create_tracking_for_user', return_value={'success': True, 'tracking_id': 'trk-101'}):
            add_post = self.client.post(
                '/tracking/add',
                data={'tracking_number': 'SPXVN999999', 'carrier_id': 'auto', 'alias': 'Chuột mới'},
            )
            self.assertEqual(add_post.status_code, 302)
            self.assertTrue(add_post.headers['Location'].endswith('/dashboard'))

        with patch('app.v2.routes.TrackingsRepo.get_by_id', return_value=self.sample_tracking):
            detail = self.client.get('/tracking/trk-100')
            self.assertEqual(detail.status_code, 200)
            self.assertIn('Rời kho trung chuyển', detail.get_data(as_text=True))

            with patch('app.v2.routes.TrackingService.refresh_tracking', return_value=True):
                ref = self.client.post('/tracking/trk-100/refresh', data={'next': '/dashboard'})
                self.assertEqual(ref.status_code, 302)
                self.assertEqual(ref.headers['Location'], '/dashboard')

            with patch('app.v2.routes.TrackingsRepo.delete') as mock_del:
                dele = self.client.post('/tracking/trk-100/delete')
                self.assertEqual(dele.status_code, 302)
                mock_del.assert_called_once_with('trk-100')

    def test_developers_portal_key_and_webhook_management(self):
        self.login_session()
        dev_page = self.client.get('/developers')
        self.assertEqual(dev_page.status_code, 200)
        self.assertIn(self.api_key_prefix, dev_page.get_data(as_text=True))

        with patch('app.v2.routes.UsersRepo.update_partner_api') as mock_upd:
            gen_res = self.client.post('/developers/api-key/generate', follow_redirects=True)
            self.assertEqual(gen_res.status_code, 200)
            self.assertIn('oth_live_', gen_res.get_data(as_text=True))
            mock_upd.assert_called_once()

    def test_partner_rest_api_endpoints(self):
        # Unauthenticated rejected
        self.assertEqual(self.client.get('/api/v1/trackings').status_code, 401)
        self.assertEqual(
            self.client.get('/api/v1/trackings', headers={'Authorization': 'Bearer invalid'}).status_code,
            401,
        )

        # Public health & carriers
        self.assertEqual(self.client.get('/api/v1/health').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/carriers').status_code, 200)

        headers = {'Authorization': f'Bearer {self.raw_api_key}'}

        with patch('app.api.routes.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]):
            list_res = self.client.get('/api/v1/trackings?status=active', headers=headers)
            self.assertEqual(list_res.status_code, 200)
            body = list_res.get_json()
            self.assertTrue(body['success'])
            self.assertEqual(body['data'][0]['trackingNumber'], 'SPXVN0123456789')
            self.assertEqual(body['data'][0]['externalRef'], 'ORD-55')

            by_num = self.client.get('/api/v1/trackings/by-number/SPXVN0123456789', headers=headers)
            self.assertEqual(by_num.status_code, 200)
            self.assertEqual(by_num.get_json()['data']['id'], 'trk-100')

        with patch('app.api.routes.TrackingService.create_tracking_for_user', return_value={'success': True, 'tracking_id': 'trk-100'}), \
             patch('app.api.routes.TrackingsRepo.update') as mock_upd, \
             patch('app.api.routes.TrackingsRepo.get_by_id', return_value=self.sample_tracking):
            create_res = self.client.post(
                '/api/v1/trackings',
                headers=headers,
                json={'tracking_number': 'SPXVN0123456789', 'alias': 'Tai nghe', 'external_ref': 'ORD-55'},
            )
            self.assertEqual(create_res.status_code, 201)
            mock_upd.assert_called_once_with('trk-100', {'externalRef': 'ORD-55'})

        # SSRF private IP blocked when TESTING=False
        self.app.config['TESTING'] = False
        self.app.config['DEBUG'] = False
        bad_wh = self.client.put(
            '/api/v1/webhook',
            headers=headers,
            json={'webhook_url': 'https://192.168.1.10/hook', 'enabled': True},
        )
        self.assertEqual(bad_wh.status_code, 422)
        self.app.config['TESTING'] = True

    def test_signed_outbound_webhook_delivery_and_tracking_service_trigger(self):
        headers = {'X-API-Key': self.raw_api_key}
        captured = {}

        def fake_post(url, data, headers, timeout):
            captured['url'] = url
            captured['body'] = data
            captured['headers'] = headers
            resp = MagicMock()
            resp.status_code = 200
            return resp

        with patch('app.api.webhooks.requests.post', side_effect=fake_post), \
             patch('app.api.webhooks.UsersRepo.update_partner_api'):
            test_res = self.client.post('/api/v1/webhook/test', headers=headers)
            self.assertEqual(test_res.status_code, 200)
            self.assertTrue(test_res.get_json()['data']['delivered'])

        ts = int(captured['headers']['X-OrderTracker-Timestamp'])
        expected_sig = sign_webhook_payload(self.wh_secret, ts, captured['body'])
        self.assertEqual(captured['headers']['X-OrderTracker-Signature'], expected_sig)
        parsed = json.loads(captured['body'].decode('utf-8'))
        self.assertEqual(parsed['event'], 'webhook.test')

        # Verify TrackingService.refresh_tracking triggers PartnerWebhookService.notify_tracking_updated on new events
        from app.tracking.services import TrackingService

        fake_provider = MagicMock()
        fake_provider.id = 'spx_vn'
        fake_provider.displayName = 'Shopee Express VN'
        fake_provider.is_final_status.return_value = True
        fake_provider.format_time.return_value = '10:00 18/11/2026'
        fake_provider.track.return_value = TrackingResult(
            trackingNumber='SPXVN0123456789',
            carrierId='spx_vn',
            currentStatus='Giao hàng thành công',
            lastEventTime=datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc),
            events=[
                TrackingEvent(
                    eventHash='ev_new_delivered',
                    code='DELIVERED',
                    name='Giao hàng thành công',
                    descBuyer='Người nhận đã nhận hàng.',
                    descSeller='',
                    milestoneCode=4,
                    milestoneName='Delivered',
                    actualTime=datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc),
                    currentLocation=TrackingLocation(address='Quận 7, TP.HCM'),
                )
            ],
        )

        with self.app.app_context(), \
             patch('app.tracking.services.TrackingsRepo.get_by_id', return_value=self.sample_tracking), \
             patch('app.tracking.services.TrackingsRepo.update'), \
             patch('app.tracking.services.registry.get_provider', return_value=fake_provider), \
             patch('app.tracking.services.NotificationService.send_to_user'), \
             patch('app.api.webhooks.PartnerWebhookService.notify_tracking_updated') as mock_wh:
            ok = TrackingService.refresh_tracking('trk-100')
            self.assertTrue(ok)
            mock_wh.assert_called_once()
            self.assertTrue(mock_wh.call_args.kwargs['is_final'])


if __name__ == '__main__':
    unittest.main()
