# Đối chiếu điều kiện nghiệm thu 0.4

> QA-01 / QA-03 ngày 05/11: hồi quy trên commit `6df28d1` đạt 207/207 Python và 52/52 JavaScript; điều kiện legacy/migration được đánh dấu đạt trong phạm vi fixture, theo lựa chọn bỏ qua bản sao SQLite cũ vì chưa có dữ liệu cũ. Không coi đây là nghiệm thu kho vận hành; xem `KIEM-THU.md`.

> FMT-02 / QA-02 ngày 05/11: thử hai thẻ trên kho giả, thẻ đang soạn hiện cảnh báo xem trước khi thẻ kia đã lưu tiêu đề bản tin, giữ nội dung chưa lưu và từ chối lưu phiên bản cũ. Đây là một tình huống Facebook nháp; xem `KIEM-THU.md`, QA-02 vẫn mở.

> APR-03 / QA-02 ngày 05/11: với một bản X hai đoạn trên kho giả, đã thử tệp UTF-8 qua trình duyệt, chặn tải khi đang sửa và khi bản duyệt bị hủy; sau đó thử riêng hai thẻ, duyệt lại ở thẻ thứ hai khiến thẻ cũ từ chối tải và sao chép đoạn cũ. Tệp ở thẻ mới khớp nội dung và nguồn hiển thị. Chưa kiểm tra mọi trình duyệt, kênh hoặc thay đổi sau phản hồi export; xem `KIEM-THU.md`.

> BASE-03 ngày 05/11: các ví dụ đếm trong tài liệu X và 15 trường hợp URL Unicode của corpus đã ghim khớp bộ đếm cục bộ. Bộ sưu tập Threads API chính thức đọc được nhưng phần đã xem không đặc tả phép đếm Unicode; chưa kiểm chứng composer X/Threads thực tế. Gate vẫn mở; xem `KIEM-THU.md`.

> QA-02 / DIG-02: trên một kho giả, đã đổi thứ tự và lưu nội dung qua giao diện; sau khi dừng và mở lại tiến trình máy chủ, trình duyệt mở lại đúng revision, thứ tự, nội dung và URL từng mục. Đây là lượt thử riêng với bản tin hai mục được chuẩn bị bằng service; QA-02 vẫn mở. Xem `KIEM-THU.md`.

> APR-01 / QA-02: server v5 mã 1b57698 trên kho giả đã thử lưu, xác nhận lại và duyệt lại bản X chưa ghi nhận; bản X khác đã ghi nhận 1/2 theo v4 giữ snapshot lịch sử và ghi nhận thêm URL giả đoạn 2 qua giao diện. Phạm vi, giới hạn và các trạng thái khác xem KIEM-THU.md; QA-02 và BASE-03 vẫn mở.

> MIG-01…05 / QA-03: bổ sung kiểm tra integrity, khóa ngoại, restore DB hỏng và thử khôi phục backup schema 3 bằng mã 0.3.1 trên fixture. Python 190/190 và JavaScript 41/41 đạt. Phần thử bản sao SQLite cũ không áp dụng theo xác nhận của người dùng; chưa triển khai. Xem `KIEM-THU.md`.

> Cập nhật sau commit `6c0b631`: trình duyệt tích hợp trên các kho fixture đã thử policy v4, khôi phục phiên sau restart và ngắt phản hồi sau khi ghi nhận URL, số liệu hoặc đính chính. Số liệu thử lại cùng nội dung có một lượt; đính chính đã lưu được đối chiếu ở thẻ khác. Các trường hợp này được tiêm lỗi, không phải kiểm tra mọi lỗi mạng; QA-02 và BASE-03 vẫn mở. Chi tiết tại `KIEM-THU.md`.

> Cập nhật 04/11/2026: Bằng chứng giao diện mới hơn các nhận xét ban đầu trong bảng: trên kho fixture, đã thử đính chính, hủy và ghi lại cùng URL cho X; ghi nhận URL giả trên Facebook và Threads, lưu và xem lại số liệu riêng của hai kênh. Sau tải lại, tổng số ba đoạn và URL cùng số liệu Threads vẫn hiển thị. Đây là smoke test; QA-02 và việc đối chiếu URL thực tế vẫn mở. Xem `KIEM-THU.md`.

> Bổ sung 04/11: Edge trên fixture tạo bản tin từ ba tin giả, kể cả hai tin ẩn khi lọc; đổi thứ tự bằng bàn phím và tải lại giữ thứ tự cùng URL từng mục. Chưa restart server trong cùng lượt UI; bằng chứng restart service là kiểm thử riêng.

