# Đối chiếu điều kiện nghiệm thu 0.4

Ngày rà soát: 03/11/2026. Đối chiếu mục 10 của [kế hoạch nâng cấp](KE-HOACH-NANG-CAP-BAN-TIN-DA-KENH.md) với mã và bằng chứng được ghi trong [nhật ký kiểm thử](KIEM-THU.md). Đây là trạng thái kiểm chứng, không phải chấp thuận triển khai. Các lệnh và kết quả chi tiết, dữ liệu sử dụng và giới hạn được ghi tại nhật ký đó.

| Điều kiện mục 10 | Bằng chứng hiện có | Phần còn thiếu để kết luận |
| --- | --- | --- |
| Ba bài nguồn, thứ tự và truy vết qua restart | `tests/test_bulletins.py`: `test_reorder_and_packet_preserve_snapshots_after_refresh_restart`, `test_three_channel_bulletin_survives_backup_restore_with_partial_publication`; thao tác bàn phím và tải lại trên kho demo. | Chưa hoàn tất toàn bộ QA Windows và kiểm thử restart server trong lượt thao tác bàn phím đó. |
| Biên tập thủ công hoặc gói tư liệu, không phát sinh model call | Ba pilot fixture trong `KIEM-THU.md`; `test_no_publish_or_ai_integration_endpoint` trong `tests/test_server.py`; gói tư liệu được tạo trong `bulletins.py`. | Ba lượt là dữ liệu giả; cần người dùng xem kết quả pilot và xác nhận quy trình phù hợp với thực tế. |
| Ba biến thể độc lập, có thể dùng một kênh | Test ba kênh qua backup/restore trong `tests/test_bulletins.py`; các lượt pilot Facebook, Threads và X trên kho demo. | Chưa kiểm chứng toàn bộ đường thao tác và chính sách của ba nền tảng trên tài khoản đích. |
| Đầu ra, bộ đếm, preview, copy, file và approval khớp; giữ nguồn | `test_approved_export_matches_preview_and_changes_invalidate`, `test_split_rechecks_numbering_and_keeps_sources_and_text`; ba tệp pilot được đối chiếu; đã thử copy và fallback clipboard ở phạm vi ghi trong `KIEM-THU.md`. | BASE-03 còn mở: Threads là ước lượng, X chưa xác minh đầy đủ emoji và URL thực tế; chưa kiểm tra mọi luồng copy/chia trên trình duyệt. |
| Hủy duyệt đúng phạm vi; bản ghi nhận bất biến; ghi nhận một phần | Các test `test_parent_edit_resets_checks_of_unlocked_variants_only`, `test_cancel_all_preserves_lock_and_history_and_can_record_again`, `test_policy_change_after_partial_recording_preserves_snapshot`; có smoke hiển thị 1/N và 0/N từ dữ liệu chuẩn bị sẵn. | Chưa kiểm tra trọn luồng đính chính, hủy và ghi lại qua giao diện; công cụ trình duyệt từng bị kẹt ở hộp xác nhận. |
| URL và số liệu riêng theo kênh/đoạn, không giữ URL bài khác | Test binding trong `tests/draft-state.test.js`, test handler trong `tests/correction-ui.test.js`, test vòng đời HTTP trong `tests/test_server.py`; đã thử một số bước bằng kho demo. | Còn QA chuyển kênh/đoạn, ghi nhận và nhập số liệu qua trình duyệt; chưa đối chiếu mọi dạng URL nền tảng hoặc số liệu tài khoản thật. |
| Legacy giữ nội dung/hash/export/history; migration và restore vượt test lỗi | Fixture schema 3 từ mã cũ và fixture schema 1/2 mô phỏng trong `tests/test_migrations_v4.py`; test lỗi backup/migration/restore, cấu trúc schema 4 và restore liên thông ba kênh. | Chưa thử migration, restore và đường lui trên bản sao dữ liệu vận hành được phép; fixture 1/2 không phải snapshot lịch sử. Chưa kiểm chứng mọi payload hoặc lỗi hệ thống tập tin. |
| Test đạt và có QA trình duyệt/clipboard | Lần hồi quy gần nhất ghi trong `KIEM-THU.md`: 161 Python và 20 JavaScript; đã có bằng chứng dán clipboard và fallback trên Edge với dữ liệu giả. | QA-02 chưa hoàn tất toàn bộ bàn phím, tab, trạng thái chưa lưu, restart và các luồng mới; công cụ hiện không truy cập được trình duyệt. Cần chạy lại hồi quy sau mọi thay đổi. |
| README, hướng dẫn, kiến trúc, kiểm thử cập nhật | `README.md`, `docs/HUONG-DAN-SU-DUNG.md`, `docs/KIEN-TRUC.md`, `docs/KIEM-THU.md` và `docs/API-BAN-TIN-DA-KENH.md` đã có nội dung cho 0.4. | Cần rà soát lại tính nhất quán theo trạng thái cuối trước phát hành, bao gồm policy và kết quả QA còn mở. |
| Người dùng xem pilot và quyết định triển khai | Ba lượt pilot fixture đã ghi thời gian và vấn đề trong `KIEM-THU.md`. | Chưa có quyết định triển khai lên kho vận hành. Không tự thực hiện migration trên kho đó. |

## Các việc tiếp theo có phụ thuộc bên ngoài

1. Khôi phục khả năng điều khiển trình duyệt Windows, rồi hoàn tất QA-02 trên kho giả, nhất là luồng ghi nhận, đính chính, số liệu và cảnh báo chưa lưu. Không thay bằng DOM giả.
2. Hoàn tất BASE-03 bằng bằng chứng phù hợp cho cách đếm và mẫu URL của các nền tảng; khi chưa chứng minh được thì giữ nhãn ước lượng và gate mở.
3. Nhận đường dẫn bản sao SQLite được phép sử dụng; thử migration/restore và đường lui trên bản sao riêng, không sửa kho vận hành.
4. Tổng hợp bằng chứng mới, đối chiếu lại toàn bộ mục 10 và để người dùng xem pilot trước quyết định triển khai.

Không suy ra bài đã đăng hoặc nguồn đã được xác minh từ URL, kiểm thử fixture hay bản duyệt nội bộ.
