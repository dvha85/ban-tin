# Đối chiếu điều kiện nghiệm thu 0.4

> Cập nhật 04/11/2026: Bằng chứng giao diện mới hơn các nhận xét ban đầu trong bảng: trên kho fixture, đã thử đính chính, hủy và ghi lại cùng URL cho X; ghi nhận URL giả trên Facebook và Threads, lưu và xem lại số liệu riêng của hai kênh. Sau tải lại, tổng số ba đoạn và URL cùng số liệu Threads vẫn hiển thị. Đây là smoke test; QA-02 và việc đối chiếu URL thực tế vẫn mở. Xem `KIEM-THU.md`.

> Bổ sung 04/11: Edge trên fixture tạo bản tin từ ba tin giả, kể cả hai tin ẩn khi lọc; đổi thứ tự bằng bàn phím và tải lại giữ thứ tự cùng URL từng mục. Chưa restart server trong cùng lượt UI; bằng chứng restart service là kiểm thử riêng.

> Bổ sung restart: từ kho fixture đó tạo backup qua UI, khôi phục sang thư mục riêng, dừng và chạy lại server của bản khôi phục. Edge mở bản tin #2 vẫn thấy đúng thứ tự Alpha → Charlie → Bravo và ba URL nguồn. Không suy rộng sang mất điện hay dữ liệu vận hành.

> QA-02 còn lỗi phục hồi phiên: dữ liệu nhập được giữ sau lỗi kết nối, nhưng lưu lại sau restart bị từ chối và yêu cầu tải lại; thao tác tải lại có thể mất nội dung chưa lưu. Cần xử lý và thử lại; chi tiết tại `KIEM-THU.md`.

Ngày rà soát: 03/11/2026. Đối chiếu mục 10 của [kế hoạch nâng cấp](KE-HOACH-NANG-CAP-BAN-TIN-DA-KENH.md) với mã và bằng chứng được ghi trong [nhật ký kiểm thử](KIEM-THU.md). Đây là trạng thái kiểm chứng, không phải chấp thuận triển khai. Các lệnh và kết quả chi tiết, dữ liệu sử dụng và giới hạn được ghi tại nhật ký đó.

| Điều kiện mục 10 | Bằng chứng hiện có | Phần còn thiếu để kết luận |
| --- | --- | --- |
| Ba bài nguồn, thứ tự và truy vết qua restart | `tests/test_bulletins.py`: `test_reorder_and_packet_preserve_snapshots_after_refresh_restart`, `test_three_channel_bulletin_survives_backup_restore_with_partial_publication`; Edge tạo, đổi thứ tự và tải lại ba tin giả; backup, khôi phục và restart server bản sao rồi mở lại đúng thứ tự và nguồn. | Điều kiện này đạt trong phạm vi fixture; QA Windows tổng thể vẫn mở. |
| Biên tập thủ công hoặc gói tư liệu, không phát sinh model call | Ba pilot fixture trong `KIEM-THU.md`; `test_no_publish_or_ai_integration_endpoint` trong `tests/test_server.py`; gói tư liệu được tạo trong `bulletins.py`. | Ba lượt là dữ liệu giả; cần người dùng xem kết quả pilot và xác nhận quy trình phù hợp với thực tế. |
| Ba biến thể độc lập, có thể dùng một kênh | Test ba kênh qua backup/restore trong `tests/test_bulletins.py`; các lượt pilot Facebook, Threads và X trên kho demo. | Chưa kiểm chứng toàn bộ đường thao tác và chính sách của ba nền tảng trên tài khoản đích. |
| Đầu ra, bộ đếm, preview, copy, file và approval khớp; giữ nguồn | `test_approved_export_matches_preview_and_changes_invalidate`, `test_split_rechecks_numbering_and_keeps_sources_and_text`; ba tệp pilot được đối chiếu; đã thử copy và fallback clipboard ở phạm vi ghi trong `KIEM-THU.md`. | BASE-03 còn mở: Threads là ước lượng, X chưa xác minh đầy đủ emoji và URL thực tế; chưa kiểm tra mọi luồng copy/chia trên trình duyệt. |
| Hủy duyệt đúng phạm vi; bản ghi nhận bất biến; ghi nhận một phần | Các test `test_parent_edit_resets_checks_of_unlocked_variants_only`, `test_cancel_all_preserves_lock_and_history_and_can_record_again`, `test_policy_change_after_partial_recording_preserves_snapshot`; có smoke hiển thị 1/N và 0/N từ dữ liệu chuẩn bị sẵn. | Chưa kiểm tra trọn luồng đính chính, hủy và ghi lại qua giao diện; công cụ trình duyệt từng bị kẹt ở hộp xác nhận. |
| URL và số liệu riêng theo kênh/đoạn, không giữ URL bài khác | Test binding trong `tests/draft-state.test.js`, test handler trong `tests/correction-ui.test.js`, test vòng đời HTTP trong `tests/test_server.py`; trên kho fixture, URL chưa lưu ở đoạn hai được giữ và chặn thao tác nhập số liệu đoạn một. | Còn QA chuyển kênh/đoạn, ghi nhận và lưu số liệu qua trình duyệt; chưa đối chiếu mọi dạng URL nền tảng hoặc số liệu tài khoản thật. |
| Legacy giữ nội dung/hash/export/history; migration và restore vượt test lỗi | Fixture schema 3 từ mã cũ và fixture schema 1/2 mô phỏng trong `tests/test_migrations_v4.py`; test lỗi backup/migration/restore, cấu trúc schema 4 và restore liên thông ba kênh. | Không áp dụng thử trên bản sao SQLite cũ trong đợt này vì người dùng xác nhận chưa có dữ liệu cũ; fixture 1/2 không phải snapshot lịch sử. Chưa kiểm chứng mọi payload hoặc lỗi hệ thống tập tin. |
| Test đạt và có QA trình duyệt/clipboard | Lần hồi quy gần nhất ghi trong `KIEM-THU.md`: 163 Python và 20 JavaScript; đã có bằng chứng dán clipboard và fallback trên Edge với dữ liệu giả. | QA-02 chưa hoàn tất toàn bộ bàn phím, tab, trạng thái chưa lưu, restart và các luồng mới; công cụ từng bị gián đoạn khi xử lý hộp thoại. Cần chạy lại hồi quy sau mỗi thay đổi chức năng. |
| README, hướng dẫn, kiến trúc, kiểm thử cập nhật | `README.md`, `docs/HUONG-DAN-SU-DUNG.md`, `docs/KIEN-TRUC.md`, `docs/KIEM-THU.md` và `docs/API-BAN-TIN-DA-KENH.md` đã có nội dung cho 0.4. | Cần rà soát lại tính nhất quán theo trạng thái cuối trước phát hành, bao gồm policy và kết quả QA còn mở. |
| Người dùng xem pilot và quyết định triển khai | Ba lượt pilot fixture đã ghi thời gian và vấn đề trong `KIEM-THU.md`. | Chưa có quyết định triển khai lên kho vận hành. Không tự thực hiện migration trên kho đó. |