> Bổ sung restart: từ kho fixture đó tạo backup qua UI, khôi phục sang thư mục riêng, dừng và chạy lại server của bản khôi phục. Edge mở bản tin #2 vẫn thấy đúng thứ tự Alpha → Charlie → Bravo và ba URL nguồn. Không suy rộng sang mất điện hay dữ liệu vận hành.

> QA-02: lỗi phục hồi phiên sau restart đã được xử lý bằng nút khôi phục không tải trang; không tự gửi lại thao tác và có so sánh thư mục kho. Test handler, HTTP và smoke UI trên kho giả đạt; đường dẫn trùng không chứng minh kho chưa bị thay thế. Các trường hợp kết quả lưu không rõ được thử sau đó như nêu ở cập nhật đầu tài liệu; chi tiết tại `KIEM-THU.md`.

> FIX-03: người dùng đã xác nhận URL-01…04 đạt trên Edge với kho giả của hotfix 0.3.1 độc lập; API kho thử xác nhận trạng thái và URL cuối. Hồi quy 89 Python, 6 JavaScript đạt; xem `KIEM-THU.md`. Đây chưa phải nghiệm thu toàn bộ QA-02 hoặc phát hành 0.3.1.

> QA-02: người dùng đã kiểm tra cả hai lựa chọn của cảnh báo khi chuyển bản tin có tiêu đề chưa lưu trên Edge với kho giả. API kho thử xác nhận hai bản tin vẫn ở revision ban đầu; xem `KIEM-THU.md`. Các trường hợp rời trang, biểu mẫu và thao tác bàn phím còn lại vẫn cần đối chiếu.

Ngày cập nhật bằng chứng: 04/11/2026. Đối chiếu mục 10 của [kế hoạch nâng cấp](KE-HOACH-NANG-CAP-BAN-TIN-DA-KENH.md) với mã và bằng chứng được ghi trong [nhật ký kiểm thử](KIEM-THU.md). Đây là trạng thái kiểm chứng, không phải chấp thuận triển khai. Các lệnh và kết quả chi tiết, dữ liệu sử dụng và giới hạn được ghi tại nhật ký đó.

> Bổ sung sau `46a6e6d`: hồi quy 196 Python và 44 JavaScript đạt; đã smoke lưu trữ/khôi phục trên trình duyệt với kho giả. Ma trận bảo vệ POST nay bao gồm 15 route đa kênh, gồm lưu trữ; bảy tài nguyên tĩnh được phép cũng được kiểm tra HTTP. Đã thử bốn cặp lưu và ghi nhận cùng revision trên SQLite giả. Các kiểm thử này không đóng QA-02 hoặc toàn bộ điều kiện phát hành; xem `KIEM-THU.md`.

