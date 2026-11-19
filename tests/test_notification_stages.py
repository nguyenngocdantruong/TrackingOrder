import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from flask import Flask

from app import create_app
from app.providers.base import TrackingEvent, TrackingResult
from app.repos.users_repo import User
from app.tracking.services import TrackingService
from app.tracking.stages import (
    STAGE_IDS, StageProfile, PROFILES, classify_event, selected_stages, wants_stage,
)


class StageClassificationTests(unittest.TestCase):
    def test_specific_codes_override_coarse_milestones(self):
        for code, expected in [('F100', 'picked_up'), ('F098', 'picked_up'),
                               ('F599', 'at_delivery_station'), ('F598', 'at_delivery_station'),
                               ('F510', 'in_transit')]:
            with self.subTest(code=code):
                self.assertEqual(classify_event('shopee_express_vn', {
                    'code': code, 'milestoneCode': 5, 'milestoneName': 'In transit',
                }), expected)

    def test_lex_stages_do_not_depend_on_zero_milestone(self):
        cases = {
            'cb_pre_accept': 'preparing', 'cb_uplifted': 'in_transit',
            'cb_pre_transport': 'in_transit', 'cb_customs_clearance_success': 'in_transit',
            'domestic_package_stationed_in': 'at_delivery_station',
            'domestic_package_stationed_out': 'out_for_delivery',
            'domestic_redelivery': 'out_for_delivery',
            'domestic_1st_attempt_failed': 'out_for_delivery',
            'domestic_delivered': 'delivered',
        }
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(classify_event('lex', {'code': code, 'milestoneCode': 0}), expected)
        self.assertIsNone(classify_event('lex', {'code': 'brand_new', 'milestoneCode': 0}))

    def test_jt_ambiguous_codes_use_description(self):
        for description, expected in [
            ('Nhân viên của bưu cục đang giao hàng.', 'out_for_delivery'),
            ('Đơn hàng đã ký nhận. Người ký nhận là: khách hàng', 'delivered'),
        ]:
            self.assertEqual(classify_event('jt_express', {
                'code': 'PROCESSING', 'descBuyer': description,
            }), expected)
        self.assertIsNone(classify_event('jt_express', {
            'code': 'PICKED_UP', 'name': 'Đã nhận hàng', 'milestoneName': 'Picked Up',
            'descBuyer': 'Đã đăng ký Kiện Vấn Đề',
        }))
        self.assertEqual(classify_event('jt_express', {
            'code': 'PICKED_UP', 'descBuyer': 'Nhân viên đã nhận hàng.',
        }), 'picked_up')

    def test_new_provider_can_add_profile_without_changing_filter(self):
        with patch.dict(PROFILES, {'new_carrier': StageProfile(codes={'arrived': 'at_delivery_station'})}):
            self.assertEqual(classify_event('new_carrier', {'code': 'ARRIVED'}), 'at_delivery_station')
        self.assertEqual(classify_event('new_carrier', {'name': 'Out for delivery'}), 'out_for_delivery')
        self.assertIsNone(classify_event('new_carrier', {'milestoneCode': 8}))

    def test_preference_defaults_empty_and_unknown(self):
        for settings in ({}, None, {'notifyStages': None}):
            self.assertEqual(selected_stages(settings), list(STAGE_IDS))
            self.assertTrue(wants_stage(settings, None))
        for value in ([], ['delivered'], 'delivered'):
            self.assertFalse(wants_stage({'notifyStages': value}, None))
        self.assertFalse(wants_stage({'notifyStages': []}, 'delivered'))
        self.assertTrue(wants_stage({'notifyStages': ['delivered']}, 'delivered'))


class StageNotificationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.now = datetime(2026, 11, 19, tzinfo=timezone.utc)
        self.old = self.event('old', 'F100', -1).to_dict()
        self.tracking = {
            'userId': 'test-user', 'carrierId': 'shopee_express_vn',
            'trackingNumber': 'TEST', 'events': [self.old],
        }

    def event(self, event_hash, code, minutes):
        return TrackingEvent(event_hash, code, code, 'Synthetic event', '', 5,
                             'In transit', self.now + timedelta(minutes=minutes))

    def refresh(self, events, settings):
        provider = MagicMock()
        provider.track.return_value = TrackingResult('TEST', 'shopee_express_vn',
                                                     'In transit', self.now, events)
        provider.is_final_status.return_value = False
        provider.format_time.return_value = '12:00'
        with self.app.app_context(), \
             patch('app.tracking.services.registry.get_provider', return_value=provider), \
             patch('app.tracking.services.TrackingsRepo.get_by_id', return_value=self.tracking), \
             patch('app.tracking.services.TrackingsRepo.update') as update, \
             patch('app.repos.users_repo.UsersRepo.get_by_id', return_value=SimpleNamespace(settings=settings)), \
             patch('app.tracking.services.NotificationService.send_to_user') as send, \
             patch('app.api.webhooks.PartnerWebhookService.notify_tracking_updated') as webhook:
            self.assertTrue(TrackingService.refresh_tracking('test-tracking'))
        return send, update, webhook

    def test_multiple_events_in_same_stage_and_no_repeat_on_next_poll(self):
        events = [self.event('a', 'F510', 0), self.event('b', 'F540', 1)]
        send, update, _ = self.refresh(events, {'notifyStages': ['in_transit']})
        self.assertEqual(send.call_count, 2)
        self.assertIn('F510', send.call_args_list[0].args[1])
        self.assertIn('F540', send.call_args_list[1].args[1])
        self.tracking.update(update.call_args.args[1])
        send, _, _ = self.refresh(events, {'notifyStages': ['in_transit']})
        send.assert_not_called()

    def test_mixed_batch_only_sends_selected_events_and_still_updates_webhook(self):
        events = [self.event('transit', 'F510', 0), self.event('delivery', 'F600', 1)]
        send, update, webhook = self.refresh(events, {'notifyStages': ['in_transit']})
        send.assert_called_once()
        self.assertIn('F510', send.call_args.args[1])
        self.assertIn('Trạng thái: Đang vận chuyển', send.call_args.args[1])
        self.assertNotIn('F600', send.call_args.args[1])
        self.assertEqual(len(update.call_args.args[1]['events']), 3)
        self.assertEqual(len(webhook.call_args.kwargs['new_events']), 2)

    def test_none_selected_or_global_off_still_saves_tracking(self):
        for settings in ({'notifyStages': []}, {'notifyEnabled': False}):
            with self.subTest(settings=settings):
                send, update, webhook = self.refresh([self.event('new', 'F600', 1)], settings)
                send.assert_not_called()
                update.assert_called_once()
                webhook.assert_called_once()

    def test_initial_sync_only_latest_event_and_deduplicates_response(self):
        self.tracking['events'] = []
        latest = self.event('latest', 'F600', 1)
        send, update, _ = self.refresh([self.event('earlier', 'F510', 0), latest, latest], {})
        send.assert_called_once()
        self.assertIn('F600', send.call_args.args[1])
        self.assertEqual(len(update.call_args.args[1]['events']), 2)


class StageSettingsTests(unittest.TestCase):
    def setUp(self):
        with patch('app.init_firebase'), patch('app.init_gateways'), patch('app.init_notification_providers'):
            self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY='test-stages')
        self.user = User('stage-user', 'test', '', settings={'notifyEnabled': True, 'unrelated': 'keep'})
        self.client = self.app.test_client()
        self.loader = patch('app.repos.users_repo.UsersRepo.get_by_id', return_value=self.user)
        self.loader.start()
        self.addCleanup(self.loader.stop)
        with self.client.session_transaction() as session:
            session['_user_id'] = self.user.id
            session['_fresh'] = True

    def test_both_settings_pages_default_and_saved_selection(self):
        for path in ('/settings', '/v1/settings/'):
            for value in (None, [], ['delivered', 'out_for_delivery']):
                with self.subTest(path=path, value=value):
                    self.user.settings['notifyStages'] = value
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    soup = BeautifulSoup(response.data, 'html.parser')
                    fields = soup.select('input[name="notify_stages"]')
                    self.assertEqual(len(fields), 6)
                    checked = [item['value'] for item in fields if item.has_attr('checked')]
                    self.assertEqual(checked, list(STAGE_IDS) if value is None else
                                     [stage for stage in STAGE_IDS if stage in value])

    def test_save_subset_empty_and_reject_unknown_on_both_routes(self):
        for path in ('/settings', '/v1/settings/'):
            for value in (['delivered'], [], ['not-a-stage']):
                with self.subTest(path=path, value=value), \
                     patch('app.repos.users_repo.UsersRepo.update_settings') as save:
                    response = self.client.post(path, data={
                        'notify_stages': value, 'notify_enabled': 'y',
                    })
                    if value == ['not-a-stage']:
                        self.assertEqual(response.status_code, 200)
                        save.assert_not_called()
                    else:
                        self.assertEqual(response.status_code, 302)
                        stored = save.call_args.args[1]
                        self.assertEqual(stored['notifyStages'], value)
                        self.assertEqual(stored['unrelated'], 'keep')


if __name__ == '__main__':
    unittest.main()