## Các việc tiếp theo có phụ thuộc bên ngoài

1. Hoàn tất QA-02 trên kho giả, nhất là luồng ghi nhận, đính chính, số liệu và cảnh báo chưa lưu; xử lý gián đoạn điều khiển hộp thoại khi thử. Không thay bằng DOM giả.
2. Hoàn tất BASE-03 bằng bằng chứng phù hợp cho cách đếm và mẫu URL của các nền tảng; khi chưa chứng minh được thì giữ nhãn ước lượng và gate mở.
3. Không áp dụng thử migration/restore trên bản sao SQLite cũ trong đợt này: người dùng xác nhận chưa có dữ liệu cũ. Các kiểm thử migration/restore bằng fixture vẫn được giữ; không coi đó là thử dữ liệu vận hành.
4. Tổng hợp bằng chứng mới, đối chiếu lại toàn bộ mục 10 và để người dùng xem pilot trước quyết định triển khai.

Không suy ra bài đã đăng hoặc nguồn đã được xác minh từ URL, kiểm thử fixture hay bản duyệt nội bộ.

## Cập nhật ngày 04/11/2026

- Hồi quy trước thay đổi: 163/163 Python và 20/20 JavaScript đạt. Các test restore sử dụng kho tạm/fixture.
- Edge mở kho fixture riêng có hai mục và phiên bản X hai đoạn đã ghi nhận giả một đoạn. Giao diện hiển thị trạng thái 1/2, nguồn của từng đoạn, liên kết giả, nút nhập số liệu và đính chính. Fixture được chuẩn bị bằng service, nên đây không phải kiểm thử toàn bộ luồng từ đầu.
- Khi nhập tám số liệu giả, công cụ điều khiển bị kẹt ở chuỗi hộp thoại; chưa xác nhận dữ liệu đã được lưu, chưa kiểm tra đính chính thành công hay luồng từ đầu đến cuối. Đây là giới hạn công cụ, chưa đủ bằng chứng kết luận ứng dụng lỗi hoặc quyết định thay hộp thoại. QA-02 tiếp tục mở.
- Sau lần thử xác nhận đoạn hai, thẻ mới trên cùng server fixture hiển thị trạng thái 2/2 và hai URL giả đúng từng đoạn. Đoạn một đã được chuẩn bị bằng service; không xác định được thao tác xác nhận nào hoàn tất đoạn hai. Chưa kiểm tra restart server, nhập số liệu hoặc đính chính thành công.
- Đối chiếu ngày 04/11: [Meta](https://about.fb.com/news/2023/07/introducing-threads-new-app-text-sharing/) nêu bài Threads thông thường tối đa 500 ký tự; [Meta](https://about.fb.com/news/2025/09/attach-text-threads-posts-share-longer-perspectives/) cũng mô tả tệp văn bản đính kèm riêng. [X](https://help.x.com/en/using-x/types-of-posts) nêu giới hạn thông thường 280 ký tự và các gói có bài dài; [X](https://help.x.com/en/using-twitter/how-to-tweet-a-link.html) nêu URL được tính 23 ký tự. Các nguồn này chưa xác minh đầy đủ phép đếm Unicode, emoji mới hay mọi alias URL. BASE-03 vẫn mở và cần kiểm tra bản thực tế trước khi đăng.
- Theo xác nhận của người dùng, thử trên bản sao SQLite cũ không áp dụng vì chưa có dữ liệu cũ. Nếu về sau xuất hiện dữ liệu cần nâng cấp, phải lập lại phương án thử trên bản sao trước khi xử lý dữ liệu đó.