| Điều kiện mục 10 | Bằng chứng hiện có | Phần còn thiếu để kết luận |
| --- | --- | --- |
| Ba bài nguồn, thứ tự và truy vết qua restart | `tests/test_bulletins.py`: `test_reorder_and_packet_preserve_snapshots_after_refresh_restart`, `test_three_channel_bulletin_survives_backup_restore_with_partial_publication`; Edge tạo, đổi thứ tự và tải lại ba tin giả; backup, khôi phục và restart server bản sao rồi mở lại đúng thứ tự và nguồn. | Điều kiện này đạt trong phạm vi fixture; QA Windows tổng thể vẫn mở. |
| Biên tập thủ công hoặc gói tư liệu, không phát sinh model call | Ba pilot fixture trong `KIEM-THU.md`; test ba route không tồn tại trong `tests/test_server.py`; test service `test_multichannel_workflow_does_not_make_network_connections` thực hiện từ kho mới đến ghi nhận URL giả khi hai API kết nối socket bị chặn. Người dùng đã xác nhận mẫu đầu ra giả lập cho ba kênh phù hợp quy trình dự kiến. | Test không bao phủ mọi đường chạy hay tiến trình ngoài; ba lượt pilot là dữ liệu giả và mẫu được duyệt không phải tệp của ba lượt pilot cũ. |
| Ba biến thể độc lập, có thể dùng một kênh | Test ba kênh qua backup/restore trong `tests/test_bulletins.py`; các lượt pilot Facebook, Threads và X trên kho demo. | Chưa kiểm chứng toàn bộ đường thao tác và chính sách của ba nền tảng trên tài khoản đích. |
| Đầu ra, bộ đếm, preview, copy, file và approval khớp; giữ nguồn | `test_approved_export_matches_preview_and_changes_invalidate`, `test_split_rechecks_numbering_and_keeps_sources_and_text`; ba tệp pilot được đối chiếu; đã thử copy và fallback clipboard ở phạm vi ghi trong `KIEM-THU.md`. | BASE-03 còn mở: Threads là ước lượng, X chưa xác minh đầy đủ emoji và URL thực tế; chưa kiểm tra mọi luồng copy/chia trên trình duyệt. |
| Hủy duyệt đúng phạm vi; bản ghi nhận bất biến; ghi nhận một phần | Các test `test_parent_edit_resets_checks_of_unlocked_variants_only`, `test_cancel_all_preserves_lock_and_history_and_can_record_again`, `test_policy_change_after_partial_recording_preserves_snapshot`; smoke kho fixture X đã thử đính chính, hủy và ghi lại cùng URL, thấy tiến độ 0/2 → 1/2 → 0/2 → 1/2. | Chưa thử mọi kênh, toàn bộ luồng từ đầu hoặc thay policy qua giao diện; công cụ trình duyệt từng bị kẹt ở hộp xác nhận. |
| URL và số liệu riêng theo kênh/đoạn, không giữ URL bài khác | Test binding trong `tests/draft-state.test.js`, test handler trong `tests/correction-ui.test.js`, test vòng đời HTTP trong `tests/test_server.py`; kho fixture đã ghi URL giả Facebook/Threads, lưu và xem lại số liệu riêng, chặn đổi kênh khi số liệu chưa lưu. Trên X fixture, đã thử ngắt phản hồi sau commit URL, số liệu và đính chính; đối chiếu kết quả ở UI và thẻ khác. | Còn QA rời trang và các tổ hợp lỗi/kênh/đoạn qua trình duyệt; chưa đối chiếu mọi dạng URL nền tảng hoặc số liệu tài khoản thật. |
| Legacy giữ nội dung/hash/export/history; migration và restore vượt test lỗi | Fixture schema 3 từ mã cũ và fixture schema 1/2 mô phỏng trong `tests/test_migrations_v4.py`; test lỗi backup/migration/restore, cấu trúc schema 4 và restore liên thông ba kênh; thử phục hồi backup schema 3 rồi mở bằng mã 0.3.1 trên fixture. | Không áp dụng thử trên bản sao SQLite cũ trong đợt này vì người dùng xác nhận chưa có dữ liệu cũ; fixture 1/2 không phải snapshot lịch sử. Chưa kiểm chứng mọi payload hoặc lỗi hệ thống tập tin. |
| Test đạt và có QA trình duyệt/clipboard | Hồi quy cho thay đổi tại `6c0b631`: 183/183 Python và 36/36 JavaScript đạt; đã có bằng chứng dán clipboard và fallback trên Edge với dữ liệu giả. Trình duyệt tích hợp đã thao tác và kiểm tra các trường hợp ngắt phản hồi nêu trên. | QA-02 chưa hoàn tất toàn bộ bàn phím, tab, trạng thái chưa lưu và các luồng mới. Cần chạy lại hồi quy sau mỗi thay đổi chức năng. |
| README, hướng dẫn, kiến trúc, kiểm thử cập nhật | `README.md`, `docs/HUONG-DAN-SU-DUNG.md`, `docs/KIEN-TRUC.md`, `docs/KIEM-THU.md` và `docs/API-BAN-TIN-DA-KENH.md` đã có nội dung cho 0.4. | Cần rà soát lại tính nhất quán theo trạng thái cuối trước phát hành, bao gồm policy và kết quả QA còn mở. |
| Người dùng xem pilot và quyết định triển khai | Ba lượt pilot fixture đã ghi thời gian và vấn đề trong `KIEM-THU.md`. Ngày 04/11/2026 người dùng xác nhận [mẫu đầu ra giả lập](MAU-DAU-RA-GIA-LAP-0.4.md) cho ba kênh phù hợp với quy trình dự kiến. | Mẫu mới không phải tệp của ba pilot cũ; xác nhận này không phải quyết định triển khai lên kho vận hành. Các điều kiện QA và chính sách còn mở. |

## Các việc tiếp theo có phụ thuộc bên ngoài

