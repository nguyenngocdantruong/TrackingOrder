# Order Tracker — Windows Desktop (Tauri v2)

Ứng dụng Windows gọn nhẹ cho **Order Tracking Hub** theo kiến trúc Hybrid (Tauri v2 + Rust System Tray Worker):

- **Đăng nhập đồng bộ tự động:** Đăng nhập trên cửa sổ ứng dụng tự động cấp token riêng (`oth_desk_...`) cho tiến trình chạy ngầm, hỗ trợ tối đa 5 thiết bị và tự thu hồi khi đăng xuất.
- **System Tray & Chạy ngầm:** Đóng cửa sổ `X` tự thu xuống khay hệ thống, cập nhật tooltip trực tiếp theo **địa chỉ mặc định** và tổng tiền COD cần chuẩn bị.
- **Thông báo gốc Windows (Native Toast):** Đồng bộ 6 giai đoạn thông báo từ tài khoản web, khử trùng lặp theo `eventHash`, nhắc kèm số tiền COD và địa chỉ nhận.
- **Khởi động cùng Windows (`--minimized`):** Bật/tắt ngay ở menu chuột phải System Tray hoặc trang **Cấu hình > Thông báo** bên trong ứng dụng.
- **Thêm đơn nhanh (`Ctrl + Shift + T`):** Mở hộp nhập nổi từ bất kỳ đâu, tự nhận mã vận đơn (`SPXVN...`, `LEX...`, J&T) đang có trong Clipboard và gắn sẵn địa chỉ mặc định.

## Đóng gói tự động qua GitHub Actions (Khuyên dùng)

1. Mở tab **Actions** trên GitHub repository → chọn workflow **Build Windows Desktop App**.
2. Nhấn **Run workflow** (chọn `publish_release = true` nếu muốn xuất thẳng lên GitHub Releases để trang `/download` trên web tải trực tiếp), **hoặc** đẩy tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. Sau khi workflow chạy xong, hai bộ cài `OrderTracker_1.0.0_x64-setup.exe` (NSIS, không cần quyền Admin) và `.msi` sẽ tự động xuất hiện trên GitHub Releases và trang `/download` của web.

## Chạy và build tại máy local (nếu cài Rust)

Yêu cầu: Node.js >= 20, [Rustup](https://rustup.rs/) (MSVC toolchain) và Windows 10/11 WebView2.

```bash
cd desktop
npm install
npm run dev     # Chạy chế độ phát triển
npm run build   # Xuất file .exe và .msi tại desktop/src-tauri/target/release/bundle/
```
