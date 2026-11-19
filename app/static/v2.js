(() => {
  'use strict';

  /* ==========================================================================
     1. Complete Bilingual Dictionary (VI / EN) Across All Screens & Docs
     ========================================================================== */
  const DICT = {
    vi: {
      'a11y.skip': 'Chuyển đến nội dung chính',
      'a11y.open_menu': 'Mở trình đơn điều hướng',
      'a11y.close_toast': 'Đóng thông báo',

      'common.copy': 'Sao chép',
      'common.copy_short': 'Chép',
      'common.enable': 'Kích hoạt',
      'common.unchecked': 'Chưa kiểm tra',
      'common.unsynced': 'Chưa đồng bộ',

      'status.active': 'Đang theo dõi',
      'status.completed': 'Đã hoàn tất',
      'status.cancelled': 'Đã hủy / Hoàn',
      'status.ended': 'Đã kết thúc',

      'nav.dashboard': 'Đơn hàng',
      'nav.add': 'Thêm đơn',
      'nav.config': 'Cấu hình',
      'nav.notifications': 'Thông báo',
      'nav.notifications_desc': 'Telegram & Zalo Bot',
      'nav.developers': 'API Đối tác',
      'nav.developers_desc': 'API Key & Webhook',
      'nav.docs': 'Tài liệu API',
      'nav.support': 'Ủng hộ',
      'nav.admin': 'Quản trị',
      'nav.admin_desc': 'Tham số hệ thống',
      'nav.login': 'Đăng nhập',
      'nav.register': 'Đăng ký',
      'nav.logout': 'Đăng xuất',
      'footer.tagline': 'Order Tracking Hub · Theo dõi vận đơn tập trung qua Telegram, Zalo & Partner API.',
      'theme.to_dark': 'Chuyển sang chế độ tối',
      'theme.to_light': 'Chuyển sang chế độ sáng',

      'landing.title': 'Theo dõi mọi kiện hàng tập trung, báo tin tức thì',
      'landing.lead.prefix': 'Quản lý toàn bộ hành trình đơn hàng từ',
      'landing.lead.suffix': 'tại một bảng điều khiển duy nhất, tự động gửi thông báo ngay khi bưu cục cập nhật.',
      'landing.input.placeholder': 'Dán mã vận đơn (SPXVN…, LEX…, J&T…)',
      'landing.cta.track': 'Theo dõi ngay',
      'landing.cta.dashboard': 'Mở bảng điều khiển',
      'landing.cta.register': 'Tạo tài khoản miễn phí',
      'landing.partner_badge': 'REST API & Webhook',
      'landing.demo.item': 'Bàn phím cơ Keychron Q1',
      'landing.demo.badge': 'Dữ liệu minh họa',
      'landing.demo.ev1_title': 'Tài xế đang giao hàng đến bạn',
      'landing.demo.ev1_time': '08:45 · Hôm nay',
      'landing.demo.ev1_desc': 'Bưu tá khu vực Quận 7 đang trên tuyến phát kiện hàng.',
      'landing.demo.ev2_title': 'Đã đến kho phân loại TP.HCM',
      'landing.demo.ev2_time': '05:20 · Hôm nay',
      'landing.demo.ev2_desc': 'Hoàn tất khai thác tại trung tâm trung chuyển Củ Chi.',
      'landing.demo.push_title': 'Thông báo & Webhook tự động vừa gửi',

      'landing.ledger.heading': 'Nhận diện tự động hãng vận chuyển & chuẩn hóa hành trình',
      'landing.ledger.sub': 'Dán mã đơn nguyên bản từ sàn thương mại điện tử — hệ thống tự phân tích định dạng, quy chiếu về 4 chặng giao nhận thống nhất và khử trùng lặp sự kiện.',
      'landing.carrier.spx_rule': 'Nhận diện tức thì tiền tố SPXVN… và đồng bộ chi tiết trạm trung chuyển, bưu cục phát.',
      'landing.carrier.lex_rule': 'Hỗ trợ chuỗi mã LEX / LEXPU / LEXST và lưu vết đầy đủ lịch sử khai thác kho phân loại.',
      'landing.carrier.jnt_rule': 'Kết hợp mã vận đơn cùng 4 chữ số cuối SĐT người nhận để xác thực tra cứu chính xác.',
      'landing.carrier.try': 'Thử mã mẫu',
      'landing.pipeline.label': 'Chuẩn hóa trạng thái thống nhất:',

      'landing.omni.heading': 'Theo dõi trên trình duyệt hoặc nhắn thẳng mã đơn cho Bot',
      'landing.omni.sub': 'Không cần mở từng ứng dụng mua sắm để làm mới thủ công. Thêm vận đơn từ bất kỳ kênh nào và nhận tin báo tự động ngay khi kiện hàng di chuyển.',
      'landing.omni.f1_title': 'Gửi mã đơn trực tiếp trong khung chat',
      'landing.omni.f1_desc': 'Nhắn mã vận đơn kèm tên gợi nhớ cho Telegram hoặc Zalo Bot để đăng ký theo dõi tức thì ngay trên điện thoại.',
      'landing.omni.f2_title': 'Đồng bộ hai chiều với tài khoản Web',
      'landing.omni.f2_desc': 'Liên kết một lần để toàn bộ danh sách kiện hàng trên Telegram, Zalo và bảng điều khiển trình duyệt luôn khớp nhau.',
      'landing.omni.f3_title': 'Khử trùng lặp, chỉ báo khi có mốc mới',
      'landing.omni.f3_desc': 'Đối chiếu mã băm từng sự kiện từ bưu cục, chỉ gửi tin nhắn khi đơn hàng thực sự phát sinh thay đổi trạng thái.',
      'landing.omni.live_tag': 'Tự động 24/7',

      'landing.chat.tg_user_note': 'Bàn phím cơ',
      'landing.chat.sent_now': 'Bạn · 08:10',
      'landing.chat.tg_ack_title': 'Đã thêm vận đơn Shopee Express VN',
      'landing.chat.tg_ack_body': 'Bàn phím cơ (SPXVN048291049281) đang ở trạng thái Đã đến kho phân loại TP.HCM. Bot sẽ nhắn ngay khi có mốc mới.',
      'landing.chat.tg_push_title': 'Cập nhật mới · Bàn phím cơ',
      'landing.chat.tg_push_body': 'Tài xế đang giao hàng đến bạn — Bưu tá khu vực Quận 7 đang trên tuyến phát kiện hàng.',
      'landing.chat.zl_user_note': 'Màn hình 27 inch',
      'landing.chat.zl_sent_time': 'Bạn · 14:05',
      'landing.chat.zl_ack_title': 'Đã đồng bộ Lazada Express',
      'landing.chat.zl_ack_body': 'Đơn Màn hình 27 inch đã gắn vào tài khoản của bạn trên cả Zalo và Web Dashboard.',
      'landing.chat.zl_push_title': 'Giao hàng thành công · Màn hình 27 inch',
      'landing.chat.zl_push_body': 'Kiện hàng LEXPU0391827364 đã được phát thành công tới người nhận. Tự động khép lại chu kỳ theo dõi.',

      'landing.api.heading': 'Tích hợp Partner REST API & Webhook ký số thời gian thực',
      'landing.api.sub': 'Kết nối cửa hàng thương mại điện tử, OMS hoặc ERP của bạn qua chuẩn JSON RESTful v1. Tự động nhận bản tin HTTP POST kèm chữ ký bảo mật ngay khi đơn hàng chuyển trạng thái.',
      'landing.api.p1': 'Xác thực linh hoạt qua Bearer Token hoặc X-API-Key, gắn mã tham chiếu nội bộ external_ref cho từng đơn.',
      'landing.api.p2': 'Đẩy sự kiện tracking.created, tracking.updated và tracking.completed tức thì tới HTTPS endpoint của đối tác.',
      'landing.api.p3': 'Chữ ký HMAC-SHA256 trên header X-OrderTracker-Signature chống giả mạo và phát lại bản tin.',
      'landing.api.cta_docs': 'Xem tài liệu tích hợp',
      'landing.api.cta_key': 'Quản lý API Key',

      'landing.close.heading': 'Sẵn sàng gom mọi vận đơn về một nơi duy nhất?',
      'landing.close.sub': 'Tạo tài khoản miễn phí trong vài giây, bật thông báo Telegram hoặc Zalo bất cứ lúc nào.',

      'dash.title': 'Vận đơn của tôi',
      'dash.subtitle': 'Theo dõi tiến trình vận chuyển thời gian thực từ mọi đơn vị giao nhận.',
      'dash.add': 'Thêm vận đơn',
      'dash.tab.all': 'Tất cả',
      'dash.tab.active': 'Đang theo dõi',
      'dash.tab.completed': 'Đã hoàn tất',
      'dash.search.placeholder': 'Tìm theo tên gợi nhớ hoặc mã đơn…',
      'dash.view.grid': 'Xem dạng thẻ',
      'dash.view.table': 'Xem dạng bảng gọn',
      'dash.status_label': 'Trạng thái mới nhất',
      'dash.detail': 'Chi tiết',
      'dash.refresh': 'Làm mới',
      'dash.tbl.parcel': 'Đơn hàng',
      'dash.tbl.carrier': 'Nhà vận chuyển',
      'dash.tbl.status': 'Trạng thái mới nhất',
      'dash.tbl.updated': 'Cập nhật',
      'dash.tbl.actions': 'Thao tác',
      'dash.filter_empty.title': 'Không tìm thấy vận đơn phù hợp',
      'dash.filter_empty.desc': 'Không có kiện hàng nào khớp với bộ lọc hoặc từ khóa tìm kiếm hiện tại.',
      'dash.filter_empty.reset': 'Xóa bộ lọc tìm kiếm',
      'dash.empty.title': 'Chưa có vận đơn nào đang theo dõi',
      'dash.empty.desc': 'Thêm mã vận đơn đầu tiên từ Shopee Express VN, Lazada Express hoặc J&T Express để tự động nhận thông báo hành trình.',
      'dash.empty.cta': 'Thêm vận đơn đầu tiên',
      'dash.notify_banner': 'Bạn chưa cấu hình nhận tin qua Telegram hoặc Zalo.',
      'dash.notify_cta': 'Thiết lập thông báo',
      'dash.cod_due': 'Tổng COD cần chuẩn bị:',

      'add.title': 'Thêm vận đơn mới',
      'add.subtitle': 'Dán mã vận đơn để hệ thống tự động nhận diện hãng vận chuyển và đồng bộ lịch sử ngay lập tức.',
      'add.tracking_number': 'Mã vận đơn',
      'add.tracking_hint': 'Hỗ trợ tự nhận diện Shopee Express VN (SPXVN…), Lazada Express (LEX…) và J&T Express (mã vận đơn kèm 4 số cuối SĐT).',
      'add.carrier': 'Đơn vị vận chuyển',
      'add.alias': 'Tên gợi nhớ (không bắt buộc)',
      'add.alias.placeholder': 'Ví dụ: Bàn phím cơ, Sách công nghệ, Quà tặng…',
      'add.cod': 'Tiền thu hộ COD — VND (không bắt buộc)',
      'add.cod.placeholder': '0 (Để trống nếu đã thanh toán trước)',
      'add.cod.prepaid': '0 ₫ · Trả trước',
      'add.note': 'Ghi chú nhận hàng (không bắt buộc)',
      'add.note.placeholder': 'Ví dụ: Nhờ lễ tân nhận giúp, đồng kiểm khi giao…',
      'add.submit': 'Bắt đầu theo dõi',
      'add.back': 'Quay lại danh sách',

      'detail.back': 'Đơn hàng',
      'detail.refresh': 'Làm mới trạng thái',
      'detail.edit': 'Sửa đơn / COD',
      'detail.share': 'Chia sẻ hành trình',
      'detail.delete': 'Xóa đơn',
      'detail.cancelled_prefix': 'Đơn hàng đã hủy hoặc hoàn trả:',
      'detail.info': 'Thông tin kiện hàng',
      'detail.dt.status': 'Trạng thái hiện tại',
      'detail.dt.carrier': 'Đơn vị vận chuyển',
      'detail.dt.code': 'Mã vận đơn',
      'detail.dt.cod': 'Tiền thu hộ (COD)',
      'detail.cod_zero': '0 ₫ · Đã trả trước',
      'detail.dt.note': 'Ghi chú nhận hàng',
      'detail.dt.checked': 'Kiểm tra gần nhất',
      'detail.dt.events': 'Tổng mốc sự kiện',
      'detail.events_unit': 'mốc hành trình',
      'detail.history': 'Lịch sử hành trình',
      'detail.no_history': 'Chưa ghi nhận mốc sự kiện nào từ nhà vận chuyển.',
      'detail.step1': 'Đã lấy hàng',
      'detail.step2': 'Đang trung chuyển',
      'detail.step3': 'Đang giao hàng',
      'detail.step4': 'Giao thành công',

      'edit.title': 'Cập nhật thông tin vận đơn',
      'edit.save': 'Lưu thay đổi',

      'share.active_label': 'Liên kết chia sẻ công khai đang bật:',
      'share.copy_link': 'Chép link',
      'share.revoke': 'Thu hồi link',
      'share.public_banner': 'Trang theo dõi hành trình công khai (chế độ chỉ đọc — thông tin cá nhân đã được ẩn).',
      'share.track_yours': 'Tự theo dõi đơn của bạn',
      'share.invalid.title': 'Liên kết theo dõi không khả dụng hoặc đã thu hồi',
      'share.invalid.desc': 'Người gửi có thể đã tắt chia sẻ công khai hoặc xóa vận đơn này khỏi hệ thống. Hãy yêu cầu liên kết mới nếu bạn vẫn đang chờ nhận hàng.',
      'share.invalid.cta': 'Về trang chủ Order Tracker',

      'webapp.connecting.title': 'Đang kết nối Telegram Mini App…',
      'webapp.connecting.desc': 'Đang xác thực chữ ký phiên Telegram của bạn để đồng bộ danh sách vận đơn.',
      'webapp.outside_tg': 'Trang này dành cho Telegram Mini App. Nếu bạn đang mở bằng trình duyệt thường, hãy đăng nhập trực tiếp bên dưới.',

      'offline.title': 'Thiết bị đang mất kết nối mạng',
      'offline.desc': 'Không thể tải dữ liệu vận đơn mới nhất lúc này. Hãy kiểm tra kết nối Wi-Fi hoặc dữ liệu di động rồi bấm thử lại.',
      'offline.retry': 'Thử kết nối lại',

      'delete.title': 'Xóa vận đơn khỏi danh sách?',
      'delete.cancel': 'Hủy bỏ',
      'delete.confirm': 'Xóa vĩnh viễn',

      'settings.title': 'Cài đặt thông báo',
      'settings.subtitle': 'Quản lý kênh nhận tin tự động qua Telegram, Zalo và kiểm tra kết nối bot.',
      'settings.partner_cta': 'Cấu hình API & Webhook',
      'settings.master.title': 'Thông báo đẩy tự động',
      'settings.master.desc': 'Gửi tin nhắn ngay khi đơn hàng chuyển sang trạng thái mới.',
      'settings.channel_toggle': 'Bật kênh',
      'settings.tg.title': 'Kênh Telegram',
      'settings.tg.desc': 'Nhận tin nhắn tự động từ bot Telegram chính thức.',
      'settings.tg.placeholder': 'Ví dụ: 987654321',
      'settings.zalo.title': 'Kênh Zalo',
      'settings.zalo.desc': 'Nhận tin nhắn cập nhật trực tiếp qua Zalo Bot.',
      'settings.zalo.placeholder': 'Dán Zalo Chat ID của bạn',
      'settings.zalo.help': 'Dán mã chat_id nhận được khi tương tác lệnh với Zalo Bot hoặc liên kết từ Zalo.',
      "settings.stages.title": "Thông báo theo giai đoạn",
      "settings.stages.help": "Nhận các cập nhật trong giai đoạn bạn chọn, kể cả nhiều cập nhật cùng giai đoạn. Bỏ chọn hết để tắt thông báo cập nhật giao hàng.",
      "settings.stages.all_help": "Chọn cả 6 để nhận mọi cập nhật, bao gồm các phát sinh khác. Cài đặt này áp dụng cho cả Telegram và Zalo khi thông báo tự động được bật.",
      "settings.stages.preparing": "Tiếp nhận / Chuẩn bị",
      "settings.stages.picked_up": "Đã lấy / nhận hàng",
      "settings.stages.in_transit": "Đang vận chuyển",
      "settings.stages.at_delivery_station": "Đến trạm giao hàng",
      "settings.stages.out_for_delivery": "Đang giao hàng",
      "settings.stages.delivered": "Đã giao",
      'settings.save': 'Lưu cài đặt thông báo',
      'settings.test_tg.title': 'Kiểm tra kết nối Telegram',
      'settings.test_tg.desc': 'Gửi một tin nhắn mẫu tới Telegram Chat ID đã lưu để xác nhận hoạt động.',
      'settings.test_tg.btn': 'Gửi tin thử Telegram',
      'settings.test_zalo.title': 'Kiểm tra kết nối Zalo',
      'settings.test_zalo.desc': 'Gửi một tin nhắn mẫu tới Zalo Chat ID đã lưu để xác nhận hoạt động.',
      'settings.test_zalo.btn': 'Gửi tin thử Zalo',

      'support.title': 'Ủng hộ duy trì hệ thống',
      'support.subtitle': 'Đóng góp của bạn giúp duy trì máy chủ và bot thông báo hoạt động ổn định 24/7.',
      'support.gateway_pending': 'Cổng thanh toán PayOS hiện đang bảo trì hoặc chưa được cấu hình. Vui lòng quay lại sau.',
      'support.amount_label': 'Mức ủng hộ (VND)',
      'support.amount_placeholder': 'Ví dụ: 50000',
      'support.name_label': 'Tên người ủng hộ',
      'support.name_placeholder': 'Tên hoặc biệt danh của bạn',
      'support.email_label': 'Địa chỉ Email',
      'support.message_label': 'Lời nhắn (không bắt buộc)',
      'support.message_placeholder': 'Gửi lời nhắn cho đội ngũ phát triển…',
      'support.method_label': 'Phương thức thanh toán',
      'support.method_value': 'Chuyển khoản VietQR · PayOS',
      'support.submit': 'Tạo liên kết ủng hộ qua PayOS',

      'login.title': 'Đăng nhập tài khoản',
      'login.subtitle': 'Truy cập bảng điều khiển để xem và quản lý các kiện hàng của bạn.',
      'login.username': 'Tên đăng nhập',
      'login.username.placeholder': 'Nhập tên đăng nhập',
      'login.password': 'Mật khẩu',
      'login.password.placeholder': 'Nhập mật khẩu',
      'login.submit': 'Đăng nhập',
      'login.no_account': 'Chưa có tài khoản?',
      'login.register_link': 'Đăng ký miễn phí',

      'register.title': 'Tạo tài khoản mới',
      'register.subtitle': 'Theo dõi không giới hạn vận đơn và nhận thông báo tức thì qua Telegram hoặc Zalo.',
      'register.username': 'Tên đăng nhập',
      'register.username.placeholder': 'Từ 2 đến 20 ký tự',
      'register.username.hint': 'Tên đăng nhập gồm 2–20 ký tự, dùng để đăng nhập trên trình duyệt.',
      'register.password': 'Mật khẩu',
      'register.password.placeholder': 'Nhập mật khẩu bảo mật',
      'register.confirm': 'Xác nhận mật khẩu',
      'register.confirm.placeholder': 'Nhập lại mật khẩu',
      'register.submit': 'Tạo tài khoản',
      'register.has_account': 'Đã có tài khoản?',
      'register.login_link': 'Đăng nhập ngay',

      'link_tg.title': 'Liên kết Telegram với tài khoản web',
      'link_tg.subtitle': 'Đặt tên đăng nhập và mật khẩu để đồng bộ toàn bộ vận đơn đang theo dõi trên Telegram lên trình duyệt.',
      'link_tg.username': 'Tên đăng nhập mới',
      'link_tg.password': 'Mật khẩu (tối thiểu 6 ký tự)',
      'link_tg.password.placeholder': 'Nhập mật khẩu ít nhất 6 ký tự',
      'link_tg.submit': 'Hoàn tất liên kết Telegram',

      'link_zalo.title': 'Liên kết Zalo với tài khoản web',
      'link_zalo.subtitle': 'Gắn Zalo vào tài khoản sẵn có hoặc khởi tạo tài khoản mới để đồng bộ vận đơn hai chiều.',
      'link_zalo.mode_label': 'Phương thức liên kết',
      'link_zalo.mode.existing': 'Đăng nhập tài khoản có sẵn',
      'link_zalo.mode.new': 'Tạo tài khoản mới',
      'link_zalo.existing_user': 'Tên đăng nhập hiện có',
      'link_zalo.existing_pwd': 'Mật khẩu hiện có',
      'link_zalo.existing_hint': 'Các vận đơn đã thêm qua Zalo trước đó sẽ được chuyển gộp vào tài khoản này.',
      'link_zalo.submit': 'Xác nhận liên kết Zalo',

      'dev.title': 'API Đối tác & Webhook',
      'dev.subtitle': 'Quản lý khóa xác thực REST API và nhận sự kiện đẩy thời gian thực khi vận đơn cập nhật.',
      'dev.open_docs': 'Xem tài liệu tích hợp',
      'dev.key_once_title': 'Hãy sao chép API Key ngay bây giờ — khóa đầy đủ chỉ hiển thị một lần duy nhất:',
      'dev.key_section.title': 'Khóa xác thực Partner API',
      'dev.key_section.desc': 'Dùng trong header Authorization: Bearer <API_KEY> hoặc X-API-Key khi gọi các endpoint /api/v1/*.',
      'dev.status.active': 'Đang hoạt động',
      'dev.status.none': 'Chưa khởi tạo',
      'dev.key_current_label': 'Khóa hiện hành',
      'dev.key_empty_hint': 'Chưa có khóa nào. Nhấn nút bên phải để cấp khóa mới.',
      'dev.btn.create_key': 'Tạo API Key',
      'dev.btn.rotate_key': 'Cấp lại API Key mới',
      'dev.btn.revoke_key': 'Thu hồi khóa',
      'dev.base_url_label': 'Địa chỉ gốc API (Base URL)',
      'dev.wh.title': 'Cấu hình Webhook nhận cập nhật',
      'dev.wh.desc': 'Hệ thống tự động gửi HTTP POST kèm chữ ký HMAC-SHA256 mỗi khi đơn hàng có mốc hành trình mới.',
      'dev.wh.enable_label': 'Bật Webhook',
      'dev.wh.url_label': 'Endpoint nhận sự kiện (HTTPS)',
      'dev.wh.url_help': 'Yêu cầu giao thức HTTPS trên môi trường thực tế và phản hồi mã 2xx trong vòng 8 giây.',
      'dev.wh.events_label': 'Sự kiện đăng ký nhận',
      'dev.ev.created': 'Khi vận đơn mới được khởi tạo qua Web, Bot hoặc API',
      'dev.ev.updated': 'Khi phát hiện mốc trạng thái vận chuyển mới từ hãng giao nhận',
      'dev.ev.completed': 'Khi đơn hàng giao thành công hoặc kết thúc hành trình',
      'dev.wh.save_btn': 'Lưu cấu hình Webhook',
      'dev.wh.secret_label': 'Khóa ký xác thực (Signing Secret — HMAC-SHA256)',
      'dev.wh.rotate_secret': 'Đổi Secret',
      'dev.wh.secret_empty': 'Khóa Signing Secret sẽ được tự động sinh ngay khi bạn lưu Webhook hoặc tạo API Key.',
      'dev.wh.last_delivery': 'Lần gửi gần nhất:',
      'dev.wh.no_delivery': 'Chưa có bản ghi gửi sự kiện nào.',
      'dev.wh.test_btn': 'Gửi Webhook thử nghiệm',

      'docs.title': 'Tài liệu tích hợp Partner API & Webhook',
      'docs.subtitle': 'Hướng dẫn kết nối REST API v1 và xác thực sự kiện Webhook thời gian thực dành cho hệ thống đối tác thứ ba.',
      'docs.cta_keys': 'Quản lý API Key & Webhook',
      'docs.cta_get_key': 'Đăng nhập lấy API Key',
      'docs.toc.overview': '1. Tổng quan & Xác thực',
      'docs.toc.carriers': '2. Danh sách nhà vận chuyển',
      'docs.toc.trackings': '3. Quản lý vận đơn',
      'docs.toc.webhooks': '4. Tích hợp Webhook',
      'docs.toc.signature': '5. Xác minh chữ ký bảo mật',
      'docs.toc.errors': '6. Mã lỗi chuẩn',
      'docs.s1.title': '1. Tổng quan & Xác thực',
      'docs.s2.title': '2. Danh sách nhà vận chuyển hỗ trợ',
      'docs.s3.title': '3. Quản lý & Đồng bộ vận đơn',
      'docs.s3.create': 'Đăng ký theo dõi vận đơn mới',
      'docs.s3.other': 'Các endpoint tra cứu, làm mới & xóa',
      'docs.s4.title': '4. Nhận cập nhật thời gian thực qua Webhook',
      'docs.s5.title': '5. Xác minh chữ ký bảo mật HMAC-SHA256',
      'docs.s6.title': '6. Mã trạng thái HTTP & Xử lý lỗi',
      'docs.tbl.carrier_name': 'Đơn vị vận chuyển',
      'docs.tbl.example': 'Định dạng mẫu',
      'docs.tbl.field': 'Trường dữ liệu',
      'docs.tbl.type': 'Kiểu',
      'docs.tbl.desc': 'Mô tả',
      'docs.tbl.trigger': 'Thời điểm kích hoạt',
      'docs.tbl.meaning': 'Ý nghĩa',

      'admin.title': 'Cấu hình hệ thống',
      'admin.subtitle': 'Quản lý tham số đồng bộ vận đơn, cổng thanh toán PayOS và kết nối bot Telegram/Zalo.',
      'admin.group.tracking.title': 'Theo dõi đơn hàng',
      'admin.group.tracking.desc': 'Điều chỉnh việc nhận và cập nhật vận đơn.',
      'admin.group.payos.title': 'PayOS',
      'admin.group.payos.desc': 'Quản lý cổng thanh toán và thông tin kết nối.',
      'admin.group.telegram.title': 'Telegram',
      'admin.group.telegram.desc': 'Kết nối bot nhận lệnh và gửi thông báo vận đơn.',
      'admin.group.zalo.title': 'Zalo',
      'admin.group.zalo.desc': 'Kết nối bot Zalo qua polling.',
      'admin.field.TRACKING_ENABLED': 'Cho phép theo dõi',
      'admin.field.SCHEDULER_ENABLED': 'Tự động cập nhật',
      'admin.field.POLL_INTERVAL_SECONDS': 'Chu kỳ cập nhật (giây)',
      'admin.field.MAX_EVENTS_PER_TRACKING': 'Số sự kiện tối đa mỗi đơn',
      'admin.field.PAYOS_ENABLED': 'Bật PayOS',
      'admin.field.PAYOS_CLIENT_ID': 'Client ID',
      'admin.field.PAYOS_API_KEY': 'API key',
      'admin.field.PAYOS_CHECKSUM_KEY': 'Checksum key',
      'admin.field.PAYOS_RETURN_URL': 'URL thanh toán thành công',
      'admin.field.PAYOS_CANCEL_URL': 'URL hủy thanh toán',
      'admin.field.PAYOS_DONATION_AMOUNT': 'Số tiền mặc định (VND)',
      'admin.field.DONATE_NOTIFY_ALL': 'Thông báo ủng hộ cho mọi người',
      'admin.field.TELEGRAM_ENABLED': 'Bật Telegram bot',
      'admin.field.TELEGRAM_BOT_TOKEN': 'Bot token',
      'admin.field.TELEGRAM_BOT_USERNAME': 'Tên bot',
      'admin.field.ZALO_ENABLED': 'Bật Zalo bot',
      'admin.field.ZALO_BOT_TOKEN': 'Bot token',
      'admin.field.ZALO_BOT_UID': 'Bot UID',
      'admin.secret.configured': 'Đã cấu hình',
      'admin.secret.unconfigured': 'Chưa cấu hình',
      'admin.secret.placeholder': 'Nhập khóa mới để thay đổi',
      'admin.secret.hint': 'Để trống nếu muốn giữ nguyên khóa bảo mật hiện tại.',
      'admin.save.clean': 'Chưa có thay đổi',
      'admin.save.desc': 'Lưu toàn bộ mục cấu hình vào .env / config.conf và áp dụng cho dịch vụ.',
      'admin.save.btn': 'Lưu & áp dụng',
      'admin.verify.title': 'Xác nhận quyền quản trị',
      'admin.verify.subtitle': 'Liên kết một lần từ Telegram Bot sẽ xác thực danh tính quản trị viên cho tài khoản web đang đăng nhập.',
      'admin.verify.btn': 'Xác nhận & mở bảng quản trị',
      'admin.saved.title': 'Đã lưu cấu hình hệ thống',
      'admin.saved.auto': 'Dịch vụ đang tự động khởi động lại để áp dụng thay đổi mới. Vui lòng đợi vài giây trước khi mở lại trang quản trị.',
      'admin.saved.manual': 'Các tệp cấu hình đã được ghi thành công. Khởi động lại ứng dụng để áp dụng toàn bộ thay đổi.',
      'admin.saved.back_admin': 'Quay lại trang quản trị',
      'admin.saved.back_dash': 'Về bảng điều khiển'
    },
    en: {
      'a11y.skip': 'Skip to main content',
      'a11y.open_menu': 'Toggle navigation menu',
      'a11y.close_toast': 'Dismiss notification',

      'common.copy': 'Copy',
      'common.copy_short': 'Copy',
      'common.enable': 'Enable',
      'common.unchecked': 'Not checked yet',
      'common.unsynced': 'Not synced yet',

      'status.active': 'Active',
      'status.completed': 'Completed',
      'status.cancelled': 'Cancelled / Returned',
      'status.ended': 'Closed',

      'nav.dashboard': 'Shipments',
      'nav.add': 'Add Parcel',
      'nav.config': 'Settings',
      'nav.notifications': 'Notifications',
      'nav.notifications_desc': 'Telegram & Zalo Bots',
      'nav.developers': 'Partner API',
      'nav.developers_desc': 'API Keys & Webhooks',
      'nav.docs': 'API Docs',
      'nav.support': 'Support',
      'nav.admin': 'Admin',
      'nav.admin_desc': 'System parameters',
      'nav.login': 'Sign in',
      'nav.register': 'Create account',
      'nav.logout': 'Sign out',
      'footer.tagline': 'Order Tracking Hub · Centralized parcel tracking via Telegram, Zalo & Partner API.',
      'theme.to_dark': 'Switch to dark mode',
      'theme.to_light': 'Switch to light mode',

      'landing.title': 'Track every parcel in one place with instant alerts',
      'landing.lead.prefix': 'Monitor every shipment milestone across',
      'landing.lead.suffix': 'from one unified workspace, with automatic alerts pushed the moment your parcel moves.',
      'landing.input.placeholder': 'Paste tracking code (SPXVN…, LEX…, J&T…)',
      'landing.cta.track': 'Track parcel',
      'landing.cta.dashboard': 'Open dashboard',
      'landing.cta.register': 'Create free account',
      'landing.partner_badge': 'REST API & Webhooks',
      'landing.demo.item': 'Keychron Q1 Mechanical Keyboard',
      'landing.demo.badge': 'Sample preview',
      'landing.demo.ev1_title': 'Courier is out for delivery',
      'landing.demo.ev1_time': '08:45 · Today',
      'landing.demo.ev1_desc': 'District 7 delivery driver is en route to recipient.',
      'landing.demo.ev2_title': 'Arrived at Ho Chi Minh sorting hub',
      'landing.demo.ev2_time': '05:20 · Today',
      'landing.demo.ev2_desc': 'Completed processing at Cu Chi distribution center.',
      'landing.demo.push_title': 'Instant alert & webhook dispatched',

      'landing.ledger.heading': 'Automatic carrier detection & normalized transit stages',
      'landing.ledger.sub': 'Paste raw marketplace tracking numbers — the hub detects the carrier format, maps checkpoints onto 4 unified milestones, and deduplicates events.',
      'landing.carrier.spx_rule': 'Detects SPXVN… prefixes immediately and syncs sorting hubs and local delivery stations.',
      'landing.carrier.lex_rule': 'Supports LEX / LEXPU / LEXST codes with complete fulfillment center checkpoint history.',
      'landing.carrier.jnt_rule': 'Combines the waybill number with the recipient’s last 4 phone digits for verified lookup.',
      'landing.carrier.try': 'Try sample',
      'landing.pipeline.label': 'Unified milestone pipeline:',

      'landing.omni.heading': 'Track on the web or message the bot directly',
      'landing.omni.sub': 'Stop opening separate shopping apps to refresh by hand. Add parcels from any channel and get notified the moment a courier scans your package.',
      'landing.omni.f1_title': 'Paste tracking codes straight into chat',
      'landing.omni.f1_desc': 'Send a tracking number and optional label to the Telegram or Zalo Bot to start monitoring right from your phone.',
      'landing.omni.f2_title': 'Two-way sync with your web workspace',
      'landing.omni.f2_desc': 'Link once so every parcel across Telegram, Zalo, and the browser dashboard stays in lockstep.',
      'landing.omni.f3_title': 'Zero duplicate noise — only real changes',
      'landing.omni.f3_desc': 'Checkpoints are fingerprinted by event hash so alerts fire only when a genuinely new carrier scan arrives.',
      'landing.omni.live_tag': 'Automated 24/7',

      'landing.chat.tg_user_note': 'Mechanical keyboard',
      'landing.chat.sent_now': 'You · 08:10',
      'landing.chat.tg_ack_title': 'Added Shopee Express VN parcel',
      'landing.chat.tg_ack_body': 'Mechanical keyboard (SPXVN048291049281) is currently at Ho Chi Minh sorting hub. You will be alerted on the next scan.',
      'landing.chat.tg_push_title': 'New checkpoint · Mechanical keyboard',
      'landing.chat.tg_push_body': 'Courier is out for delivery — District 7 delivery driver is en route to recipient.',
      'landing.chat.zl_user_note': '27-inch monitor',
      'landing.chat.zl_sent_time': 'You · 14:05',
      'landing.chat.zl_ack_title': 'Lazada Express synced',
      'landing.chat.zl_ack_body': '27-inch monitor is now linked across both your Zalo chat and Web Dashboard.',
      'landing.chat.zl_push_title': 'Delivered · 27-inch monitor',
      'landing.chat.zl_push_body': 'Parcel LEXPU0391827364 was delivered to the recipient. Active polling closed automatically.',

      'landing.api.heading': 'Integrate Partner REST API & signed real-time Webhooks',
      'landing.api.sub': 'Connect your storefront, OMS, or ERP over clean JSON REST v1 endpoints. Receive signed HTTP POST webhooks the instant any shipment updates.',
      'landing.api.p1': 'Authenticate via Bearer token or X-API-Key and attach your internal external_ref order ID to every shipment.',
      'landing.api.p2': 'Push tracking.created, tracking.updated, and tracking.completed events directly to your HTTPS endpoint.',
      'landing.api.p3': 'Verify payload authenticity and prevent replay attacks with HMAC-SHA256 on X-OrderTracker-Signature.',
      'landing.api.cta_docs': 'Read integration docs',
      'landing.api.cta_key': 'Manage API Keys',

      'landing.close.heading': 'Ready to centralize every parcel in one place?',
      'landing.close.sub': 'Create a free account in seconds and connect Telegram or Zalo alerts whenever you like.',

      'dash.title': 'My Shipments',
      'dash.subtitle': 'Monitor live delivery progress across all supported carriers.',
      'dash.add': 'Add parcel',
      'dash.tab.all': 'All',
      'dash.tab.active': 'Active',
      'dash.tab.completed': 'Completed',
      'dash.search.placeholder': 'Filter by alias or tracking code…',
      'dash.view.grid': 'Card grid view',
      'dash.view.table': 'Compact table view',
      'dash.status_label': 'Latest status',
      'dash.detail': 'Details',
      'dash.refresh': 'Refresh',
      'dash.tbl.parcel': 'Shipment',
      'dash.tbl.carrier': 'Carrier',
      'dash.tbl.status': 'Latest status',
      'dash.tbl.updated': 'Updated',
      'dash.tbl.actions': 'Actions',
      'dash.filter_empty.title': 'No matching shipments',
      'dash.filter_empty.desc': 'No parcels match the active status tab or search query.',
      'dash.filter_empty.reset': 'Clear search & filters',
      'dash.empty.title': 'No shipments tracked yet',
      'dash.empty.desc': 'Add your first tracking code from Shopee Express VN, Lazada Express, or J&T Express to start receiving live updates.',
      'dash.empty.cta': 'Add first parcel',
      'dash.notify_banner': 'You have not connected Telegram or Zalo alerts yet.',
      'dash.notify_cta': 'Configure alerts',
      'dash.cod_due': 'Active COD due:',

      'add.title': 'Add New Parcel',
      'add.subtitle': 'Paste a tracking code to auto-detect the carrier and sync its latest history immediately.',
      'add.tracking_number': 'Tracking number',
      'add.tracking_hint': 'Automatically detects Shopee Express VN (SPXVN…), Lazada Express (LEX…), and J&T Express (code + last 4 phone digits).',
      'add.carrier': 'Carrier',
      'add.alias': 'Label / Alias (optional)',
      'add.alias.placeholder': 'e.g. Mechanical keyboard, Tech books, Gift…',
      'add.cod': 'Cash on Delivery / COD — VND (optional)',
      'add.cod.placeholder': '0 (Leave blank if prepaid)',
      'add.cod.prepaid': '0 ₫ · Prepaid',
      'add.note': 'Delivery note (optional)',
      'add.note.placeholder': 'e.g. Leave at reception desk, inspect on delivery…',
      'add.submit': 'Start tracking',
      'add.back': 'Back to shipments',

      'detail.back': 'Shipments',
      'detail.refresh': 'Refresh status',
      'detail.edit': 'Edit / COD',
      'detail.share': 'Share timeline',
      'detail.delete': 'Delete',
      'detail.cancelled_prefix': 'Order cancelled or returned:',
      'detail.info': 'Shipment summary',
      'detail.dt.status': 'Current status',
      'detail.dt.carrier': 'Carrier',
      'detail.dt.code': 'Tracking number',
      'detail.dt.cod': 'Cash on delivery (COD)',
      'detail.cod_zero': '0 ₫ · Prepaid',
      'detail.dt.note': 'Delivery note',
      'detail.dt.checked': 'Last checked',
      'detail.dt.events': 'Total checkpoints',
      'detail.events_unit': 'checkpoints',
      'detail.history': 'Tracking timeline',
      'detail.no_history': 'No carrier checkpoints have been recorded yet.',
      'detail.step1': 'Picked up',
      'detail.step2': 'In transit',
      'detail.step3': 'Out for delivery',
      'detail.step4': 'Delivered',

      'edit.title': 'Edit shipment details',
      'edit.save': 'Save changes',

      'share.active_label': 'Public tracking link is active:',
      'share.copy_link': 'Copy link',
      'share.revoke': 'Revoke link',
      'share.public_banner': 'Public read-only shipment timeline (personal details are hidden).',
      'share.track_yours': 'Track your own parcels',
      'share.invalid.title': 'Tracking link unavailable or revoked',
      'share.invalid.desc': 'The sender may have turned off public sharing or removed this parcel. Request a fresh link if you are still expecting delivery.',
      'share.invalid.cta': 'Go to Order Tracker home',

      'webapp.connecting.title': 'Connecting Telegram Mini App…',
      'webapp.connecting.desc': 'Verifying your signed Telegram session to sync tracked parcels.',
      'webapp.outside_tg': 'This entry point is for Telegram Mini App. In a regular browser, sign in directly below.',

      'offline.title': 'You are currently offline',
      'offline.desc': 'Live shipment updates cannot be loaded right now. Check your Wi-Fi or mobile data and try again.',
      'offline.retry': 'Try again',

      'delete.title': 'Delete this shipment?',
      'delete.cancel': 'Cancel',
      'delete.confirm': 'Delete permanently',

      'settings.title': 'Notification Settings',
      'settings.subtitle': 'Configure automatic Telegram and Zalo alerts and verify bot delivery.',
      'settings.partner_cta': 'Partner API & Webhooks',
      'settings.master.title': 'Automatic push alerts',
      'settings.master.desc': 'Notify immediately whenever a tracked parcel changes status.',
      'settings.channel_toggle': 'Enable channel',
      'settings.tg.title': 'Telegram Channel',
      'settings.tg.desc': 'Receive instant automated updates from the official Telegram bot.',
      'settings.tg.placeholder': 'e.g. 987654321',
      'settings.zalo.title': 'Zalo Channel',
      'settings.zalo.desc': 'Receive shipment updates directly through the Zalo Bot.',
      'settings.zalo.placeholder': 'Paste your Zalo Chat ID',
      'settings.zalo.help': 'Paste the chat_id obtained when messaging or linking via the Zalo Bot.',
      "settings.stages.title": "Shipment stage notifications",
      "settings.stages.help": "Receive updates in the stages you select, including multiple updates in the same stage. Clear all to turn off shipment updates.",
      "settings.stages.all_help": "Select all 6 to receive every update, including other exceptions. Applies to both Telegram and Zalo when automatic notifications are enabled.",
      "settings.stages.preparing": "Accepted / Preparing",
      "settings.stages.picked_up": "Picked up / Received",
      "settings.stages.in_transit": "In transit",
      "settings.stages.at_delivery_station": "At delivery station",
      "settings.stages.out_for_delivery": "Out for delivery",
      "settings.stages.delivered": "Delivered",
      'settings.save': 'Save notification settings',
      'settings.test_tg.title': 'Test Telegram bot',
      'settings.test_tg.desc': 'Send a sample message to your saved Telegram Chat ID to verify delivery.',
      'settings.test_tg.btn': 'Send Telegram test',
      'settings.test_zalo.title': 'Test Zalo bot',
      'settings.test_zalo.desc': 'Send a sample message to your saved Zalo Chat ID to verify delivery.',
      'settings.test_zalo.btn': 'Send Zalo test',

      'support.title': 'Support Order Tracker',
      'support.subtitle': 'Your contribution keeps the server and notification bots running reliably 24/7.',
      'support.gateway_pending': 'PayOS checkout is currently under maintenance or not configured. Please try again later.',
      'support.amount_label': 'Contribution amount (VND)',
      'support.amount_placeholder': 'e.g. 50000',
      'support.name_label': 'Your name',
      'support.name_placeholder': 'Your name or handle',
      'support.email_label': 'Email address',
      'support.message_label': 'Message (optional)',
      'support.message_placeholder': 'Leave a note for the maintainers…',
      'support.method_label': 'Payment method',
      'support.method_value': 'VietQR Bank Transfer · PayOS',
      'support.submit': 'Continue to PayOS checkout',

      'login.title': 'Sign in',
      'login.subtitle': 'Access your dashboard to check and manage tracked parcels.',
      'login.username': 'Username',
      'login.username.placeholder': 'Enter your username',
      'login.password': 'Password',
      'login.password.placeholder': 'Enter your password',
      'login.submit': 'Sign in',
      'login.no_account': 'Need an account?',
      'login.register_link': 'Create free account',

      'register.title': 'Create account',
      'register.subtitle': 'Track unlimited parcels with instant Telegram and Zalo notifications.',
      'register.username': 'Username',
      'register.username.placeholder': '2 to 20 characters',
      'register.username.hint': 'Choose a 2–20 character username for web sign-in.',
      'register.password': 'Password',
      'register.password.placeholder': 'Choose a strong password',
      'register.confirm': 'Confirm password',
      'register.confirm.placeholder': 'Re-enter your password',
      'register.submit': 'Create account',
      'register.has_account': 'Already registered?',
      'register.login_link': 'Sign in',

      'link_tg.title': 'Link Telegram to web account',
      'link_tg.subtitle': 'Set a username and password to sync your Telegram-tracked parcels with the web dashboard.',
      'link_tg.username': 'New username',
      'link_tg.password': 'Password (at least 6 characters)',
      'link_tg.password.placeholder': 'At least 6 characters',
      'link_tg.submit': 'Complete Telegram link',

      'link_zalo.title': 'Link Zalo to web account',
      'link_zalo.subtitle': 'Attach Zalo to an existing web account or create a new one for two-way sync.',
      'link_zalo.mode_label': 'Linking method',
      'link_zalo.mode.existing': 'Sign in to existing account',
      'link_zalo.mode.new': 'Create new account',
      'link_zalo.existing_user': 'Existing username',
      'link_zalo.existing_pwd': 'Existing password',
      'link_zalo.existing_hint': 'Any parcels previously tracked via Zalo will merge into this account.',
      'link_zalo.submit': 'Confirm Zalo link',

      'dev.title': 'Partner API & Webhooks',
      'dev.subtitle': 'Manage REST API credentials and receive real-time push webhooks whenever shipments update.',
      'dev.open_docs': 'Read integration docs',
      'dev.key_once_title': 'Copy your new API key now — the full secret is shown only once:',
      'dev.key_section.title': 'Partner API Key',
      'dev.key_section.desc': 'Send via Authorization: Bearer <API_KEY> or X-API-Key when calling /api/v1/* endpoints.',
      'dev.status.active': 'Active',
      'dev.status.none': 'Not created',
      'dev.key_current_label': 'Current key',
      'dev.key_empty_hint': 'No active key yet. Generate a key to authenticate third-party requests.',
      'dev.btn.create_key': 'Generate API key',
      'dev.btn.rotate_key': 'Rotate API key',
      'dev.btn.revoke_key': 'Revoke key',
      'dev.base_url_label': 'API Base URL',
      'dev.wh.title': 'Outbound Webhook Configuration',
      'dev.wh.desc': 'Automatically delivers HMAC-SHA256 signed HTTP POST payloads whenever a parcel gains new checkpoints.',
      'dev.wh.enable_label': 'Enable webhook',
      'dev.wh.url_label': 'Destination URL (HTTPS)',
      'dev.wh.url_help': 'Requires HTTPS in production and a 2xx response within 8 seconds.',
      'dev.wh.events_label': 'Subscribed events',
      'dev.ev.created': 'Triggered when a new parcel is registered via Web, Bot, or API',
      'dev.ev.updated': 'Triggered when new carrier transit checkpoints are detected',
      'dev.ev.completed': 'Triggered when a parcel is delivered or reaches terminal status',
      'dev.wh.save_btn': 'Save webhook settings',
      'dev.wh.secret_label': 'Webhook Signing Secret (HMAC-SHA256)',
      'dev.wh.rotate_secret': 'Rotate secret',
      'dev.wh.secret_empty': 'Your signing secret is generated automatically when you save a webhook or create an API key.',
      'dev.wh.last_delivery': 'Last delivery:',
      'dev.wh.no_delivery': 'No webhook deliveries recorded yet.',
      'dev.wh.test_btn': 'Send test webhook',

      'docs.title': 'Partner API & Webhook Documentation',
      'docs.subtitle': 'Reference guide for integrating REST API v1 and verifying real-time shipment webhooks.',
      'docs.cta_keys': 'Manage API Key & Webhooks',
      'docs.cta_get_key': 'Sign in to get API Key',
      'docs.toc.overview': '1. Overview & Auth',
      'docs.toc.carriers': '2. Supported Carriers',
      'docs.toc.trackings': '3. Shipment Endpoints',
      'docs.toc.webhooks': '4. Outbound Webhooks',
      'docs.toc.signature': '5. Signature Verification',
      'docs.toc.errors': '6. Error Reference',
      'docs.s1.title': '1. Overview & Authentication',
      'docs.s2.title': '2. Supported Carriers',
      'docs.s3.title': '3. Managing & Syncing Shipments',
      'docs.s3.create': 'Register a new shipment',
      'docs.s3.other': 'Query, refresh & delete endpoints',
      'docs.s4.title': '4. Real-Time Outbound Webhooks',
      'docs.s5.title': '5. Verifying HMAC-SHA256 Signatures',
      'docs.s6.title': '6. HTTP Status & Error Codes',
      'docs.tbl.carrier_name': 'Carrier name',
      'docs.tbl.example': 'Example format',
      'docs.tbl.field': 'Field',
      'docs.tbl.type': 'Type',
      'docs.tbl.desc': 'Description',
      'docs.tbl.trigger': 'When triggered',
      'docs.tbl.meaning': 'Meaning',

      'admin.title': 'System Configuration',
      'admin.subtitle': 'Manage parcel polling cadence, PayOS gateway credentials, and Telegram/Zalo bot connections.',
      'admin.group.tracking.title': 'Order Tracking',
      'admin.group.tracking.desc': 'Control parcel registration and background sync intervals.',
      'admin.group.payos.title': 'PayOS',
      'admin.group.payos.desc': 'Manage checkout gateway credentials and return URLs.',
      'admin.group.telegram.title': 'Telegram',
      'admin.group.telegram.desc': 'Connect the Telegram bot for commands and push alerts.',
      'admin.group.zalo.title': 'Zalo',
      'admin.group.zalo.desc': 'Connect the Zalo polling bot.',
      'admin.field.TRACKING_ENABLED': 'Enable order tracking',
      'admin.field.SCHEDULER_ENABLED': 'Enable automatic polling',
      'admin.field.POLL_INTERVAL_SECONDS': 'Polling interval (seconds)',
      'admin.field.MAX_EVENTS_PER_TRACKING': 'Max checkpoints per parcel',
      'admin.field.PAYOS_ENABLED': 'Enable PayOS gateway',
      'admin.field.PAYOS_CLIENT_ID': 'Client ID',
      'admin.field.PAYOS_API_KEY': 'API key',
      'admin.field.PAYOS_CHECKSUM_KEY': 'Checksum key',
      'admin.field.PAYOS_RETURN_URL': 'Success return URL',
      'admin.field.PAYOS_CANCEL_URL': 'Cancel return URL',
      'admin.field.PAYOS_DONATION_AMOUNT': 'Default donation amount (VND)',
      'admin.field.DONATE_NOTIFY_ALL': 'Broadcast donations to all users',
      'admin.field.TELEGRAM_ENABLED': 'Enable Telegram bot',
      'admin.field.TELEGRAM_BOT_TOKEN': 'Bot token',
      'admin.field.TELEGRAM_BOT_USERNAME': 'Bot username',
      'admin.field.ZALO_ENABLED': 'Enable Zalo bot',
      'admin.field.ZALO_BOT_TOKEN': 'Bot token',
      'admin.field.ZALO_BOT_UID': 'Bot UID',
      'admin.secret.configured': 'Configured',
      'admin.secret.unconfigured': 'Not configured',
      'admin.secret.placeholder': 'Enter new secret to replace',
      'admin.secret.hint': 'Leave blank to preserve the currently stored secret.',
      'admin.save.clean': 'No unsaved changes',
      'admin.save.desc': 'Writes all settings to .env / config.conf and applies service changes.',
      'admin.save.btn': 'Save & apply',
      'admin.verify.title': 'Verify Admin Identity',
      'admin.verify.subtitle': 'This one-time link from the Telegram Bot confirms administrator privileges for your signed-in web account.',
      'admin.verify.btn': 'Confirm & open admin panel',
      'admin.saved.title': 'Configuration Saved',
      'admin.saved.auto': 'The service is restarting automatically to apply new settings. Wait a few seconds before reopening Admin.',
      'admin.saved.manual': 'Configuration files have been updated. Restart the application to apply all changes.',
      'admin.saved.back_admin': 'Back to Admin',
      'admin.saved.back_dash': 'Go to Shipments'
    }
  };

  /* Server Flash & Validation Error Bilingual Map */
  const FLASH_EN = {
    'Vui lòng đăng nhập để tiếp tục.': 'Please sign in to continue.',
    'Thêm vận đơn thành công!': 'Parcel added successfully!',
    'Không thể thêm vận đơn mới.': 'Unable to add parcel.',
    'Cập nhật trạng thái vận đơn thành công!': 'Shipment status refreshed!',
    'Không thể cập nhật trạng thái vận đơn.': 'Unable to refresh shipment status.',
    'Vận đơn đã bị xóa.': 'Shipment removed.',
    'Tài khoản đã được tạo thành công! Bạn có thể đăng nhập ngay bây giờ.': 'Account created! You can sign in now.',
    'Đăng nhập không thành công. Vui lòng kiểm tra lại tên đăng nhập và mật khẩu.': 'Sign-in failed. Please check your username and password.',
    'Đã lưu cài đặt thông báo!': 'Notification settings saved!',
    'Đã gửi tin nhắn thử tới Telegram!': 'Test message sent to Telegram!',
    'Đã gửi tin nhắn thử tới Zalo!': 'Test message sent to Zalo!',
    'Bot Telegram chưa được cấu hình trên hệ thống.': 'Telegram bot is not configured on this server.',
    'Bot Zalo chưa được cấu hình trên hệ thống.': 'Zalo bot is not configured on this server.',
    'Vui lòng lưu Telegram Chat ID trước khi gửi thử.': 'Please save your Telegram Chat ID before sending a test.',
    'Vui lòng lưu Zalo Chat ID trước khi gửi thử.': 'Please save your Zalo Chat ID before sending a test.',
    'Cảm ơn bạn đã ủng hộ!': 'Thank you for your support!',
    'Giao dịch đã được hủy.': 'Payment was cancelled.',
    'Đã khởi tạo API Key mới thành công!': 'New Partner API key generated!',
    'Đã thu hồi API Key hiện tại.': 'API key revoked.',
    'Đã lưu cấu hình Webhook đối tác!': 'Partner webhook configuration saved!',
    'Đã làm mới khóa ký Webhook (Signing Secret)!': 'Webhook signing secret rotated!',
    'Vui lòng lưu URL nhận Webhook trước khi gửi sự kiện thử nghiệm.': 'Save a webhook URL before sending a test event.',
    'Phiên làm việc đã hết hạn. Vui lòng thử lại.': 'Session expired. Please try again.',
    'Mã vận đơn này đã có trong danh sách theo dõi của bạn.': 'This tracking number is already in your shipment list.',
    'Đã cập nhật thông tin vận đơn!': 'Shipment details updated!',
    'Đã tạo liên kết chia sẻ hành trình công khai!': 'Public tracking link created!',
    'Đã thu hồi liên kết chia sẻ công khai.': 'Public tracking link revoked.'
  };

  const ERR_MAP = {
    'This field is required.': { vi: 'Vui lòng nhập thông tin này.', en: 'This field is required.' },
    'Field must be between 2 and 20 characters long.': { vi: 'Độ dài phải từ 2 đến 20 ký tự.', en: 'Must be between 2 and 20 characters.' },
    'Field must be at least 6 characters long.': { vi: 'Mật khẩu phải có ít nhất 6 ký tự.', en: 'Password must be at least 6 characters.' },
    'Field must be equal to password.': { vi: 'Mật khẩu xác nhận không khớp.', en: 'Passwords do not match.' },
    'Field must be equal to new_password.': { vi: 'Mật khẩu xác nhận không khớp.', en: 'Passwords do not match.' },
    'Invalid email address.': { vi: 'Địa chỉ email không hợp lệ.', en: 'Enter a valid email address.' },
    'Not a valid integer value.': { vi: 'Vui lòng nhập số tiền hợp lệ.', en: 'Enter a valid numeric amount.' },
    'Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.': { vi: 'Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.', en: 'Username is already taken. Please choose another.' },
    'Vui lòng nhập tối thiểu 1,000 VND': { vi: 'Vui lòng nhập tối thiểu 1.000 VND.', en: 'Minimum amount is 1,000 VND.' },
    'Sai tên đăng nhập hoặc mật khẩu.': { vi: 'Sai tên đăng nhập hoặc mật khẩu.', en: 'Incorrect username or password.' }
  };

  let currentLang = localStorage.getItem('v2_lang') || localStorage.getItem('language') || 'vi';
  if (!DICT[currentLang]) currentLang = 'vi';

  function getEffectiveTheme() {
    const attr = document.documentElement.getAttribute('data-theme');
    if (attr === 'dark' || attr === 'light') return attr;
    const saved = localStorage.getItem('v2_theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function syncThemeButton() {
    const btn = document.getElementById('v2-theme-toggle');
    if (!btn) return;
    const isDark = getEffectiveTheme() === 'dark';
    const label = DICT[currentLang][isDark ? 'theme.to_light' : 'theme.to_dark'];
    btn.setAttribute('aria-pressed', String(isDark));
    btn.setAttribute('aria-label', label);
    btn.setAttribute('title', label);
  }

  function applyTheme(theme, persist = true) {
    const next = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    const metaTc = document.getElementById('v2-meta-theme-color');
    if (metaTc) {
      metaTc.setAttribute('content', next === 'dark' ? '#0b0f17' : '#4f46e5');
    }
    if (persist) {
      localStorage.setItem('v2_theme', next);
    }
    syncThemeButton();
    window.dispatchEvent(new CustomEvent('v2:themechange', { detail: { theme: next } }));
  }

  window.changeV2Theme = applyTheme;

  function applyLang(lang) {
    if (!DICT[lang]) return;
    currentLang = lang;
    localStorage.setItem('v2_lang', lang);
    localStorage.setItem('language', lang);
    document.documentElement.lang = lang;

    document.querySelectorAll('[data-v2-i18n]').forEach((el) => {
      const key = el.getAttribute('data-v2-i18n');
      const val = DICT[lang][key];
      if (!val) return;
      const attr = el.getAttribute('data-v2-i18n-attr');
      if (attr) {
        el.setAttribute(attr, val);
      } else {
        el.textContent = val;
      }
    });

    document.querySelectorAll('[data-lang-block]').forEach((el) => {
      el.hidden = el.getAttribute('data-lang-block') !== lang;
    });

    document.querySelectorAll('[data-v2-err]').forEach((el) => {
      const raw = el.getAttribute('data-v2-err') || '';
      if (ERR_MAP[raw]) {
        el.textContent = ERR_MAP[raw][lang];
      }
    });

    document.querySelectorAll('[data-v2-flash]').forEach((el) => {
      const orig = el.getAttribute('data-v2-flash') || '';
      if (lang === 'en' && FLASH_EN[orig]) {
        el.textContent = FLASH_EN[orig];
      } else {
        el.textContent = orig;
      }
    });

    document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
      const isShown = btn.getAttribute('aria-pressed') === 'true';
      btn.setAttribute(
        'aria-label',
        lang === 'en' ? (isShown ? 'Hide secret' : 'Show secret') : (isShown ? 'Ẩn mật khẩu' : 'Hiện mật khẩu')
      );
    });

    document.querySelectorAll('[data-v2-lang]').forEach((btn) => {
      btn.setAttribute('aria-pressed', String(btn.getAttribute('data-v2-lang') === lang));
    });

    syncThemeButton();
    window.dispatchEvent(new CustomEvent('v2:langchange', { detail: { lang } }));
  }

  window.changeV2Language = applyLang;

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(getEffectiveTheme(), false);
    applyLang(currentLang);

    const themeToggle = document.getElementById('v2-theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => {
        applyTheme(getEffectiveTheme() === 'dark' ? 'light' : 'dark', true);
      });
    }

    if (window.matchMedia) {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      const handleSystemChange = (e) => {
        const saved = localStorage.getItem('v2_theme');
        if (saved !== 'dark' && saved !== 'light') {
          applyTheme(e.matches ? 'dark' : 'light', false);
        }
      };
      if (typeof mq.addEventListener === 'function') {
        mq.addEventListener('change', handleSystemChange);
      }
    }

    document.querySelectorAll('[data-v2-lang]').forEach((btn) => {
      btn.addEventListener('click', () => applyLang(btn.getAttribute('data-v2-lang')));
    });

    const navToggle = document.getElementById('v2-nav-toggle');
    const navCluster = document.getElementById('v2-nav-cluster');
    if (navToggle && navCluster) {
      navToggle.addEventListener('click', () => {
        const expanded = navToggle.getAttribute('aria-expanded') === 'true';
        navToggle.setAttribute('aria-expanded', String(!expanded));
        navCluster.classList.toggle('is-open', !expanded);
      });
    }

    // Accessible Navigation Dropdowns ("Cấu hình")
    const dropdowns = Array.from(document.querySelectorAll('[data-v2-dropdown]'));
    const closeAllDropdowns = (except = null) => {
      dropdowns.forEach((dd) => {
        if (dd === except) return;
        const btn = dd.querySelector('button[aria-controls]');
        const menu = dd.querySelector('.v2-dropdown-menu');
        if (btn) btn.setAttribute('aria-expanded', 'false');
        if (menu) menu.hidden = true;
      });
    };

    dropdowns.forEach((dd) => {
      const btn = dd.querySelector('button[aria-controls]');
      const menu = dd.querySelector('.v2-dropdown-menu');
      if (!btn || !menu) return;

      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = btn.getAttribute('aria-expanded') === 'true';
        closeAllDropdowns(dd);
        btn.setAttribute('aria-expanded', String(!isOpen));
        menu.hidden = isOpen;
      });

      dd.addEventListener('keydown', (e) => {
        const links = Array.from(menu.querySelectorAll('a'));
        if (e.key === 'Escape') {
          btn.setAttribute('aria-expanded', 'false');
          menu.hidden = true;
          btn.focus();
        } else if (e.key === 'ArrowDown') {
          e.preventDefault();
          if (menu.hidden) {
            closeAllDropdowns(dd);
            btn.setAttribute('aria-expanded', 'true');
            menu.hidden = false;
            if (links[0]) links[0].focus();
          } else {
            const idx = links.indexOf(document.activeElement);
            const next = links[(idx + 1) % links.length];
            if (next) next.focus();
          }
        } else if (e.key === 'ArrowUp' && !menu.hidden) {
          e.preventDefault();
          const idx = links.indexOf(document.activeElement);
          const prev = links[(idx - 1 + links.length) % links.length];
          if (prev) prev.focus();
        }
      });
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('[data-v2-dropdown]')) {
        closeAllDropdowns();
      }
    });

    document.querySelectorAll('.v2-toast').forEach((toast) => {
      const closeBtn = toast.querySelector('.v2-toast-close');
      const dismiss = () => toast.remove();
      if (closeBtn) closeBtn.addEventListener('click', dismiss);
      if (toast.dataset.tone !== 'danger') {
        setTimeout(() => {
          if (toast.isConnected) dismiss();
        }, 5500);
      }
    });

    document.querySelectorAll('[data-copy-text]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const text = btn.getAttribute('data-copy-text') || '';
        if (!text) return;
        const labelEl = btn.querySelector('[data-copy-label]');
        try {
          await navigator.clipboard.writeText(text);
          if (labelEl) {
            const prev = labelEl.textContent;
            labelEl.textContent = currentLang === 'en' ? 'Copied' : 'Đã chép';
            setTimeout(() => { labelEl.textContent = prev; }, 1800);
          }
        } catch (_) {}
      });
    });

    document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-toggle-password');
        const input = document.getElementById(targetId);
        if (!input) return;
        const isPwd = input.type === 'password';
        input.type = isPwd ? 'text' : 'password';
        btn.setAttribute('aria-pressed', String(isPwd));
        btn.setAttribute(
          'aria-label',
          currentLang === 'en' ? (isPwd ? 'Hide secret' : 'Show secret') : (isPwd ? 'Ẩn mật khẩu' : 'Hiện mật khẩu')
        );
      });
    });

    document.querySelectorAll('form[data-v2-busy]').forEach((form) => {
      form.addEventListener('submit', () => {
        const btn = form.querySelector('button[type="submit"]');
        if (btn && !btn.disabled) {
          const busyText = form.getAttribute('data-v2-busy');
          btn.disabled = true;
          btn.setAttribute('aria-busy', 'true');
          if (busyText) {
            const textSpan = btn.querySelector('[data-btn-label]');
            if (textSpan) textSpan.textContent = busyText;
          }
        }
      });
    });
  });
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
    });
  }
})();