1. Hoàn tất QA-02 trên kho giả, gồm các thao tác bàn phím và tổ hợp kênh/đoạn còn thiếu. Phần rời trang và tải lại khi có nội dung chưa lưu được người dùng chọn để sau; hai lựa chọn khi chuyển bản tin đã được người dùng thử. Các lượt có bằng chứng UI được ghi riêng trong `KIEM-THU.md`.
2. Hoàn tất BASE-03 bằng bằng chứng phù hợp cho cách đếm và mẫu URL của các nền tảng; khi chưa chứng minh được thì giữ nhãn ước lượng và gate mở.
3. Không áp dụng thử migration/restore trên bản sao SQLite cũ trong đợt này: người dùng xác nhận chưa có dữ liệu cũ. Các kiểm thử migration/restore bằng fixture vẫn được giữ; không coi đó là thử dữ liệu vận hành.
4. Tổng hợp bằng chứng mới, đối chiếu lại toàn bộ mục 10 và để người dùng xem pilot trước quyết định triển khai.

Không suy ra bài đã đăng hoặc nguồn đã được xác minh từ URL, kiểm thử fixture hay bản duyệt nội bộ.

## Đối chiếu bổ sung về bộ đếm ngày 04/11/2026

- [Cấu hình twitter-text của X](https://github.com/twitter/twitter-text/blob/master/config/README.md) mô tả cấu hình có nhận diện emoji: cả cụm emoji, kể cả cụm nối bằng ZWJ, được tính theo trọng số mặc định; URL dùng độ dài chuyển đổi mặc định 23. Đây là tài liệu thư viện, không chứng minh composer X hiện tại dùng cùng phiên bản dữ liệu emoji. Bộ đếm trong repo dùng dữ liệu Unicode 15.1 được ghim và có fixture riêng; emoji mới hơn và hành vi thực tế vẫn chưa được nghiệm thu.
- Khi thử truy cập [tài liệu tạo bài Threads của Meta](https://developers.facebook.com/documentation/threads/posts) và [tổng quan Threads API](https://developers.facebook.com/documentation/threads/overview), công cụ tra cứu trả HTTP 429. Vì chưa đọc được nội dung gốc trong lượt này, không coi thông tin từ nguồn thứ ba là xác nhận quy tắc emoji hay số liên kết, và không thay đổi policy dựa trên chúng. Việc đăng thủ công còn cần đối chiếu composer của người dùng; BASE-03 vẫn mở.

## Cập nhật ngày 04/11/2026

- Hồi quy trước thay đổi: 163/163 Python và 20/20 JavaScript đạt. Các test restore sử dụng kho tạm/fixture.
- Edge mở kho fixture riêng có hai mục và phiên bản X hai đoạn đã ghi nhận giả một đoạn. Giao diện hiển thị trạng thái 1/2, nguồn của từng đoạn, liên kết giả, nút nhập số liệu và đính chính. Fixture được chuẩn bị bằng service, nên đây không phải kiểm thử toàn bộ luồng từ đầu.
- Khi nhập tám số liệu giả, công cụ điều khiển bị kẹt ở chuỗi hộp thoại; chưa xác nhận dữ liệu đã được lưu, chưa kiểm tra đính chính thành công hay luồng từ đầu đến cuối. Đây là giới hạn công cụ, chưa đủ bằng chứng kết luận ứng dụng lỗi hoặc quyết định thay hộp thoại. QA-02 tiếp tục mở.
- Sau lần thử xác nhận đoạn hai, thẻ mới trên cùng server fixture hiển thị trạng thái 2/2 và hai URL giả đúng từng đoạn. Đoạn một đã được chuẩn bị bằng service; không xác định được thao tác xác nhận nào hoàn tất đoạn hai. Chưa kiểm tra restart server, nhập số liệu hoặc đính chính thành công.
- Đối chiếu ngày 04/11: [Meta](https://about.fb.com/news/2023/07/introducing-threads-new-app-text-sharing/) nêu bài Threads thông thường tối đa 500 ký tự; [Meta](https://about.fb.com/news/2025/09/attach-text-threads-posts-share-longer-perspectives/) cũng mô tả tệp văn bản đính kèm riêng. [X](https://help.x.com/en/using-x/types-of-posts) nêu giới hạn thông thường 280 ký tự và các gói có bài dài; [X](https://help.x.com/en/using-twitter/how-to-tweet-a-link.html) nêu URL được tính 23 ký tự. Các nguồn này chưa xác minh đầy đủ phép đếm Unicode, emoji mới hay mọi alias URL. BASE-03 vẫn mở và cần kiểm tra bản thực tế trước khi đăng.
- Theo xác nhận của người dùng, thử trên bản sao SQLite cũ không áp dụng vì chưa có dữ liệu cũ. Nếu về sau xuất hiện dữ liệu cần nâng cấp, phải lập lại phương án thử trên bản sao trước khi xử lý dữ liệu đó.
