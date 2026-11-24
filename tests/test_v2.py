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

    def test_theme_toggle_present_and_legacy_footer_link_removed(self):
        guest_html = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="v2-theme-toggle"', guest_html)
        self.assertIn("localStorage.getItem('v2_theme')", guest_html)
        self.assertNotIn('data-v2-i18n="footer.classic"', guest_html)
        self.assertNotIn('Giao diện cũ (v1)', guest_html)

        self.login_session()
        with patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]):
            dash_html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('id="v2-theme-toggle"', dash_html)
        self.assertNotIn('data-v2-i18n="footer.classic"', dash_html)
        self.assertNotIn('Giao diện cũ (v1)', dash_html)
        self.assertNotIn('href="/v1/dashboard"', dash_html)

    def test_favicon_config_dropdown_order_and_landing_sections(self):
        fav = self.client.get('/favicon.ico')
        self.assertEqual(fav.status_code, 200)
        fav.close()

        home_html = self.client.get('/').get_data(as_text=True)
        self.assertIn('favicon.svg', home_html)
        self.assertIn('v2-ledger-section', home_html)
        self.assertIn('v2-omni-stage', home_html)
        self.assertIn('v2-partner-stage', home_html)
        self.assertIn('v2-closing-bar', home_html)

        self.login_session()
        with patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]):
            nav_html = self.client.get('/dashboard').get_data(as_text=True)

        nav_segment = nav_html.split('class="v2-nav-list"', 1)[1].split('</nav>', 1)[0]
        pos_add = nav_segment.index('data-v2-i18n="nav.add"')
        pos_cfg = nav_segment.index('id="v2-config-toggle"')
        pos_notify = nav_segment.index('data-v2-i18n="nav.notifications"')
        pos_dev = nav_segment.index('data-v2-i18n="nav.developers"')
        pos_admin = nav_segment.index('data-v2-i18n="nav.admin"')
        pos_docs = nav_segment.index('data-v2-i18n="nav.docs"')
        self.assertTrue(pos_add < pos_cfg < pos_notify < pos_dev < pos_admin < pos_docs)

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

    def test_duplicate_tracking_prevention_and_normalization(self):
        from app.tracking.services import TrackingService

        with self.app.app_context(), patch(
            'app.repos.trackings_repo.TrackingsRepo.get_user_trackings',
            return_value=[self.sample_tracking],
        ), patch('app.repos.trackings_repo.TrackingsRepo.create') as mock_create:
            # Lowercase + zero-width space + whitespace still detected as duplicate!
            dup_res = TrackingService.create_tracking_for_user(
                user=self.user,
                tracking_number='  \u200bspxvn0123456789  ',
                alias='Trùng lặp',
            )
            self.assertFalse(dup_res['success'])
            self.assertTrue(dup_res['duplicate'])
            self.assertEqual(dup_res['tracking_id'], 'trk-100')
            mock_create.assert_not_called()

        # Web POST /tracking/add redirects directly to existing detail page on duplicate
        self.login_session()
        with patch('app.repos.trackings_repo.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]):
            web_dup = self.client.post(
                '/tracking/add',
                data={'tracking_number': 'spxvn0123456789', 'carrier_id': 'auto', 'alias': 'Test'},
            )
            self.assertEqual(web_dup.status_code, 302)
            self.assertTrue(web_dup.headers['Location'].endswith('/tracking/trk-100'))

        # Partner API returns 409 Conflict with duplicate_tracking code
        headers = {'Authorization': f'Bearer {self.raw_api_key}'}
        with patch('app.repos.trackings_repo.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]), \
             patch('app.api.routes.TrackingsRepo.get_by_id', return_value=self.sample_tracking):
            api_dup = self.client.post(
                '/api/v1/trackings',
                headers=headers,
                json={'tracking_number': 'spxvn0123456789'},
            )
            self.assertEqual(api_dup.status_code, 409)
            self.assertEqual(api_dup.get_json()['error']['code'], 'duplicate_tracking')

    def test_edit_alias_cod_note_and_active_cod_summary_edge_cases(self):
        self.login_session()

        # Invalid COD amount on /tracking/add rejected cleanly
        bad_cod = self.client.post(
            '/tracking/add',
            data={'tracking_number': 'SPXVN888888', 'carrier_id': 'auto', 'cod_amount': '-5000'},
        )
        self.assertEqual(bad_cod.status_code, 200)
        self.assertIn('không được âm', bad_cod.get_data(as_text=True))

        # Dashboard sums ONLY active non-cancelled COD
        items = [
            {**self.sample_tracking, 'id': 't1', 'isActive': True, 'codAmount': 150000, 'currentStatus': 'Đang giao hàng'},
            {**self.sample_tracking, 'id': 't2', 'isActive': False, 'codAmount': 500000, 'currentStatus': 'Giao thành công'},
            {**self.sample_tracking, 'id': 't3', 'isActive': True, 'codAmount': 900000, 'currentStatus': 'Đơn hàng đã hủy'},
        ]
        with patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=items):
            dash = self.client.get('/dashboard')
            html = dash.get_data(as_text=True)
            self.assertIn('150.000 ₫', html)
            self.assertNotIn('1.550.000 ₫', html)

        # POST /tracking/<id>/edit updates alias, formatted COD ("250.000"), and note
        with patch('app.v2.routes.TrackingsRepo.get_by_id', return_value=self.sample_tracking), \
             patch('app.v2.routes.TrackingsRepo.update') as mock_upd:
            ed = self.client.post(
                '/tracking/trk-100/edit',
                data={'alias': 'Bàn phím mới', 'cod_amount': '250.000', 'note': 'Giao giờ hành chính'},
            )
            self.assertEqual(ed.status_code, 302)
            mock_upd.assert_called_once_with('trk-100', {
                'alias': 'Bàn phím mới',
                'codAmount': 250000,
                'note': 'Giao giờ hành chính',
            })

        # Non-owner edit attempt -> 403
        other_trk = {**self.sample_tracking, 'userId': 'u-other'}
        with patch('app.v2.routes.TrackingsRepo.get_by_id', return_value=other_trk):
            self.assertEqual(self.client.post('/tracking/trk-100/edit', data={'alias': 'Hack'}).status_code, 403)

        # Partner API PATCH /api/v1/trackings/<id>
        headers = {'Authorization': f'Bearer {self.raw_api_key}'}
        with patch('app.api.routes.TrackingsRepo.get_by_id', return_value=self.sample_tracking), \
             patch('app.api.routes.TrackingsRepo.update') as mock_api_upd:
            patch_res = self.client.patch(
                '/api/v1/trackings/trk-100',
                headers=headers,
                json={'alias': 'API Alias', 'cod_amount': 320000, 'note': 'Fragile'},
            )
            self.assertEqual(patch_res.status_code, 200)
            mock_api_upd.assert_called_once_with('trk-100', {
                'alias': 'API Alias',
                'codAmount': 320000,
                'note': 'Fragile',
            })

    def test_public_share_link_privacy_masking_and_revocation(self):
        self.login_session()
        jnt_trk = {
            **self.sample_tracking,
            'id': 'trk-jnt-share',
            'trackingNumber': '841092837465-4829',
            'carrierId': 'jt_express',
            'codAmount': 185000,
            'note': 'Mật khẩu cổng nhà riêng 1234',
            'externalRef': 'SECRET-ERP-99',
        }

        captured_token = {}
        def save_share(tid, data):
            captured_token.update(data)

        with patch('app.v2.routes.TrackingsRepo.get_by_id', return_value=jnt_trk), \
             patch('app.v2.routes.TrackingsRepo.update', side_effect=save_share):
            sh = self.client.post('/tracking/trk-jnt-share/share')
            self.assertEqual(sh.status_code, 302)
            self.assertTrue(len(captured_token.get('shareToken', '')) >= 16)

        token = captured_token['shareToken']
        shared_doc = {**jnt_trk, 'shareToken': token}

        # Logout and view as anonymous visitor
        self.client.get('/auth/logout')
        with patch('app.v2.routes.TrackingsRepo.get_by_share_token', return_value=shared_doc):
            pub = self.client.get(f'/s/{token}')
            self.assertEqual(pub.status_code, 200)
            self.assertEqual(pub.headers.get('X-Robots-Tag'), 'noindex, nofollow')
            pub_html = pub.get_data(as_text=True)
            # Masks phone suffix, shows COD, hides private note & externalRef & userId!
            self.assertIn('841092837465-**29', pub_html)
            self.assertNotIn('841092837465-4829', pub_html)
            self.assertIn('185.000 ₫', pub_html)
            self.assertNotIn('Mật khẩu cổng nhà riêng 1234', pub_html)
            self.assertNotIn('SECRET-ERP-99', pub_html)
            self.assertNotIn('u-v2', pub_html)

        # Invalid or revoked share link -> clean 404
        with patch('app.v2.routes.TrackingsRepo.get_by_share_token', return_value=None):
            revoked = self.client.get('/s/invalid_or_revoked_token_12345')
            self.assertEqual(revoked.status_code, 404)

    def test_telegram_mini_app_hmac_auth_and_pwa_assets(self):
        import time as _time
        from urllib.parse import urlencode

        # PWA endpoints
        mf = self.client.get('/manifest.webmanifest')
        self.assertEqual(mf.status_code, 200)
        self.assertEqual(mf.get_json()['display'], 'standalone')
        mf.close()

        sw = self.client.get('/sw.js')
        self.assertEqual(sw.status_code, 200)
        self.assertEqual(sw.headers.get('Service-Worker-Allowed'), '/')
        sw.close()

        self.assertEqual(self.client.get('/offline').status_code, 200)
        self.assertEqual(self.client.get('/webapp').status_code, 200)

        # Telegram Mini App HMAC-SHA256 verification
        bot_tok = '999888:MINI_APP_SECRET_TOKEN'
        self.app.config['TELEGRAM_BOT_TOKEN'] = bot_tok

        def make_init_data(user_dict, auth_date, start_param='', tamper=False):
            fields = {
                'auth_date': str(auth_date),
                'query_id': 'AAHdF6IQAAAAAN0XohDhrOrc',
                'user': json.dumps(user_dict, separators=(',', ':')),
            }
            if start_param:
                fields['start_param'] = start_param
            dcs = '\n'.join(f'{k}={fields[k]}' for k in sorted(fields))
            skey = hmac.new(b'WebAppData', bot_tok.encode('utf-8'), hashlib.sha256).digest()
            sig = hmac.new(skey, dcs.encode('utf-8'), hashlib.sha256).hexdigest()
            if tamper:
                sig = ('0' if sig[0] != '0' else '1') + sig[1:]
            fields['hash'] = sig
            return urlencode(fields)

        now_ts = int(_time.time())
        valid_init = make_init_data({'id': 777888, 'first_name': 'Alice'}, now_ts, start_param='add')

        with patch('app.v2.routes.UsersRepo.get_or_create_temp_by_telegram_chat_id', return_value=self.user):
            ok_res = self.client.post('/auth/telegram-webapp', json={'initData': valid_init})
            self.assertEqual(ok_res.status_code, 200)
            self.assertEqual(ok_res.get_json()['redirect'], '/tracking/add')

        # Tampered hash -> 401
        bad_sig = make_init_data({'id': 777888, 'first_name': 'Alice'}, now_ts, tamper=True)
        self.assertEqual(self.client.post('/auth/telegram-webapp', json={'initData': bad_sig}).status_code, 401)

        # Expired auth_date (> 24h old) -> 401
        expired = make_init_data({'id': 777888, 'first_name': 'Alice'}, now_ts - 90000)
        self.assertEqual(self.client.post('/auth/telegram-webapp', json={'initData': expired}).status_code, 401)

        # Bot account -> 401
        bot_init = make_init_data({'id': 777888, 'first_name': 'Bot', 'is_bot': True}, now_ts)
        self.assertEqual(self.client.post('/auth/telegram-webapp', json={'initData': bot_init}).status_code, 401)

    def test_delivery_addresses_crud_single_default_and_dashboard_filtering(self):
        self.login_session()

        # 1. Without any addresses: dashboard behaves normally, no address bar shown
        with patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]):
            dash_no_addr = self.client.get('/dashboard').get_data(as_text=True)
        self.assertNotIn('class="v2-address-bar"', dash_no_addr)
        self.assertIn('data-v2-i18n="nav.addresses"', dash_no_addr)
        self.assertIn('/settings/addresses', dash_no_addr)

        # 2. Address book CRUD + enforce at most 1 default address
        stored_addresses = []

        def fake_update_addresses(uid, addrs):
            stored_addresses.clear()
            stored_addresses.extend(addrs)
            return list(stored_addresses)

        with patch('app.v2.routes.UsersRepo.update_addresses', side_effect=fake_update_addresses), \
             patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=[self.sample_tracking]):
            # GET empty address book
            page_empty = self.client.get('/settings/addresses')
            self.assertEqual(page_empty.status_code, 200)
            self.assertIn('Chưa có địa chỉ nhận hàng nào', page_empty.get_data(as_text=True))

            # Add first address (default)
            r1 = self.client.post(
                '/settings/addresses',
                data={
                    'name': 'Nhà riêng',
                    'detail': '123 Nguyễn Huệ, Quận 1, TP.HCM',
                    'note': 'Gửi bảo vệ tầng 1',
                    'is_default': 'y',
                },
            )
            self.assertEqual(r1.status_code, 302)
            self.assertEqual(len(stored_addresses), 1)
            self.assertTrue(stored_addresses[0]['isDefault'])
            home_id = stored_addresses[0]['id']

            # Add second address also marked default -> must clear default on first
            r2 = self.client.post(
                '/settings/addresses',
                data={
                    'name': 'Công ty',
                    'detail': '456 Lê Lợi, Quận 1, TP.HCM',
                    'note': 'Giờ hành chính',
                    'is_default': 'y',
                },
            )
            self.assertEqual(r2.status_code, 302)
            self.assertEqual(len(stored_addresses), 2)
            defaults = [a for a in stored_addresses if a['isDefault']]
            self.assertEqual(len(defaults), 1)
            self.assertEqual(defaults[0]['name'], 'Công ty')
            office_id = defaults[0]['id']

            # Edit first address
            r_edit = self.client.post(
                f'/settings/addresses/{home_id}/edit',
                data={
                    'name': 'Nhà bố mẹ',
                    'detail': '789 Pasteur, Quận 3',
                    'note': 'Gọi trước khi giao',
                },
            )
            self.assertEqual(r_edit.status_code, 302)
            edited = next(a for a in stored_addresses if a['id'] == home_id)
            self.assertEqual(edited['name'], 'Nhà bố mẹ')
            self.assertEqual(edited['detail'], '789 Pasteur, Quận 3')

            # Switch default back to home_id
            r_def = self.client.post(f'/settings/addresses/{home_id}/default')
            self.assertEqual(r_def.status_code, 302)
            self.assertEqual(self.user.get_default_address()['id'], home_id)

            # 3. Dashboard defaults to filtering by default address (home_id)
            trk_home = {**self.sample_tracking, 'id': 'trk-home', 'addressId': home_id, 'codAmount': 120000}
            trk_office = {
                **self.sample_tracking,
                'id': 'trk-office',
                'trackingNumber': 'LEX1234567890',
                'carrierId': 'lex',
                'alias': 'Bàn phím văn phòng',
                'addressId': office_id,
                'codAmount': 350000,
            }
            with patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=[trk_home, trk_office]):
                dash_html = self.client.get('/dashboard').get_data(as_text=True)
                self.assertIn('class="v2-address-bar"', dash_html)
                self.assertIn(f'let activeAddress = "{home_id}"', dash_html)
                self.assertIn('120.000 ₫', dash_html)

                # Explicit ?address=all overrides default filter
                dash_all = self.client.get('/dashboard?address=all').get_data(as_text=True)
                self.assertIn('let activeAddress = "all"', dash_all)
                self.assertIn('470.000 ₫', dash_all)

            # 4. Add tracking pre-selects default address and passes address_id
            add_html = self.client.get('/tracking/add').get_data(as_text=True)
            self.assertIn('Nhà bố mẹ (Mặc định)', add_html)
            with patch('app.v2.routes.TrackingService.create_tracking_for_user', return_value={'success': True, 'tracking_id': 'trk-new'}) as mock_create:
                res_add = self.client.post(
                    '/tracking/add',
                    data={
                        'tracking_number': 'SPXVN888888888',
                        'carrier_id': 'auto',
                        'alias': 'Đơn nhà',
                        'address_id': office_id,
                    },
                )
                self.assertEqual(res_add.status_code, 302)
                self.assertEqual(mock_create.call_args.kwargs.get('address_id'), office_id)

            # 5. Detail page displays address & edit_tracking updates addressId
            with patch('app.v2.routes.TrackingsRepo.get_by_id', return_value=trk_home), \
                 patch('app.v2.routes.TrackingsRepo.update') as mock_upd:
                detail_html = self.client.get('/tracking/trk-home').get_data(as_text=True)
                self.assertIn('Nhà bố mẹ', detail_html)
                self.assertIn('789 Pasteur, Quận 3', detail_html)

                res_upd = self.client.post(
                    '/tracking/trk-home/edit',
                    data={'alias': 'Tai nghe', 'address_id': office_id, 'cod_amount': '120000', 'note': ''},
                )
                self.assertEqual(res_upd.status_code, 302)
                mock_upd.assert_called_once_with('trk-home', {
                    'alias': 'Tai nghe',
                    'addressId': office_id,
                    'codAmount': 120000,
                    'note': None,
                })

            # 6. Unset default -> dashboard falls back to 'all'
            self.client.post(f'/settings/addresses/{home_id}/default', data={'unset': '1'})
            self.assertIsNone(self.user.get_default_address())
            with patch('app.v2.routes.TrackingsRepo.get_user_trackings', return_value=[trk_home, trk_office]):
                dash_no_def = self.client.get('/dashboard').get_data(as_text=True)
                self.assertIn('let activeAddress = "all"', dash_no_def)

            # 7. Delete address removes it cleanly
            r_del = self.client.post(f'/settings/addresses/{office_id}/delete')
            self.assertEqual(r_del.status_code, 302)
            self.assertEqual(len(stored_addresses), 1)


if __name__ == '__main__':
    unittest.main()
