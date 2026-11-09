# Phương án dùng thử Bàn tin 0.4

**Trạng thái: chuẩn bị để xem xét, chưa triển khai.** Bản đang phát triển nằm ở nhánh `codex/newsroom-multichannel`; `main` chưa chứa bản đa kênh. Phương án này không phải chấp thuận gộp nhánh, mở kho vận hành hoặc tự đăng bài.

## Bằng chứng và điều kiện còn mở

- Mẫu đầu ra policy v6 đã được người dùng xem và xác nhận phù hợp. Người dùng cũng xác nhận một đoạn Facebook giả được dán đúng từ Edge. Hồi quy gần nhất trên mã ứng dụng sau sửa khởi động đạt 263/263 Python, 90/90 JavaScript; xem [kiểm thử](KIEM-THU.md).
- Việc thử cảnh báo rời trang/tải lại khi có thay đổi chưa lưu tiếp tục **để sau** theo lựa chọn của người dùng. API, xử lý xung đột, URL và policy vẫn còn giới hạn tại [ma trận bằng chứng](MA-TRAN-BANG-CHUNG-0.4.md); chưa kết luận hoàn tất toàn bộ checklist 0.4.
- Threads có bộ đếm ước lượng; X dùng dữ liệu emoji đã ghim. Người biên tập cần kiểm tra lại độ dài và nội dung trên nền tảng trước khi tự đăng. URL ghi nhận là do người dùng nhập và không chứng minh bài tồn tại.
- Người dùng đã xác nhận chưa có SQLite cũ để thử migration. Nếu thực tế xuất hiện dữ liệu cần giữ, dừng và lập phương án sao lưu, thử trên bản sao trước; không suy ra kho hiện tại trống chỉ từ xác nhận trước đây.

## Đề xuất: kho mới riêng để dùng thử

Chỉ thực hiện sau khi người dùng quyết định bắt đầu và sau khi kiểm tra trạng thái nghiệm thu còn mở. Đây là **kho dùng thử với tin thật**, khác với kho minh họa; nội dung và URL người dùng nhập sẽ được lưu thật trong thư mục được chọn.

1. Xác nhận nhánh và commit cần chạy, tình trạng làm việc sạch và mã đã đẩy lên Git. Nếu mã thay đổi sau lần hồi quy gần nhất, chạy lại kiểm thử trước khi bắt đầu. Không tự gộp vào `main`.
2. Chọn một thư mục mới, riêng, nằm ngoài OneDrive và ổ mạng; xác nhận đường dẫn chưa tồn tại trước khi dùng. Chẳng hạn, nếu thư mục ví dụ dưới đây chưa tồn tại, mở PowerShell trong thư mục chứa mã đã xác nhận:

   ```powershell
   python -m newsroom --data-dir "$env:USERPROFILE\AppData\Local\BanTinLocal-Pilot-04" --port 8879 --no-refresh
   ```

   Nếu thư mục đã tồn tại, **không dùng lại theo quán tính**: kiểm tra dữ liệu hoặc chọn tên mới. Nếu cổng bận, chọn cổng khác và kiểm tra địa chỉ hiển thị. `--no-refresh` tắt lịch tự đọc nguồn khi khởi động; chỉ chủ động đọc nguồn sau khi người dùng chọn. Không dùng `--demo` cùng `--data-dir`.
3. Giữ cửa sổ chạy mở và kiểm tra địa chỉ localhost cùng đường dẫn dữ liệu được ứng dụng hiển thị. Xác nhận đây là thư mục dùng thử trước khi nhập tin; không đưa ứng dụng ra LAN/Internet.
4. Với một nhóm tin thật do người dùng chọn, đọc nguồn, biên tập và kiểm chứng từng mục; tạo phiên bản kênh cần dùng, xem trước, duyệt và đối chiếu nội dung cùng nguồn. Có thể dừng ở bản nháp. Người dùng quyết định việc đăng, tự đăng thủ công và chỉ sau đó tự ghi nhận URL nếu muốn; ứng dụng không đăng hoặc xác minh bài trên mạng xã hội.
5. Dùng nút sao lưu trong ứng dụng và giữ bản sao ở vị trí khác; việc khôi phục thực hiện vào **thư mục mới**, theo [hướng dẫn](HUONG-DAN-SU-DUNG.md). Đối chiếu kết quả trước khi dùng bản khôi phục; không ghi đè kho đang chạy.

## Dừng hoặc chuyển sang vận hành

- Lưu hoặc sao chép nội dung đang soạn, rồi dừng đúng cửa sổ server bằng `Ctrl+C`. Giữ nguyên thư mục dữ liệu thử và bản sao lưu; không xóa hoặc đổi tên tự động.
- Nếu muốn dùng dữ liệu thử tiếp như kho vận hành hoặc thay thế kho mặc định, cần quyết định và phương án riêng sau khi xem kết quả thử; kiểm tra thư mục đích, bản sao lưu, khả năng khôi phục và sự tương thích schema trước khi làm.
- Nếu không tiếp tục, có thể giữ kho thử để đối chiếu. Chỉ xóa sau khi người dùng xác định rõ không còn cần dữ liệu trong kho đó.
