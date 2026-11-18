import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash

from app import create_app
from app.notifications.telegram_bot import _handle_message
from app.notifications.telegram_group import (
    build_popup_summary_for_user,
    handle_callback_query,
    handle_inline_query,
)
from app.repos.users_repo import User


class TelegramGroupBotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env_file = Path(self.tmp.name) / '.env'
        conf_file = Path(self.tmp.name) / 'config.conf'
        env_file.write_text("PAYOS_API_KEY='test'\n", encoding='utf-8')
        conf_file.write_text("POLL_INTERVAL_SECONDS='300'\n", encoding='utf-8')

        self.env_patch = patch.dict(
            os.environ,
            ENV_FILE=str(env_file),
            CONF_FILE=str(conf_file),
            MANAGED_RESTART='0',
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

        with patch('app.init_firebase'), patch('app.init_gateways'), patch('app.init_notification_providers'):
            self.app = create_app()

        self.app.config.update(
            TESTING=True,
            TELEGRAM_BOT_TOKEN='123456:TEST_TOKEN',
            TELEGRAM_BOT_USERNAME='OrderTrackerTestBot',
            ADMIN_TELEGRAM_USER_ID='777888',
            WEBSITE_URL='https://tracker.example.com',
        )

        self.user_a = User(
            'u-alice',
            'tg_111_aaaa',
            generate_password_hash('pw'),
            settings={'telegramChatId': '111', 'notifyEnabled': True, 'telegramEnabled': True, 'channels': ['telegram']},
            is_temporary=True,
            link_token='secret-link-token-alice',
        )
        self.user_b = User(
            'u-bob',
            'bob',
            generate_password_hash('pw'),
            settings={'telegramChatId': '222', 'notifyEnabled': True, 'telegramEnabled': True, 'channels': ['telegram']},
            is_temporary=False,
        )
        self.admin_user = User(
            'u-admin',
            'admin',
            generate_password_hash('pw'),
            settings={'telegramChatId': '777888', 'notifyEnabled': True, 'telegramEnabled': True, 'channels': ['telegram']},
            is_temporary=False,
            telegram_verified_id='777888',
        )

        self.users_by_tg = {
            '111': self.user_a,
            '222': self.user_b,
            '777888': self.admin_user,
        }
        self.users_by_id = {u.id: u for u in self.users_by_tg.values()}

        self.trackings = {
            'trk-a1': {
                'id': 'trk-a1',
                'userId': 'u-alice',
                'trackingNumber': 'SPXVN111111',
                'carrierId': 'spx_vn',
                'alias': 'Bàn phím cơ Keychron',
                'isActive': True,
                'currentStatus': 'Tài xế đang giao hàng',
                'events': [{'currentLocation': {'address': 'Quận 7, TP.HCM'}}],
            },
            'trk-b1': {
                'id': 'trk-b1',
                'userId': 'u-bob',
                'trackingNumber': 'LEXPU222222',
                'carrierId': 'lex',
                'alias': 'Tai nghe chống ồn Sony',
                'isActive': True,
                'currentStatus': 'Đã đến kho phân loại',
                'events': [],
            },
        }

        p_get_tg = patch(
            'app.repos.users_repo.UsersRepo.get_by_telegram_chat_id',
            side_effect=lambda cid: self.users_by_tg.get(str(cid)),
        )
        p_get_or_create = patch(
            'app.repos.users_repo.UsersRepo.get_or_create_temp_by_telegram_chat_id',
            side_effect=lambda cid: self.users_by_tg.get(str(cid)),
        )
        p_get_uid = patch(
            'app.repos.users_repo.UsersRepo.get_by_id',
            side_effect=lambda uid: self.users_by_id.get(uid),
        )
        p_user_trks = patch(
            'app.repos.trackings_repo.TrackingsRepo.get_user_trackings',
            side_effect=lambda uid: [t for t in self.trackings.values() if t['userId'] == uid],
        )
        p_trk_by_id = patch(
            'app.repos.trackings_repo.TrackingsRepo.get_by_id',
            side_effect=lambda tid: self.trackings.get(tid),
        )
        for p in (p_get_tg, p_get_or_create, p_get_uid, p_user_trks, p_trk_by_id):
            p.start()
            self.addCleanup(p.stop)

    def test_private_chat_flow_remains_intact_and_supports_start_list_deeplink(self):
        sent_private = []
        with patch(
            'app.notifications.telegram_bot.TelegramNotifier.send_message',
            side_effect=lambda cid, text, **kw: sent_private.append((str(cid), text, kw)) or True,
        ):
            _handle_message(self.app, {
                'message_id': 1,
                'chat': {'id': 222, 'type': 'private'},
                'from': {'id': 222, 'first_name': 'Bob'},
                'text': '/list',
            })

        self.assertEqual(len(sent_private), 1)
        self.assertEqual(sent_private[0][0], '222')
        self.assertIn('#LEXPU222222', sent_private[0][1])

        # Deep-link /start list in private chat opens DM management menu directly
        api_calls = []
        with patch(
            'app.notifications.telegram_group.tg_api_call',
            side_effect=lambda app, method, payload, **kw: api_calls.append((method, payload)) or {'ok': True},
        ), patch('app.notifications.telegram_bot.TelegramNotifier.send_message', return_value=True):
            _handle_message(self.app, {
                'message_id': 2,
                'chat': {'id': 222, 'type': 'private'},
                'from': {'id': 222, 'first_name': 'Bob'},
                'text': '/start list',
            })
        self.assertEqual(api_calls[0][0], 'sendMessage')
        self.assertEqual(api_calls[0][1]['chat_id'], '222')
        self.assertIn('Tai nghe chống ồn Sony', api_calls[0][1]['text'])

    def test_group_list_is_neutral_and_popup_isolates_each_member(self):
        api_calls = []
        with patch(
            'app.notifications.telegram_group.tg_api_call',
            side_effect=lambda app, method, payload, **kw: api_calls.append((method, payload)) or {'ok': True},
        ):
            # Alice calls /list@OrderTrackerTestBot inside a Forum Supergroup topic
            _handle_message(self.app, {
                'message_id': 50,
                'message_thread_id': 9,
                'chat': {'id': -100999888, 'type': 'supergroup'},
                'from': {'id': 111, 'username': 'alice'},
                'text': '/list@OrderTrackerTestBot',
            })

            self.assertEqual(len(api_calls), 1)
            method, group_payload = api_calls[0]
            self.assertEqual(method, 'sendMessage')
            self.assertEqual(group_payload['chat_id'], -100999888)
            self.assertEqual(group_payload['message_thread_id'], 9)
            self.assertEqual(group_payload['reply_parameters']['message_id'], 50)
            # Zero order names or codes leaked in the group message or button labels!
            serialized = repr(group_payload)
            self.assertNotIn('Bàn phím cơ', serialized)
            self.assertNotIn('SPXVN111111', serialized)
            self.assertNotIn('Tai nghe', serialized)

            # Alice clicks [👁 Xem nhanh (Popup)] -> sees ONLY Alice's order via show_alert=True
            api_calls.clear()
            handle_callback_query(self.app, {
                'id': 'cb-alice',
                'from': {'id': 111, 'username': 'alice'},
                'data': 'grp:popup',
            })
            self.assertEqual(api_calls[0][0], 'answerCallbackQuery')
            self.assertTrue(api_calls[0][1]['show_alert'])
            self.assertLessEqual(len(api_calls[0][1]['text']), 200)
            self.assertIn('Bàn phím cơ', api_calls[0][1]['text'])
            self.assertNotIn('Tai nghe', api_calls[0][1]['text'])

            # Bob clicks the EXACT SAME button -> sees ONLY Bob's order!
            api_calls.clear()
            handle_callback_query(self.app, {
                'id': 'cb-bob',
                'from': {'id': 222, 'username': 'bob'},
                'data': 'grp:popup',
            })
            self.assertTrue(api_calls[0][1]['show_alert'])
            self.assertIn('Tai nghe', api_calls[0][1]['text'])
            self.assertNotIn('Bàn phím cơ', api_calls[0][1]['text'])

    def test_popup_summary_respects_200_char_telegram_limit_with_many_orders(self):
        many = [
            {
                'id': f'trk-{i}',
                'userId': 'u-alice',
                'trackingNumber': f'SPXVN00000000{i:02d}',
                'alias': f'Đơn hàng thử nghiệm số {i} rất dài',
                'isActive': True,
                'currentStatus': 'Đang vận chuyển qua trạm trung chuyển khu vực',
            }
            for i in range(15)
        ]
        with self.app.app_context(), patch('app.repos.trackings_repo.TrackingsRepo.get_user_trackings', return_value=many):
            summary = build_popup_summary_for_user('111')
        self.assertLessEqual(len(summary), 200)
        self.assertIn('đơn khác', summary)

    def test_group_inline_query_sets_is_personal_and_filters_per_caller(self):
        api_calls = []
        with patch(
            'app.notifications.telegram_group.tg_api_call',
            side_effect=lambda app, method, payload, **kw: api_calls.append((method, payload)) or {'ok': True},
        ):
            handle_inline_query(self.app, {
                'id': 'iq-1',
                'from': {'id': 111, 'username': 'alice'},
                'query': '',
            })

        self.assertEqual(api_calls[0][0], 'answerInlineQuery')
        iq_payload = api_calls[0][1]
        self.assertTrue(iq_payload['is_personal'])
        self.assertEqual(len(iq_payload['results']), 1)
        self.assertIn('Bàn phím cơ Keychron', iq_payload['results'][0]['title'])

    def test_group_add_sends_details_to_dm_masks_phone_and_hides_link_token(self):
        api_calls = []
        new_trk = {
            'id': 'trk-jnt',
            'userId': 'u-alice',
            'trackingNumber': '841092837465-4829',
            'carrierId': 'jt_express',
            'alias': 'Chuột gaming',
            'isActive': True,
            'currentStatus': 'Đã lấy hàng',
        }
        self.trackings['trk-jnt'] = new_trk

        with patch(
            'app.notifications.telegram_group.TrackingService.create_tracking_for_user',
            return_value={'success': True, 'tracking_id': 'trk-jnt', 'carrier_id': 'jt_express'},
        ) as mock_create, patch(
            'app.notifications.telegram_group.tg_api_call',
            side_effect=lambda app, method, payload, **kw: api_calls.append((method, payload)) or {'ok': True},
        ):
            _handle_message(self.app, {
                'message_id': 77,
                'chat': {'id': -100999888, 'type': 'group'},
                'from': {'id': 111, 'username': 'alice'},
                'text': '/add 841092837465-4829 Chuột gaming',
            })

        # Bound strictly to Alice (user_a), never to the group chat!
        self.assertEqual(mock_create.call_args.kwargs['user'].id, 'u-alice')

        dm_call = next(p for m, p in api_calls if m == 'sendMessage' and p['chat_id'] == '111')
        grp_call = next(p for m, p in api_calls if m == 'sendMessage' and p['chat_id'] == -100999888)

        # Full tracking code & link token go ONLY to Alice's DM
        self.assertIn('841092837465-4829', dm_call['text'])
        self.assertIn('secret-link-token-alice', repr(dm_call.get('reply_markup')))

        # Group message masks phone digits and NEVER contains Alice's secret link token
        self.assertIn('841092837465-**29', grp_call['text'])
        self.assertNotIn('4829', grp_call['text'])
        self.assertNotIn('secret-link-token-alice', repr(grp_call))

    def test_cross_user_remove_and_forged_callbacks_are_blocked(self):
        api_calls = []
        with patch('app.repos.trackings_repo.TrackingsRepo.delete') as mock_del, patch(
            'app.notifications.telegram_group.tg_api_call',
            side_effect=lambda app, method, payload, **kw: api_calls.append((method, payload)) or {'ok': True},
        ):
            # Bob tries to /remove Alice's tracking code in group
            _handle_message(self.app, {
                'message_id': 88,
                'chat': {'id': -100999888, 'type': 'supergroup'},
                'from': {'id': 222, 'username': 'bob'},
                'text': '/remove SPXVN111111',
            })
            mock_del.assert_not_called()
            self.assertIn('Không tìm thấy', api_calls[-1][1]['text'])

            # Bob tries forged delete callback on Alice's tracking ID
            api_calls.clear()
            handle_callback_query(self.app, {
                'id': 'cb-forged',
                'from': {'id': 222, 'username': 'bob'},
                'data': 'dm:d:trk-a1',
            })
            mock_del.assert_not_called()
            self.assertTrue(api_calls[0][1]['show_alert'])
            self.assertIn('không có quyền', api_calls[0][1]['text'])

            # Alice deletes her own tracking -> allowed!
            api_calls.clear()
            _handle_message(self.app, {
                'message_id': 89,
                'chat': {'id': -100999888, 'type': 'supergroup'},
                'from': {'id': 111, 'username': 'alice'},
                'text': '/remove SPXVN111111',
            })
            mock_del.assert_called_once_with('trk-a1')

    def test_other_bot_commands_anonymous_sender_and_admin_link_protection(self):
        api_calls = []
        with patch(
            'app.notifications.telegram_group.tg_api_call',
            side_effect=lambda app, method, payload, **kw: api_calls.append((method, payload)) or {'ok': True},
        ):
            # Command meant for a different bot in the group -> ignored completely
            _handle_message(self.app, {
                'message_id': 90,
                'chat': {'id': -100999888, 'type': 'supergroup'},
                'from': {'id': 111, 'username': 'alice'},
                'text': '/list@AnotherBot',
            })
            self.assertEqual(len(api_calls), 0)

            # Anonymous group admin sender_chat -> rejected safely
            _handle_message(self.app, {
                'message_id': 91,
                'chat': {'id': -100999888, 'type': 'supergroup'},
                'from': {'id': 1087968824, 'is_bot': True, 'username': 'GroupAnonymousBot'},
                'sender_chat': {'id': -100999888, 'title': 'Group'},
                'text': '/list',
            })
            self.assertIn('ẩn danh', api_calls[-1][1]['text'])

            # Admin types /admin in group -> secret token URL goes ONLY to Admin DM (777888), NEVER to group!
            api_calls.clear()
            _handle_message(self.app, {
                'message_id': 92,
                'chat': {'id': -100999888, 'type': 'supergroup'},
                'from': {'id': 777888, 'username': 'sysadmin'},
                'text': '/admin',
            })
            dm_msg = next(p for m, p in api_calls if m == 'sendMessage' and p['chat_id'] == '777888')
            grp_msg = next(p for m, p in api_calls if m == 'sendMessage' and p['chat_id'] == -100999888)
            self.assertIn('/admin/verify?token=', dm_msg['text'])
            self.assertNotIn('token=', grp_msg['text'])


if __name__ == '__main__':
    unittest.main()
