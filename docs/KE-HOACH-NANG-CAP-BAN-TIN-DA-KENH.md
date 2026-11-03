# Kế hoạch sửa lỗi và nâng cấp Bàn tin đa kênh

> Cập nhật kiểm thử 04/11/2026: Trên fixture, đã ghi nhận URL giả Facebook và Threads, đối chiếu số liệu riêng 101/0 và 202/3, rồi tải lại và xác nhận số liệu Threads còn lưu. Tổng quan có ba đoạn ghi nhận trên ba phiên bản, trong đó X mới có 1/2 đoạn. QA-02 và BASE-03 vẫn mở; chi tiết tại `KIEM-THU.md`.

> Bổ sung DIG-01/02: trên Edge, chọn ba tin giả bằng bàn phím, lọc còn một tin và tạo bản tin vẫn gồm cả ba; đổi thứ tự rồi tải lại giữ đúng thứ tự và URL từng mục. Chưa thử restart server ở lượt UI này; chi tiết tại `KIEM-THU.md`.

> Bổ sung restart: sao lưu kho fixture nói trên, khôi phục sang thư mục riêng, dừng và chạy lại server của bản khôi phục; Edge mở lại bản tin giữ thứ tự và ba URL nguồn. Xem phạm vi tại `KIEM-THU.md`.

> Bổ sung QA-02: biểu mẫu số liệu Threads giữ giá trị 303 và chặn chuyển sang Facebook khi chưa lưu; sau khi lưu có thể chuyển kênh và xem lại cả hai lượt số liệu. Các tình huống rời trang và mất kết nối vẫn cần kiểm tra riêng.

> QA-02 / lỗi cần xử lý: khi server thử dừng trước lúc lưu, giá trị đang nhập được giữ và có thông báo mất kết nối. Sau restart, lần lưu lại trên trang cũ bị từ chối vì phiên thay đổi và thông báo yêu cầu tải lại, có nguy cơ mất nội dung chưa lưu. Cần cơ chế khôi phục an toàn và kiểm thử cả kết quả lưu không rõ; trước mắt sao chép nội dung trước khi tải lại. Xem `KIEM-THU.md`.

> Bổ sung: đã thêm nút khôi phục phiên không tải lại và không tự gửi lại thao tác; kiểm tra thư mục dữ liệu và yêu cầu người dùng đối chiếu trước khi lưu lại. Test handler giả đạt; chưa smoke giao diện thật sau sửa, chưa thử trường hợp ghi thành công nhưng mất phản hồi. Đường dẫn giống nhau không chứng minh nội dung kho không bị thay thế.

> Kiểm thử HTTP bổ sung: server mới cùng kho tạm từ chối cookie/CSRF cũ, chấp nhận phiên mới, lưu revision hiện tại và từ chối gửi lại revision cũ. Đây là bằng chứng server, chưa thay thế smoke trình duyệt hoặc thử mất phản hồi.

> Bổ sung thử mất phản hồi: test đóng socket sau khi server ghi URL giả hoặc số liệu; gửi lại cùng khóa không tạo bản ghi trùng. Đây là lỗi tiêm ở server thử; chưa xác minh luồng mạng và thao tác lại bằng trình duyệt. Chi tiết tại `KIEM-THU.md`.

> Bảo vệ đổi kho: cập nhật trạng thái nền hoặc khôi phục phiên phát hiện đường dẫn kho khác sẽ giữ nội dung và chặn POST tiếp theo. Test handler đạt; chưa thử UI thật, không phát hiện DB bị thay thế trong cùng thư mục hoặc hủy request đã gửi.

> Bổ sung race: sau khi phát hiện đổi kho, phản hồi khôi phục phiên hoặc cập nhật nền đến muộn không được ẩn cảnh báo hay thay token. Hai test handler giả đạt; chưa có smoke UI.

> Bổ sung APR-04: API đọc một phiên bản hoặc danh sách phiên bản dùng transaction đọc để trạng thái, bản duyệt và số ghi nhận thuộc cùng snapshot. Test tiêm thay đổi đồng thời trên SQLite WAL đạt; chưa smoke tình huống này qua UI/HTTP. Chi tiết tại `KIEM-THU.md`.

> Bổ sung DIG-02/PUB-04: chi tiết bản tin và thống kê cũng dùng snapshot đọc nhất quán; đã tái hiện và sửa trường hợp revision cũ đi cùng mục mới hoặc số bản tin/bài ghi nhận không khớp khi có ghi đồng thời. Test service trên SQLite WAL đạt; chưa thử đồng thời qua UI/HTTP.

> Bổ sung PUB-03/04: danh sách ghi nhận, sự kiện và số liệu được đọc cùng snapshot; test hủy xen giữa các câu đọc đã tái hiện lỗi và đạt sau sửa. Chưa thử đồng thời qua UI/HTTP; xem `KIEM-THU.md`.

> Bổ sung BASE-02: tạo phiên bản từ chối kiểu `platform` sai bằng HTTP 400 thay vì đóng kết nối; test HTTP xác nhận không tạo bản ghi. Hợp đồng API tổng thể vẫn cần tiếp tục đối chiếu; xem `KIEM-THU.md`.

> Bổ sung BASE-02/NEWS-01: ID tin ngoài phạm vi số nguyên 64-bit SQLite bị từ chối khi tạo bản tin hoặc thêm mục, không làm thay đổi kho; test HTTP và hồi quy đạt. Chưa xác nhận biên ID của mọi route.

> Bổ sung BASE-02: các route dùng ID số kiểm tra giới hạn trước chuyển đổi và truy cập SQLite; test HTTP với ID quá lớn và chuỗi rất dài đạt. Các trường ID khác trong payload vẫn cần đối chiếu riêng.

> Bổ sung BASE-02 / legacy: API tạo draft cũ cũng từ chối ID tin vượt phạm vi SQLite bằng HTTP 400; test HTTP và hồi quy đạt. Xem `KIEM-THU.md`.

> Bổ sung PUB-02/03: tách namespace khóa đính chính nội bộ khỏi khóa client để tránh lỗi trùng khóa; kiểm thử tái hiện lỗi cũ và đối chiếu lịch sử, retry trên kho tạm. Xem `KIEM-THU.md`.

> Bổ sung FIX-03: trên nhánh 0.4, giao diện chặn URL bài cũ để trống và giữ trạng thái đã duyệt; test service kiểm tra thêm URL sai miền và trang chủ. Hồi quy gần nhất 164 Python, 28 JavaScript đạt. Chưa kiểm tra các URL sai này qua UI hoặc xác nhận bản 0.3.1 phát hành độc lập.

> Cập nhật tiếp FIX-03: vùng xác nhận bài cũ nằm trên trang; Edge đã thử URL sai miền, trang chủ, đổi URL và ghi nhận URL giả hợp lệ trên kho fixture. Sau sửa hồi quy 164 Python và 29 JavaScript đạt. Chưa xác nhận bản 0.3.1 phát hành độc lập; xem `KIEM-THU.md`.

- Ngày lập / cập nhật: **03/11/2026**, giờ Việt Nam.
- Repository: [dvha85/ban-tin](https://github.com/dvha85/ban-tin).
- Mốc mã nguồn được review: **`a180354e52e98a678d093609f9e8f2d37e6cd0a3`**, nhánh `main`, phiên bản ứng dụng `0.3.0`, dữ liệu schema `3`.
- Trạng thái: **Đang triển khai; chưa nghiệm thu hoặc phát hành 0.4.** Chi tiết và bằng chứng ở mục 11.
- Tài liệu này theo dõi kế hoạch và tiến độ, không xác nhận đã nâng cấp dữ liệu đang sử dụng hoặc đăng bài ra ngoài.
- Hướng phát hành đề xuất: **0.3.1 sửa lỗi → 0.4 bản tin nhiều mục và đầu ra Facebook / Threads / X**. Đây là mốc chức năng, chưa ấn định ngày phát hành.

## 1. Kết quả cần đạt

Một người vận hành có thể chọn nhiều tin, biên tập thành một bản tin có nguồn rõ ràng, chuẩn bị phiên bản riêng cho từng mạng xã hội, duyệt đúng nội dung cuối cùng, sao chép để tự đăng và ghi nhận kết quả riêng từng kênh.

Luồng đích:

1. Lấy tin → lọc theo chủ đề / khoảng thời gian → chọn khoảng 3–5 tin.
2. Sắp xếp các mục → đọc nguồn → bổ sung ghi chú kiểm chứng.
3. Chuẩn bị gói tư liệu nhiều mục → người dùng chuyển sang ChatGPT nếu muốn → nhập lại kết quả hoặc tự viết.
4. Biên tập bản tin gốc → chuẩn bị các biến thể Facebook / Threads / X.
5. Xem chính xác văn bản sẽ xuất, độ dài và các đoạn trong chuỗi bài.
6. Duyệt từng biến thể → sao chép / tải văn bản → tự đăng trên nền tảng.
7. Ghi nhận URL từng bài / đoạn và số liệu quan sát được, không làm lẫn giữa các kênh.

**Định nghĩa “tổng hợp” ở bản 0.4:** có cấu trúc bản tin nhiều mục, gói tư liệu và đầu ra đa kênh; nội dung do người dùng tự viết hoặc nhận qua bước AI thủ công. Không hứa có chức năng một nút tự đọc toàn văn, tự viết đúng sự thật và tự đăng.

## 2. Hiện trạng đã kiểm tra

| Hạng mục | Hiện tại | Hệ quả đối với mục tiêu |
| --- | --- | --- |
| Thu thập | RSS/API/web, nguồn tùy chỉnh, chống trùng cơ bản | Có đầu vào, nhưng chưa gom theo sự kiện hoặc tạo bản tin |
| Tạo draft | Một `article_id`; tiêu đề/nội dung ban đầu rỗng | Chưa chọn nhiều bài để tổng hợp |
| Gói tư liệu | Prompt cho một bài Page khoảng 250–400 từ | Người dùng phải chuyển đi/nhập lại; chưa có ba định dạng |
| Duyệt | Checklist, revision, hash, sửa bài làm mất duyệt | Cần giữ và mở rộng sang từng biến thể |
| Xuất | Một chuỗi tiêu đề + nội dung + danh sách URL | Chưa đếm toàn bộ đầu ra theo nền tảng hoặc chia chuỗi |
| Ghi nhận đăng | Một `post_url`, chỉ nhận Facebook | Chưa quản lý Threads/X và nhiều lượt đăng |
| Giao diện | Ô URL không được đặt lại khi đổi draft | Có thể ghi nhận bài B bằng URL còn sót của bài A |

Bằng chứng từ phiên review ngày 03/11/2026:

- Bộ hiện có: **88/88 kiểm thử đạt**, Python 3.13.13; không có nghĩa là các chức năng dự kiến trong kế hoạch đã được kiểm thử.
- Probe RSS chỉ đọc, không ghi DB vận hành: **4/4 nguồn**, 70 mục; 7 trích đoạn Google ngắn hơn 80 ký tự. Đây là kiểm tra đầu nối, không xác minh chất lượng hay sự thật của 70 mục.
- Lỗi URL đã tái hiện bằng cách thực thi các hàm giao diện hiện có với DOM giả trong Node; chưa có kiểm thử hồi quy giao diện được lưu vào repo cho lỗi này.
- Chưa thử đăng bằng tài khoản Facebook/Threads/X thật, chưa xác minh quyền tài khoản hoặc điều kiện kiếm tiền.

Điểm mã nguồn để bắt đầu; số dòng có thể thay đổi sau triển khai:

- [service.py](../newsroom/service.py): `create_draft` khoảng dòng 231, `approve` 329, `export` 354, `mark_published` 360, `packet` 385.
- [app.js](../newsroom/static/app.js): `setDraft` khoảng dòng 224–257, gửi URL khoảng dòng 558–562.
- [feeds.py](../newsroom/feeds.py): `plain_text`, `parse_feed`, `rank_article`.
- [collection_service.py](../newsroom/collection_service.py): `init_collection`, thu thập bằng chứng và quản lý phiên bản DB.
- [__main__.py](../newsroom/__main__.py): `restore` đang chấp nhận schema 1/2/3.
- [test_workflow.py](../tests/test_workflow.py), [test_server.py](../tests/test_server.py): hợp đồng hiện có cần bảo toàn.

## 3. Phạm vi và nguyên tắc

### 3.1. Có trong đợt nâng cấp

- Sửa lỗi URL bị giữ giữa các bản nháp.
- Chọn nhiều bài và sắp xếp bản tin nhiều mục; giữ nguồn theo từng mục.
- Gói tư liệu có cấu trúc cho thao tác AI thủ công; biên tập được khi không dùng AI.
- Nội dung, đích đăng, revision và duyệt riêng cho Facebook / Threads / X.
- Preview, kiểm tra toàn bộ văn bản cuối, chia chuỗi có kiểm soát, copy và tải `.txt`.
- Nhật ký đăng thủ công theo biến thể / đoạn; số liệu theo lượt đăng.
- Migration, backup/restore, kiểm thử và hướng dẫn sử dụng tương ứng.

### 3.2. Không tự mở rộng trong đợt này

- Không OAuth, API đăng bài, lịch tự đăng, tự đăng nhập hoặc điều khiển tài khoản mạng xã hội.
- Không gọi model trả phí để viết nội dung; không bật/tăng quyền hoặc hạn mức Hermes.
- Không tải toàn văn hàng loạt, không nới robots/paywall/phạm vi nguồn để lấy đủ tin.
- Không tự tạo ảnh/video, carousel, text attachment Threads hoặc bài dài theo gói tài khoản X.
- Không chứng nhận bản quyền, tính nguyên bản, khả năng kiếm tiền hoặc sự thật của nội dung.
- Không đưa máy chủ ra LAN/Internet, chuyển sang nhiều người dùng hoặc yêu cầu Docker/WSL.
- Không tự sửa DB chính, commit/push hoặc đăng bài thật chỉ vì đã có kế hoạch.

### 3.3. Các lựa chọn mặc định đề xuất

| ID | Lựa chọn | Ghi chú |
| --- | --- | --- |
| D01 | Giữ giao diện HTML/CSS/JS và backend Python hiện tại | Không đổi framework để làm đợt này |
| D02 | Bản tin mới có 1–10 mục, gợi ý 3–5 khi tổng hợp; luồng một bài cũ vẫn dùng được | Cho phép bản một mục để chuyển bài cũ sang đầu ra đa kênh; đây không phải giới hạn nền tảng |
| D03 | Mỗi mục tối đa 3 nguồn, toàn bản tin tối đa 20 URL nguồn khác nhau | Tách khỏi giới hạn 8 nguồn của draft cũ; không cắt nguồn âm thầm |
| D04 | Thêm bảng schema 4, giữ dữ liệu và workflow legacy | Không chuyển đổi hàng loạt hoặc tính lại hash bài cũ |
| D05 | Mỗi biến thể thuộc một nền tảng và một nhãn đích đăng | Muốn đích khác: tạo bản sao chưa duyệt; không cần đăng nhập tài khoản |
| D06 | Duyệt toàn bộ các đoạn của một biến thể cùng lúc | Sửa một đoạn làm mất duyệt của biến thể đó |
| D07 | Bản đã ghi nhận đăng được giữ nguyên | Đính chính nhật ký bằng sự kiện có lý do; không xóa dấu vết |
| D08 | Bộ đếm/renderer phía server là chuẩn | UI không được tự quyết định một bài có đủ điều kiện xuất hay không |
| D09 | Node chỉ dùng khi phát triển/kiểm thử | Không biến thành điều kiện chạy ứng dụng thông thường |

Những lựa chọn cần khảo sát kỹ thuật trước khi đóng thiết kế: thư viện/thuật toán đếm X; cách đếm Unicode Threads; mẫu URL bài đăng hợp lệ của từng nền tảng. Ghi kết quả, nguồn và ngày xác minh tại mục 12. Nếu chưa chứng minh được bộ đếm đúng, chưa tuyên bố nền tảng đó sẵn sàng phát hành.

## 4. Thiết kế chức năng

### 4.1. Sửa lỗi liên kết — phát hành độc lập 0.3.1

- Khi chọn draft khác: xóa URL đang nhập của draft cũ; bài đã ghi nhận hiển thị URL lấy từ bản ghi của chính nó.
- Không dùng giá trị DOM còn sót làm dữ liệu của bài mới.
- Thay đổi URL chưa gửi phải được quản lý rõ là dữ liệu chưa lưu; chuyển bài cần cảnh báo phù hợp, không giữ lẫn sang bài kế tiếp.
- Trong hộp xác nhận, hiển thị tiêu đề và URL sẽ ghi nhận; ở bản đa kênh hiển thị thêm nền tảng, đích và số đoạn.
- URL rỗng/không hợp lệ phải bị chặn phía server; lỗi không tăng số bài đã đăng.
- Không thay đổi schema hoặc nới điều kiện duyệt trong hotfix.

### 4.2. Chọn tin và soạn bản tin gốc

- Hộp tin có checkbox, số tin đã chọn, nút xóa lựa chọn và “Tạo bản tin tổng hợp”. Bộ lọc không âm thầm bỏ lựa chọn đang ẩn.
- Cửa sổ thời gian: 24 giờ / 7 ngày / tùy chọn, theo ngày nguồn; hiển thị rõ `published`, `updated`, `unknown`.
- Tin thiếu ngày, ngày tương lai hoặc ngoài cửa sổ không được tự gắn nhãn “tin mới hôm nay”; có thể thêm chủ động kèm cảnh báo.
- Bản tin có ngày biên tập, tiêu đề, lời mở đầu, các mục theo thứ tự và phần kết tùy chọn. Lưu thời điểm bằng UTC, hiển thị giờ Việt Nam.
- Mỗi mục có tiêu đề ngắn, nội dung tóm tắt do người dùng biên tập, ý nghĩa thực tế, giới hạn cần biết và nguồn liên quan.
- Dùng nút Lên/Xuống để đổi thứ tự bằng bàn phím; kéo-thả chỉ là tiện ích bổ sung.
- Một article không được thêm hai lần trong cùng bản tin. Cảnh báo khi đã dùng ở bản tin khác, không cấm tái sử dụng cho nội dung cập nhật.
- Không tự gom sự kiện theo ngữ nghĩa. Bản tối thiểu cho bổ sung nguồn vào một mục và bỏ mục trùng bằng thao tác người dùng; gộp/tách mục tự động để sau.
- Lưu từng mục có revision, không gửi lại toàn bộ kho tin. Giữ request tối đa 128 KB; kiểm tra kích thước UTF-8 trước gửi và phía server.

### 4.3. Nguồn, kiểm chứng và gói tư liệu

- Mỗi nguồn có ID ổn định, URL chuẩn hóa, tên nguồn, tiêu đề, trích đoạn, ngày nguồn/loại ngày, ngày lấy, phương pháp và phạm vi `excerpt`; lưu hash khi thực sự có.
- Snapshot tư liệu thuộc bản tin. Refresh Hộp tin không cập nhật âm thầm bản tin hoặc biến thể đã duyệt.
- Ghi chú kiểm chứng tách khỏi trích đoạn gốc. Nếu cho sửa trích đoạn, lưu rõ bản sửa thủ công và không dùng hash gốc để mô tả bản sửa.
- Cảnh báo trích đoạn rỗng/ngắn, dữ kiện thiếu và tư liệu cũ. Ngưỡng ngắn, ví dụ dưới 80 ký tự, chỉ hỗ trợ thao tác, không phải điểm tin cậy.
- Mỗi mục có checklist kiểm tra các khẳng định chính; ghi nguồn đối chiếu hoặc lý do chỉ dùng nguồn hãng. Không coi hai tên miền mặc nhiên là hai nguồn độc lập.
- Giữ nhãn “theo hãng” khi chỉ có thông báo của hãng; không suy diễn thành đánh giá độc lập hoặc trải nghiệm thực tế.
- Tư liệu gửi AI được phân cách là dữ liệu không đáng tin cậy, không phải chỉ dẫn. Prompt yêu cầu giữ ID mục/nguồn, không tự thêm dữ kiện và để danh sách điều cần kiểm tra riêng khỏi bài đăng.
- Gói tư liệu tối đa đề xuất 64 KiB UTF-8. Nếu vượt, hiển thị phần nào quá lớn để người dùng chọn/bổ sung ghi chú ngắn hơn; không cắt giữa câu hoặc bỏ nguồn mà không báo.
- Có thể tự viết toàn bộ mà không mở AI. Nút chuẩn bị tư liệu không tự tạo bài hoàn chỉnh hoặc gọi dịch vụ ngoài.
- Bản đầu dùng biểu mẫu nhập nội dung có cấu trúc, không phụ thuộc parser tự hiểu mọi định dạng trả lời của ChatGPT; import JSON AI có thể làm sau.

### 4.4. Biến thể theo nền tảng

| Nền tảng | Đầu ra bản 0.4 | Quy tắc |
| --- | --- | --- |
| Facebook | Một bài có mở đầu, từng mục và nguồn | Giới hạn biên tập nội bộ; không quảng bá giới hạn 12.000 ký tự hiện có là giới hạn chính thức của Facebook |
| Threads | Một bài ngắn hoặc chuỗi bài | Hồ sơ bài thông thường 500 ký tự; chưa hỗ trợ text attachment dài |
| X | Một bài ngắn hoặc chuỗi bài | Hồ sơ chuẩn 280 đơn vị ký tự theo quy tắc weighted count, không mặc định tài khoản có quyền bài dài |

Nguồn đối chiếu ngày 03/11/2026: [Meta về bài Threads và text attachment](https://about.fb.com/news/2025/09/attach-text-threads-posts-share-longer-perspectives/), [X về cách đếm ký tự](https://docs.x.com/fundamentals/counting-characters). Đây là căn cứ cho hồ sơ đầu ra, không xác nhận quyền/tính năng của tài khoản người dùng. Kiểm tra lại trước phát hành.

- Mỗi biến thể có nội dung và đích đăng riêng; lưu Facebook không sửa Threads/X.
- “Chuẩn bị biến thể” tạo khung có nhãn chưa biên tập hoặc gói yêu cầu viết lại; không tự rút gọn bằng cách cắt chữ và không giả là đã viết hoàn chỉnh.
- Người dùng có thể chỉ làm một hoặc hai nền tảng; không bắt tạo đủ ba để xuất.
- Tạo lại biến thể không ghi đè nội dung đã chỉnh. Cho xem khác biệt / tạo bản sao; cần xác nhận rõ nếu thay phần đang soạn.
- Mỗi đoạn liên kết tới các mục/nguồn thực sự được sử dụng. Mỗi mục xuất hiện trong biến thể phải có nguồn truy vết, không chỉ một danh sách nguồn toàn bản tin mất quan hệ.
- Cho phép bỏ một mục khỏi phiên bản ngắn nhưng phải hiển thị rõ; không bỏ nguồn của mục còn được giữ để vừa độ dài.

### 4.5. Preview, đếm ký tự và chia chuỗi

- Có một renderer chính thức tạo danh sách `rendered_posts`; preview, copy, `.txt`, kiểm tra và hash duyệt cùng dùng danh sách này.
- Đếm chuỗi cuối cùng gồm tiêu đề nếu có, nội dung, khoảng trắng, xuống dòng, URL nguồn và đánh số `1/N`. Không chỉ đếm ô body.
- X cần xử lý đúng chuẩn hóa Unicode, emoji và URL; không dùng `len()` hoặc `String.length` làm bộ đếm thay thế. Lựa chọn triển khai phải qua bộ fixture tham chiếu và kiểm tra giấy phép/phụ thuộc.
- Với Threads, xác minh cách tính ký tự ghép/emoji trước khi chốt; không sao chép quy tắc đếm của X sang.
- Server kiểm tra lại lúc duyệt, xuất và ghi nhận; UI hiển thị kết quả/phiên bản chính sách từ server. Có thể gọi preview có debounce, không bắt buộc hai bộ thuật toán độc lập.
- Chia theo mục/đoạn/câu; không cắt URL hoặc cụm ký tự đang ghép. Đây là thao tác phân đoạn, không phải tóm tắt ngữ nghĩa.
- Tính lại số đoạn và độ dài cho tới khi đánh số ổn định, gồm trường hợp 9 → 10 đoạn. Giới hạn nội bộ đề xuất tối đa 20 đoạn/biến thể.
- Nếu không chia được mà vẫn giữ nghĩa/nguồn, báo rõ đoạn cần người dùng viết ngắn lại. Không tự xóa nội dung để làm bộ đếm đạt.
- Preview mô tả văn bản cuối, không tuyên bố mô phỏng chính xác bố cục giao diện Facebook/Threads/X.
- Sao chép từng đoạn; tải `.txt` UTF-8 có ranh giới đoạn rõ. Tiêu đề kỹ thuật/metadata của file không được vô tình đưa vào nút copy bài.
- Khi chính sách nền tảng thay đổi: bản chưa đăng cần kiểm tra/duyệt lại; bản đã ghi nhận giữ snapshot cũ và thông tin chính sách thời điểm duyệt.

### 4.6. Duyệt và nhật ký đăng

- Duyệt theo biến thể, không một nút duyệt chung cả ba nền tảng.
- Chặn khi mục được sử dụng chưa biên tập/thiếu nguồn, còn cờ chưa kiểm chứng, thiếu đích đăng, thiếu checklist, đoạn trống hoặc vượt giới hạn.
- Hash bao gồm đầu ra chính xác theo thứ tự, nền tảng, đích, nguồn/snapshot liên quan, checklist, revision bản tin, phiên bản renderer và chính sách đầu ra.
- Sửa một biến thể chỉ hủy duyệt biến thể đó. Sửa bản tin gốc làm tất cả biến thể chưa ghi nhận đăng bị đánh dấu cần cập nhật/duyệt lại; không tự ghi đè nội dung của chúng.
- Các biến thể đã ghi nhận ít nhất một đoạn bị khóa toàn bộ đầu ra; sửa tiếp phải tạo bản sao chưa duyệt. Cho tiếp tục ghi các đoạn còn lại của snapshot đã khóa.
- Khóa nội dung là mốc bất biến `locked_at`/`ever_recorded`, độc lập số URL đang có hiệu lực. Hủy/đính chính toàn bộ lượt ghi nhận không mở khóa nội dung để sửa lại.
- Khi bản tin gốc hoặc policy thay đổi sau khi đã ghi nhận một phần: ghi URL cho bài người dùng đã đăng vẫn đối chiếu snapshot đã khóa, không đối chiếu nội dung cha hiện tại. Trước khi tiếp tục xuất đoạn chưa đăng, kiểm tra policy hiện hành; không còn phù hợp thì yêu cầu tạo bản sao/chỉnh/duyệt lại. Không sửa snapshot cũ để làm nó vừa giới hạn mới.
- Tách xem/tải snapshot lưu trữ khỏi xuất dưới nhãn “sẵn sàng đăng”. Bản lưu trữ có nhãn lịch sử và policy thời điểm duyệt; không được dùng đường lưu trữ để vượt cổng kiểm tra của đầu ra mới.
- Không lấy trạng thái của Facebook làm trạng thái đăng của Threads/X. Trạng thái tổng hợp của bản tin là thông tin suy ra, không là cổng chặn mọi kênh.
- Với chuỗi bài, lưu URL từng đoạn và thời gian người dùng khai báo; phân biệt chưa ghi nhận / đã ghi nhận một phần / đã ghi nhận đủ. URL đoạn đầu là liên kết đại diện.
- URL phải đúng HTTPS, hostname và hình dạng bài đăng của nền tảng; chống tên miền giả dạng, credentials, URL trang chủ/profile. Không truy cập URL để tự xác minh.
- Xác minh và ghi tài liệu các dạng URL thực tế trước khi viết allowlist; hỗ trợ alias chính thức đã kiểm tra, không chỉ kiểm tra chuỗi chứa `facebook`/`threads`/`x`.
- Yêu cầu ghi nhận có khóa chống lặp; cùng khóa và payload trả lại kết quả cũ, cùng khóa nhưng payload khác phải conflict. URL chuẩn hóa đang có hiệu lực chỉ thuộc một đoạn/lượt ghi nhận; trùng giữa các đoạn hoặc biến thể phải bị chặn kèm liên kết tới bản ghi cũ.
- Nếu nhập sai URL: thêm sự kiện đính chính/hủy ghi nhận có lý do, không sửa/xóa bằng chứng lịch sử. Không tuyên bố việc này xóa hoặc chỉnh bài ngoài nền tảng.
- Đính chính/hủy giải phóng quyền gắn URL cũ đang có hiệu lực nhưng giữ nguyên lịch sử; URL thay thế phải chưa được bản khác sử dụng. Kiểm tra cả URL legacy ở lớp đọc/overlay, không ghi lại bảng cũ. Nếu legacy đã có trùng, hiển thị để đối soát, không tự xóa hoặc làm migration thất bại.
- Số liệu gắn với lượt đăng, có `observed_at`; số chưa biết là `null`, không tự điền `0`. Nhãn chỉ số riêng nền tảng; không bắt X phải có cùng chỉ số với Facebook.
- Dashboard tách số bản tin gốc, số biến thể và số bài/đoạn đã ghi nhận; không tính một bản tin đăng ba kênh là ba bản tin nguyên bản.

## 5. Thiết kế dữ liệu và tổ chức mã đề xuất

Tên dưới đây là hợp đồng thiết kế dự kiến, chưa phải bảng/module đã tồn tại.

| Bảng mới | Trách nhiệm chính | Ràng buộc |
| --- | --- | --- |
| `bulletins` | Tiêu đề, ngày biên tập, lời mở/kết, revision, thời điểm tạo/sửa | Không dùng một `published` chung cho mọi nền tảng |
| `bulletin_items` | Thứ tự, nội dung từng mục, article nguồn và snapshot/ghi chú/checklist | ID mục ổn định; nguồn nằm trong snapshot có ID riêng; article tham chiếu không thay thế snapshot |
| `content_variants` | Nền tảng, nhãn đích, nội dung/đoạn và liên kết mục/nguồn, revision bản tin gốc, revision riêng, `locked_at` | Không ghi đè biến thể từng ghi nhận; có trạng thái cần xem lại |
| `variant_approvals` | Snapshot đầu ra và tư liệu đã duyệt, hash, version renderer/policy, thời gian | Bất biến; phê duyệt mới tạo bản ghi mới |
| `publications` | Biến thể + approval + chỉ số đoạn, URL, thời gian, idempotency key | Khóa chống lặp; URL hiệu lực duy nhất; tham chiếu đúng snapshot chứ không nội dung đang sửa |
| `publication_events` | Ghi nhận/đính chính/hủy ghi nhận, lý do, liên kết bản ghi | Append-only; giữ lịch sử URL cũ |
| `publication_metrics` | Chỉ số quan sát, loại chỉ số, thời điểm, ghi chú | Theo publication; chấp nhận chưa có dữ liệu |
| `bulletin_history` | Sự kiện sửa mục/đổi thứ tự/tạo biến thể/hủy duyệt | Có entity ID + revision, không dựa vào state UI |

Giữ nguyên `drafts`, `history`, `metrics` và định dạng xuất legacy. Cung cấp thao tác **Tạo bản sao sang quy trình mới** khi cần; bản sao chưa duyệt, nguồn/bản cũ không bị sửa. Chưa cần tự chuyển mọi draft cũ thành bản tin nhiều mục.

Trạng thái tiến độ thông thường: `draft` → `approved` → `partially_recorded` → `recorded`; biến thể một đoạn chuyển thẳng từ approved sang recorded. Tách khóa nội dung bất biến khỏi tiến độ nhật ký hiện hành: đính chính có thể giảm số đoạn hiệu lực nhưng không được đưa nội dung đã khóa về draft có thể sửa. Approval cũ vẫn còn để kiểm toán, nhưng không còn đủ điều kiện cho lần xuất mới của nội dung đã sửa.

Tách module theo trách nhiệm, không viết toàn bộ tính năng vào `service.py`:

- `newsroom/migrations.py`: sở hữu phiên bản DB và nâng cấp có giao dịch.
- `newsroom/bulletins.py`: lưu bản tin/mục/snapshot và xung đột revision.
- `newsroom/variants.py`: nội dung từng nền tảng, quan hệ với bản tin gốc và duyệt.
- `newsroom/social_formats.py`: chính sách, renderer, validator và phân đoạn.
- `newsroom/publications.py`: nhật ký đăng, idempotency, đính chính và chỉ số.
- `newsroom/static/`: helper form/preview/selection có thể kiểm thử; giữ `app.js` làm điều phối giao diện.

Các mutation phải dùng revision và giao dịch phù hợp, kiểm tra lại dưới khóa. Bật/kiểm tra foreign key trên từng kết nối khi thêm ràng buộc; tránh cascade xóa lịch sử hoặc snapshot đã duyệt. Không đưa nguồn nội dung vào `innerHTML` hoặc thực thi HTML/JS do AI trả về.

### API nội bộ dự kiến

| Nhóm | Endpoint / thao tác dự kiến | Hợp đồng |
| --- | --- | --- |
| Bản tin | `POST /api/bulletins`, `GET /api/bulletins/:id` | Tạo từ danh sách article đã chọn; trả snapshot có revision |
| Mục | `POST /api/bulletins/:id/items`, `POST /api/bulletins/:id/reorder` | Lưu/thêm/bỏ có kiểm soát, thứ tự không trùng hoặc mất mục |
| Tư liệu | `GET /api/bulletins/:id/packet` | Chỉ trả gói văn bản; không gọi model |
| Biến thể | `POST /api/bulletins/:id/variants`, `POST /api/variants/:id/save` | Không ghi đè biến thể khác, revision bắt buộc |
| Preview | `POST /api/variants/:id/preview` | Tính đầu ra không lưu/duyệt; trả counts, lỗi và policy version |
| Duyệt/xuất | `POST /api/variants/:id/approve`, `GET /api/variants/:id/export` | Kiểm tra hash và nội dung chính xác; không xuất bản chưa duyệt như bản sẵn đăng |
| Nhật ký | `POST /api/variants/:id/publications` | Chỉ ghi nhận lời xác nhận thủ công; không publish ra mạng |
| Đính chính | `POST /api/publications/:id/corrections` | Ghi sự kiện, lý do, không viết lại lịch sử |
| Chỉ số | `POST /api/publications/:id/metrics` | Quan sát thủ công, kiểm tra kiểu/range/thời điểm |

Chốt chi tiết request/response và mã lỗi bằng test hợp đồng trước code UI. Tất cả endpoint giữ session/CSRF/Origin/Host, giới hạn kích thước và xử lý conflict hiện có. Không đưa toàn bộ snapshot vào `/api/state`; trả tóm tắt và tải chi tiết theo ID để tránh state tăng vô hạn.

## 6. Migration, backup và rollback — cổng bắt buộc

Rủi ro hiện có cần xử lý trước khi thêm schema 4:

- `Newsroom.__init__` chỉ chấp nhận phiên bản DB 0/1/2/3.
- `CollectionMixin.init_collection()` hiện chạy `PRAGMA user_version=3`; nếu không tách, khởi động có thể ghi sai mốc schema mới.
- `restore()` cũng chỉ nhận schema 1/2/3.
- Không giả định `executescript()` nằm trong transaction hiện tại là tự động atomic; thiết kế transaction phải rõ và có test lỗi giữa các bước.

Quy trình đề xuất:

1. Có một migration runner sở hữu version; các mixin không tự ghi `user_version`.
2. Với DB cũ: backup bằng SQLite backup API, kiểm tra integrity và đóng handle trước khi thay đổi schema. Backup lỗi thì dừng nâng cấp.
3. Thực hiện thay đổi cần thiết trong transaction rõ ràng; đặt schema version cuối cùng. Lỗi thì rollback, không tiếp tục mở app như đã thành công.
4. Giữ nguyên từng byte payload/hash/export, revision, status, lịch sử, URL và metrics legacy; không tự duyệt lại, không bật nguồn, không chạy collection/model trong migration.
5. Bao phủ DB mới và các đường 1/2/3 → 4. DB có version mới hơn ứng dụng phải bị từ chối rõ ràng, không sửa hoặc hạ version.
6. Khởi động lại schema 4 không lặp backfill, không tạo bản sao dữ liệu hoặc backup migration liên tục.
7. Restore cho schema 4 kiểm tra bảng/ràng buộc cần thiết; đích luôn là thư mục mới ngoài OneDrive, không ghi đè DB chính.
8. Rollback phần mềm: dừng app, phục hồi backup trước nâng cấp vào thư mục mới và chạy mã phù hợp schema đó. Không hạ schema trực tiếp, không chạy code cũ trên DB 4.
9. Backup trước nâng cấp không chứa công việc phát sinh sau nâng cấp; trước rollback phải giữ riêng DB 4 và bản xuất mới. Không hứa rollback tự hợp nhất dữ liệu mới vào schema cũ.

Chỉ thử migration trên fixture và bản sao được phép trước. Chuyển sang dữ liệu vận hành cần một bước triển khai riêng: người dùng lưu bài, dừng phiên cũ, có backup đã kiểm tra và biết đường dẫn phục hồi.

## 7. Backlog theo giai đoạn

Ưu tiên: **P0** = bảo toàn dữ liệu/đúng bản duyệt; **P1** = cần cho bản 0.4; **P2** = cải thiện sau lõi. Đây là thứ tự triển khai, không phải nhãn mức độ lỗi của mọi tính năng còn thiếu.

Quy mô S/M/L là tương đối, không phải cam kết số ngày. Mặc định mọi checkbox triển khai còn trống. Người thực hiện cập nhật ID task, trạng thái, commit và bằng chứng; không đánh dấu xong chỉ vì đã viết code.

| Giai đoạn | Đầu ra | Phụ thuộc | Quy mô | Trạng thái |
| --- | --- | --- | --- | --- |
| G0 | Hotfix URL, có thể phát hành 0.3.1 riêng | Không | S | Đang làm — chờ smoke trình duyệt |
| G1 | Hợp đồng dữ liệu, policy và migration an toàn | Review kế hoạch | M | Đang làm |
| G2 | Bản tin nhiều mục + nguồn + gói tư liệu | G1 | L | Đang làm — chưa QA giao diện |
| G3 | Ba biến thể, preview, đếm/chia đoạn | G1, G2 | L | Đang làm — còn kiểm chứng bộ đếm và QA chia đoạn |
| G4 | Duyệt/xuất đúng snapshot | G2, G3 | M | Đang làm — chưa QA toàn luồng |
| G5 | Nhật ký đa kênh, chống lặp, chỉ số | G0, G4 | M | Đang làm — còn giao diện và QA |
| G6 | Hồi quy, QA Windows, tài liệu và pilot | G0–G5 | M | Đang làm — chưa đủ bằng chứng nghiệm thu |

### G0 — Hotfix URL

- [x] **FIX-01 / P0:** Viết test tái hiện URL A tràn sang B, cả trường hợp đã ghi nhận và đang nhập dở.
- [x] **FIX-02 / P0:** Bind/reset trường URL theo draft; hiển thị đúng đường dẫn đã lưu, bổ sung xác nhận có ngữ cảnh.
- [ ] **FIX-03 / P0:** Chạy hồi quy backend + test JS + smoke thật trên dữ liệu thử; cập nhật bằng chứng 0.3.1.

Gate: URL-01…04 tại mục 8 đạt, không migration, bản xuất legacy không đổi.

### G1 — Hợp đồng và nền dữ liệu

- [x] **BASE-01 / P0:** Chụp fixture legacy gồm draft/approved/published, history, metrics và nguồn tùy chỉnh; lưu expected hash/export để đối chiếu. Fixture tổng hợp được tạo bằng mã schema 3 tại commit nền `a180354`; test so sánh từng hàng và bản xuất sau nâng cấp.
- [ ] **BASE-02 / P1:** Chốt D02/D03, kiểu dữ liệu, trạng thái, hợp đồng API và giới hạn request/packet; ghi quyết định tại mục 12.
- [ ] **BASE-03 / P1:** Khảo sát bộ đếm X/Threads và URL từng nền tảng; chọn triển khai/licensing/dependency, lưu fixture có version.
- [ ] **DB-01 / P0:** Tách migration runner, bỏ quyền ghi schema version khỏi mixin; thêm schema 4 và ràng buộc.
- [ ] **DB-02 / P0:** Backup/restore/rollback và fault injection, startup idempotent, từ chối schema tương lai.

Gate: MIG-01…05 đạt; không làm thay đổi dữ liệu legacy; policy chưa rõ phải được ghi là chưa đóng.

### G2 — Bản tin tổng hợp

- [ ] **DIG-01 / P1:** UI chọn nhiều tin, giữ lựa chọn khi lọc, đếm và giới hạn lựa chọn.
- [ ] **DIG-02 / P1:** CRUD bản tin/mục, thứ tự, snapshot nguồn, revision và lịch sử.
- [ ] **DIG-03 / P1:** Cảnh báo tuổi tin/trích đoạn, ghi chú kiểm chứng riêng, nguồn theo từng mục.
- [ ] **DIG-04 / P1:** Gói tư liệu nhiều mục và biểu mẫu nhập lại kết quả; hoạt động khi không dùng AI.

Gate: NEWS-01…06 và SOURCE-01…03 đạt; chưa tuyên bố đầu ra đa kênh hoàn chỉnh ở giai đoạn này.

### G3 — Đầu ra từng nền tảng

- [ ] **FMT-01 / P1:** Tạo/lưu độc lập các biến thể, đích đăng và quan hệ với revision bản tin; không ghi đè bản đã sửa.
- [ ] **FMT-02 / P1:** Renderer chuẩn phía server và bộ đếm theo policy đã xác minh; UI preview chính chuỗi trả về.
- [ ] **FMT-03 / P1:** Chia chuỗi theo ranh giới hợp lý, kiểm tra lại numbering/nguồn; trường hợp khó yêu cầu biên tập thủ công.
- [ ] **FMT-04 / P1:** Xem/sửa từng đoạn, báo mục bị lược khỏi phiên bản ngắn; bảo đảm truy vết nguồn.

Gate: VAR-01…04, TEXT-01…06 đạt; không dùng độ dài body làm bằng chứng bài vừa giới hạn.

### G4 — Duyệt và xuất

- [ ] **APR-01 / P0:** Approval snapshot/hash/version, checklist theo mục và biến thể, block các trạng thái chưa đủ điều kiện.
- [ ] **APR-02 / P0:** Vô hiệu duyệt đúng phạm vi khi sửa nội dung/nguồn/đích/thứ tự/policy; giữ snapshot đã ghi nhận.
- [ ] **APR-03 / P1:** Copy từng đoạn, `.txt` UTF-8, fallback thủ công; export chỉ từ snapshot hợp lệ.
- [ ] **APR-04 / P0:** Bảo vệ conflict/race: sửa khi đang duyệt/xuất/ghi nhận không tạo hash hoặc nhật ký sai.

Gate: APPROVE-01…06 đạt; preview/copy/file/approval tương đương chính xác ở cấp đoạn văn bản.

### G5 — Nhật ký đa kênh

- [ ] **PUB-01 / P1:** URL validator theo nền tảng và từng đoạn, nhãn đích rõ ràng, trạng thái ghi nhận một phần.
- [ ] **PUB-02 / P0:** Idempotency, chống URL trùng giữa biến thể và khóa snapshot từ lần ghi nhận đầu tiên.
- [ ] **PUB-03 / P1:** Đính chính có lịch sử; không lẫn URL khi chuyển bài/kênh/đoạn.
- [ ] **PUB-04 / P1:** Chỉ số theo publication với thời điểm quan sát và `null` khi chưa biết; thống kê bản tin/lượt đăng tách biệt.

Gate: POST-01…06 đạt; không phát sinh request đăng bài hoặc gọi tài khoản mạng xã hội.

### G6 — Nghiệm thu và tài liệu

- [ ] **QA-01 / P0:** Toàn bộ kiểm thử cũ + mới đạt; không xóa/nới test an toàn để làm bản mới pass.
- [ ] **QA-02 / P1:** QA giao diện Windows trên kho thử: bàn phím, đổi tab, chưa lưu, clipboard/fallback, file UTF-8, restart.
- [ ] **QA-03 / P0:** Migration/restore end-to-end trên fixture và bản sao được phép; xác nhận đường lui và dữ liệu sau nâng cấp.
- [ ] **DOC-01 / P1:** Cập nhật README, KIEN-TRUC, HUONG-DAN-SU-DUNG, KIEM-THU; ghi rõ giới hạn theo nền tảng và nội dung chưa thử.
- [x] **PILOT-01 / P1:** Làm ít nhất ba bản tin thử với số mục/ngôn ngữ/độ dài khác nhau; ghi thời gian thao tác và vấn đề, không tự đăng công khai. Ba lượt dùng kho demo tạm và trình duyệt tích hợp; chi tiết và giới hạn tại `KIEM-THU.md`.
- [ ] **REL-01 / P0:** Chốt checklist mục 10, tổng hợp bằng chứng và phần chưa kiểm chứng trước khi đề nghị triển khai bản chính.

## 8. Ma trận kiểm thử bắt buộc

| ID | Tình huống | Kết quả bắt buộc |
| --- | --- | --- |
| URL-01 | Ghi URL A, ghi nhận A, mở B đã duyệt | B có ô URL rỗng |
| URL-02 | URL A nhập dở, chuyển B sau xác nhận | Không mang URL A sang B; không ghi nhận tự động |
| URL-03 | Quay lại A đã ghi nhận | Hiển thị URL đã lưu của A, không sửa bản ghi |
| URL-04 | URL thiếu/sai | Server từ chối; không đổi trạng thái/số lượt đăng |
| MIG-01 | DB mới và schema 1/2/3 → 4 | Đúng schema, integrity; payload/hash/export/history/metrics cũ không đổi |
| MIG-02 | Backup lỗi / lỗi giữa migration | Dừng an toàn, không schema nửa chừng, có đường phục hồi |
| MIG-03 | Khởi động schema 4 hai lần | Không hạ version, không backfill/trùng dữ liệu |
| MIG-04 | Restore schema 4, đích có sẵn, DB hỏng | Chỉ restore hợp lệ vào thư mục mới; không ghi đè |
| MIG-05 | DB version cao hơn mã đang chạy | Từ chối rõ ràng, không sửa DB |
| NEWS-01 | 0, 1, 2, 10, 11 mục; clone bài cũ; ID trùng/không tồn tại | 1–10 hợp lệ, clone một mục chưa duyệt; lỗi không lưu một phần |
| NEWS-02 | Chọn rồi lọc/tìm kiếm/chuyển nhóm | Giữ lựa chọn, cho biết cả mục đang ẩn |
| NEWS-03 | Thứ tự C → A → B, restart | Lưu/prompt/preview giữ đúng thứ tự |
| NEWS-04 | Bỏ mục dùng chung URL nguồn | Không mất nguồn của mục còn lại |
| NEWS-05 | Ngày UTC sát nửa đêm Việt Nam; unknown/future | Phân loại đúng, không giả ngày mới |
| NEWS-06 | Request/packet đúng ngưỡng và vượt ngưỡng UTF-8 | Không truncate âm thầm, không ghi một phần |
| SOURCE-01 | Refresh nguồn sau khi tạo/duyệt | Snapshot không thay âm thầm |
| SOURCE-02 | Sửa ghi chú hoặc trích đoạn | Tách ghi chú; bản sửa không mang hash xuất xứ giả |
| SOURCE-03 | Trích đoạn ngắn, nguồn có HTML/script/chỉ dẫn AI | Cảnh báo đúng; dữ liệu không được thực thi hoặc biến thành chỉ dẫn |
| VAR-01 | Sửa Facebook | Threads/X và revision của chúng không đổi |
| VAR-02 | Tạo lại biến thể đã chỉnh | Không ghi đè khi chưa xác nhận; có cách giữ bản cũ |
| VAR-03 | Sửa bản tin khi Facebook đã ghi nhận, Threads chưa đăng | Snapshot Facebook giữ nguyên; Threads cần cập nhật/duyệt lại |
| VAR-04 | Hai tab lưu cùng revision | Một lần thành công, lần cũ báo conflict |
| TEXT-01 | Preview/copy/file/approval | Cùng chuỗi cuối ở từng đoạn, gồm nguồn và đánh số |
| TEXT-02 | Đúng giới hạn và vượt một đơn vị | Đạt/chặn đúng, gồm trường hợp body ngắn nhưng thêm nguồn bị quá |
| TEXT-03 | Tiếng Việt NFC/NFD, emoji ZWJ, CJK, URL dài | Khớp fixture policy, không dựa `String.length` |
| TEXT-04 | Chia đoạn/câu và URL | Không mất/lặp nội dung, không đứt URL/cụm ký tự, mọi đoạn hợp lệ |
| TEXT-05 | Từ 9 sang 10 đoạn, quá 20 đoạn, không thể chia | Tính lại đúng; báo yêu cầu sửa, không cắt bỏ nguồn |
| TEXT-06 | Thay version policy/renderer | Bản chưa đăng phải kiểm tra lại; lịch sử đã ghi nhận giữ nguyên |
| APPROVE-01 | Thiếu nguồn, cờ chưa kiểm chứng, đoạn trống/quá dài | Không được duyệt/xuất như bài sẵn đăng |
| APPROVE-02 | Sửa nguồn/đích/thứ tự/nội dung | Hủy duyệt đúng phạm vi và reset kiểm tra phù hợp |
| APPROVE-03 | Gọi export chưa duyệt / hash không khớp | Fail closed, không trả văn bản dưới nhãn đã duyệt |
| APPROVE-04 | Đã ghi nhận một đoạn rồi sửa nội dung | Khóa toàn biến thể; tạo bản sao nếu cần sửa |
| APPROVE-05 | Race save/approve/export/record | Không ghi sai snapshot hoặc mất cập nhật |
| APPROVE-06 | Ghi nhận 1/N đoạn rồi sửa bản tin/policy | Lưu URL đã đăng theo snapshot khóa; xuất tiếp kiểm tra policy mới; bản lưu trữ có nhãn riêng |
| POST-01 | Ba kênh, nhiều đoạn, đăng một phần | URL/thời gian/snapshot tách đúng; hoàn tất khi đủ đoạn |
| POST-02 | URL khác kênh, domain giả, profile/home, credentials | Từ chối; không fetch để xác minh |
| POST-03 | Bấm đúp, retry cùng key, key trùng/payload khác, URL trùng đoạn/biến thể/legacy | Idempotent hoặc conflict đúng; không tăng đếm sai; legacy trùng không làm hỏng migration |
| POST-04 | Đổi draft/kênh/đoạn khi đang nhập URL | Không tràn URL; đúng cảnh báo chưa lưu |
| POST-05 | Đính chính URL; hủy hết lượt ghi nhận; gắn lại URL đã giải phóng | Giữ lịch sử, chỉ URL hiệu lực là duy nhất; nội dung vẫn khóa dù tiến độ về 0 |
| POST-06 | Chỉ số chưa có / số 0 / sai kiểu / sai publication | Phân biệt null/0; validate; thống kê tách bản tin và bài đăng |
| SAFE-01 | Tất cả mutation mới không session/CSRF/Origin hợp lệ | Bị từ chối như API hiện có |
| SAFE-02 | Nâng cấp/tạo bản tin/preview/ghi nhận | Không bật nguồn, chạy AI, gửi mạng xã hội hoặc thay DB khác |
| SAFE-03 | Thêm module JS/static mới | Chỉ phục vụ file hợp lệ; giữ CSP/Host/traversal protections |

Phương án thực thi:

- Python `unittest`: persistence, migration, policy/rendering, snapshot/hash, conflict, API và bảo mật.
- Node `node:test` + `node:assert/strict`: selection, binding form, trạng thái chưa lưu, thao tác đổi kênh và hiển thị đầu ra. Tách helper có giao diện ổn định; không duy trì test bằng cách cắt hàm từ source theo chuỗi.
- Fixture chung cho văn bản phức tạp và các chuỗi kỳ vọng. Nếu frontend cũng có bộ đếm, phải chạy cùng fixture và khớp server.
- Smoke trình duyệt thật không thay bằng DOM stub: chọn/đổi thứ tự bằng bàn phím, đổi kênh, lưu/reload, download, dán clipboard sang ứng dụng khác bằng dữ liệu thử.
- Không cần đăng công khai để nghiệm thu nội bộ. Kiểm tra trên tài khoản thật là bước riêng do người dùng quyết định.

Lệnh baseline hiện có:

```powershell
rtk proxy python -B -m unittest discover -s tests -v
```

Khi các test JS đã được tạo, thêm lệnh chạy thư mục test JS thực tế vào README và tài liệu kiểm thử; không ghi một lệnh với đường dẫn chưa tồn tại như thể đã chạy thành công.

## 9. Rủi ro và cách kiểm soát

| Rủi ro | Cách xử lý / cổng chặn |
| --- | --- |
| Migration ghi sai version hoặc mất duyệt legacy | Runner tập trung, backup trước, transaction, expected byte/hash fixtures |
| Nhiều nguồn vượt request limit | Lưu theo mục, cap UTF-8, trả lỗi rõ; không tăng limit vô hạn |
| Rút ngắn làm sai nghĩa/bỏ nguồn | Người dùng biên tập; chia đoạn không tự tóm tắt; duyệt đầu ra cuối |
| Đếm ký tự sai hoặc luật nền tảng đổi | Policy version + nguồn/ngày kiểm tra + fixture và gate trước phát hành |
| Nguồn sửa nhưng snapshot cũ vẫn tồn tại | Hiển thị tuổi tư liệu, yêu cầu người dùng đối chiếu; không quảng cáo đã đồng bộ nguồn |
| Một kênh đã đăng, kênh khác còn chỉnh | Approval bất biến, state theo biến thể; clone khi sửa bản đã ghi nhận |
| Ghi nhầm/ghi lặp URL | Binding theo ID, xác nhận có ngữ cảnh, idempotency, đính chính có lịch sử |
| Bộ test pass nhưng clipboard/Unicode thực tế lỗi | QA Windows và dán thử thật; có download/fallback |
| Scope trượt sang tài khoản/chi phí/tự đăng | Ghi ngoài phạm vi; cần quyết định riêng trước khi triển khai |

Các cải tiến để sau 0.4: tải lại nguồn web đã biết theo yêu cầu và so sánh thay đổi; gợi ý gom sự kiện; import kết quả AI có cấu trúc; ảnh có hồ sơ quyền; text attachment/bài dài; đồng bộ chỉ số; AI tích hợp hoặc đăng tự động. Chưa hứa triển khai, chưa gán ngày và không tự mở quyền cho các mục này.

## 10. Định nghĩa hoàn thành bản 0.4

Đối chiếu từng điều kiện với bằng chứng và phần còn thiếu tại [DOI-CHIEU-NGHIEM-THU-0.4.md](DOI-CHIEU-NGHIEM-THU-0.4.md); các ô dưới đây chỉ được đánh dấu sau khi đủ bằng chứng tương ứng.

- [x] Tạo được bản tin từ ít nhất ba bài nguồn, giữ thứ tự và truy vết nguồn từng mục qua restart. Đã kiểm tra với dữ liệu giả và bản sao khôi phục; xem `KIEM-THU.md`.
- [ ] Biên tập được hoàn toàn thủ công hoặc qua gói tư liệu AI thủ công, không phát sinh model call.
- [ ] Tạo được ba biến thể độc lập; có thể chỉ chọn một kênh để sử dụng.
- [ ] Văn bản cuối, bộ đếm, preview, copy, `.txt` và approval khớp nhau; không mất nguồn khi chia chuỗi.
- [ ] Sửa đúng phạm vi hủy duyệt; bài đã ghi nhận bất biến; ghi nhận một phần được xử lý rõ.
- [ ] Lưu riêng URL và số liệu từng kênh/đoạn; không còn lỗi URL bị giữ từ bản khác.
- [ ] Legacy giữ nguyên nội dung/hash/export/history; migration và restore schema 4 đạt kiểm thử lỗi.
- [ ] Các test hiện có và mới đạt; có bằng chứng QA trình duyệt/clipboard, không chỉ thông báo từ nút copy.
- [ ] README/hướng dẫn/kiến trúc/kiểm thử cập nhật, phần chưa kiểm chứng được ghi rõ.
- [ ] Người dùng đã xem kết quả pilot và quyết định triển khai lên kho dữ liệu vận hành.

Không dùng các tuyên bố “đã đăng thật”, “đã xác minh nội dung”, “đủ quyền kiếm tiền” hoặc “sẵn sàng tự động hoàn toàn” để mô tả việc hoàn thành checklist này.

## 11. Theo dõi tiến độ và bằng chứng

Trạng thái dùng thống nhất: `Chưa bắt đầu` / `Đang làm` / `Chờ quyết định` / `Chờ kiểm thử` / `Hoàn tất`.

| Ngày | Task/mốc | Trạng thái | Bằng chứng / commit / người thực hiện | Bước tiếp theo |
| --- | --- | --- | --- | --- |
| 03/11/2026 | Review hiện trạng | Hoàn tất | Commit nền `a180354`; 88/88 test; probe RSS chỉ đọc; tái hiện URL bằng DOM giả | Giữ làm baseline, không coi là nghiệm thu 0.4 |
| 03/11/2026 | Lập kế hoạch nâng cấp | Hoàn tất | Tài liệu này; chưa triển khai chức năng | Xem/chốt phạm vi rồi bắt đầu G0 |
| 03/11/2026 | FIX-01…03 | Đang làm | Test JS binding và smoke kho thử: URL A không tràn sang B trước/sau ghi nhận, A hiện đúng link; nhánh hủy giữ URL B. Test service từ chối URL rỗng/sai, không đổi draft, history và thống kê | Đối chiếu gate export legacy và kiểm tra lỗi URL trên giao diện |
| 03/11/2026 | BASE/DB | Đang làm | Migration schema 4, rollback/restore và lỗi sao lưu; fixture tổng hợp từ mã schema 3 gồm ba trạng thái, history, metrics, custom source và bản xuất được đối chiếu | Kiểm thử thêm schema 1/2, backup/restore đầu cuối và trên bản sao được phép |
| 03/11/2026 | DIG/FMT/APR/PUB | Đang làm | Có lõi, giao diện, test chia đoạn 9→10 và test HTTP CSRF; đã smoke một bản tin/phiên bản X với URL giả trên kho thử | Kiểm chứng bộ đếm, QA toàn luồng, clipboard, file tải, restart và thêm pilot |
| 03/11/2026 | DIG-03 | Đang làm | Thêm cảnh báo nguồn thiếu/ngắn và ngày không rõ/tương lai/quá 7 ngày, kèm test ngưỡng JS | Smoke giao diện và đối chiếu các tiêu chí nguồn còn lại |
| 03/11/2026 | DIG-01/02 | Đang làm | Cảnh báo tin đã dùng, cho phép chọn lại; test backend và smoke tạo/thêm trên kho thử | Kiểm tra các tiêu chí chọn lọc, đồng thời và nguồn còn lại |
| 03/11/2026 | NEWS-06 | Đang làm | Bổ sung kiểm tra 128.000 byte UTF-8 ở UI trước gửi; test JSON đúng ngưỡng/vượt một byte và Unicode | Smoke lỗi request qua giao diện |
| 03/11/2026 | NEWS-02/05/06 | Đang làm | Thêm xóa lựa chọn, đếm tin đã chọn đang ẩn, lọc số ngày tùy chọn và nhãn loại ngày; smoke trên kho thử. Packet tính cả hướng dẫn trong 64 KiB và chỉ ra mục lớn, test biên Unicode | Bổ sung kiểm tra UI ngày tương lai/unknown và smoke lỗi packet |
| 03/11/2026 | FMT-01/APR-02 | Đang làm | Sửa mất nội dung khi clone bản có mục đã bị bỏ: giữ các đoạn, không tự gán nguồn thay thế, yêu cầu kiểm tra; test mất mục/nguồn và smoke trên kho thử | Tiếp tục kiểm tra các trường hợp thay đổi policy và đối chiếu nguồn |
| 03/11/2026 | APPROVE-06 | Đang làm | Phiên bản đã khóa hiển thị mục, nguồn và preview từ snapshot đã kiểm tra hash; test backend và smoke bản gốc đã bỏ mục trên kho thử | Kiểm tra thêm thay đổi policy trong giao diện và tình huống nhiều đoạn |
| 03/11/2026 | PUB-02 / POST-03 | Đang làm | Sửa kiểm tra trùng URL theo cả hai chiều legacy/đa kênh trong giao dịch; test alias và hai thao tác đồng thời cùng URL | URL legacy có dạng chưa được validator nhận diện vẫn chưa thể đối chiếu trùng; cần chốt policy URL |
| 03/11/2026 | QA-02 / PILOT-01 | Đang làm | Kho thử hai mục tái hiện cờ chưa lưu không xóa khi hoàn nguyên; đã sửa và thử lại trên trình duyệt, test JS text/checkbox | Chưa hỗ trợ lưu đồng thời nhiều phần; lượt thử bị gián đoạn nên không tính pilot hoàn chỉnh |
| 03/11/2026 | FMT/APR/QA/PILOT | Đang làm | Từ bản hai mục đã soạn sẵn, tạo và duyệt ba kênh; tải `.txt` X hai đoạn và đối chiếu nội dung, số thứ tự, nguồn. Thời gian phần tiếp tục 127,3 giây; URL giả ở hai đoạn được chặn ghi khi còn ô khác đang nhập | Không tính thời gian này là pilot đầu cuối; cần kiểm tra tiếp kết quả ghi nhận và ba pilot đầy đủ |
| 03/11/2026 | APR-04 / APPROVE-05 | Đang làm | Xem trước và xuất đọc phiên bản, bản tin, bản duyệt trong cùng snapshot SQLite; test WAL xen kẽ ghi cho thấy kết quả nhất quán theo thời điểm bắt đầu đọc | Cần bao phủ các tổ hợp race HTTP/copy/ghi nhận còn lại |
| 03/11/2026 | APR-02 / TEXT-06 | Đang làm | Sửa checklist chưa đăng không bị xóa khi bản tin gốc đổi; chặn tái duyệt bằng checklist cũ khi policy/renderer đổi, thêm cảnh báo UI. Test service giữ nguyên bản đã ghi nhận | Smoke UI khi đổi policy và các tổ hợp nguồn/thứ tự còn lại |
| 03/11/2026 | DIG-03 / APR-01 | Đang làm | Thêm checklist tối đa 10 khẳng định/mục, ghi nguồn hoặc lý do và xác nhận riêng; chặn duyệt nếu thiếu/bỏ kiểm tra. Test lưu/restart, sửa nội dung/nguồn và smoke nhập/lưu trên demo | Kiểm tra toàn luồng duyệt đa kênh và chuyển đổi bản đã duyệt policy cũ trên giao diện |
| 03/11/2026 | QA/DOC/PILOT/REL | Đang làm | Lần chạy gần nhất 144/144 Python, 10/10 JS; Edge tải `.txt` một đoạn và đối chiếu nội dung/nguồn; đã cập nhật tài liệu cho nhánh phát triển | Clipboard thật, QA còn lại, ba pilot và quyết định kho vận hành vẫn chưa có |
| 03/11/2026 | APR-01 / QA-02 | Đang làm | Edge tạo và duyệt Facebook từ mục có checklist khẳng định trên kho demo, dùng server thử khởi động theo policy v1; dữ liệu và xác nhận là giả | Cần thử các kênh khác; nút copy báo thành công nhưng clipboard của trình điều khiển rỗng, chưa chứng minh dán thực tế |
| 03/11/2026 | TEXT-06 / APR-02 | Đang làm | Edge mở lại biến thể Facebook v1 trên server v2: cảnh báo policy, chặn xuất sẵn sàng, lưu bỏ 5 xác nhận, xác nhận lại và duyệt v2 thành công | Chưa thử giao diện khi đã ghi nhận một phần; các xác nhận dùng dữ liệu giả |
| 03/11/2026 | TEXT-03 / SAFE-01 | Đang làm | HTTP trả lỗi Unicode rõ ràng và không lưu một phần với surrogate đơn lẻ; emoji hợp lệ lưu được. Sửa nhãn ước lượng Threads vì emoji U+1FAE8 được đếm 1 dù biểu diễn UTF-8 là 4 byte | Chưa biết quy tắc thực tế của Meta cho trường hợp này; bộ đếm và BASE-03 vẫn chưa nghiệm thu |
| 03/11/2026 | BASE-03 / TEXT-03 | Đang làm | Đã đối chiếu 7 chuỗi với `twitter-text` JavaScript 3.1.0: các kết quả khớp thư viện Python đang dùng, gồm một số emoji mới được tính hơn 2 | Tài liệu X mô tả emoji ghép trọng số 2; cần bằng chứng hành vi thực tế và giải pháp dữ liệu emoji cập nhật trước khi đóng gate |
| 03/11/2026 | BASE-03 / TEXT-03 | Đang làm | Cập nhật nhận diện X dùng emoji-test Unicode 15.1 có hash và giấy phép, tính 2 cho các chuỗi kiểm tra; 24 fixture cũ và biên 280/282 đạt. Policy v3 yêu cầu duyệt lại | Chưa xác minh nền tảng X thực tế, emoji sau 15.1, cách đếm Threads hoặc mọi mẫu URL; chưa đóng BASE-03 |
| 03/11/2026 | DB-02 / MIG-04 | Đang làm | Restore kiểm tra integrity bản đích; khi copy lỗi có kiểm soát, dọn DB dở và thư mục rỗng để thử lại, không xóa tệp khác trong thư mục | Chưa thử mất điện hoặc buộc kết thúc tiến trình; chưa nghiệm thu trên bản sao dữ liệu vận hành được phép |
| 03/11/2026 | DB-02 / MIG-04 | Đang làm | Restore dùng snapshot SQLite cho kiểm tra nguồn và sao chép; test WAL xen kẽ đổi nội dung và version nguồn sau kiểm tra vẫn khôi phục đúng snapshot được kiểm tra | Chưa bao phủ mọi lỗi hệ thống tập tin hoặc kho vận hành |
| 03/11/2026 | POST-05 | Đang làm | Hủy hết ghi nhận trả tiến độ 0/N, giữ khóa và sự kiện; đọc được trạng thái cũ và ghi lại URL đã giải phóng. Test policy đổi sau ghi một phần giữ snapshot lịch sử và chặn xuất mới. Smoke trình duyệt với dữ liệu chuẩn bị sẵn thấy 1/2, 0/2, khóa và lịch sử; 0/2 còn sau tải lại | Chưa thao tác hủy hoặc ghi lại URL qua giao diện, chưa thử đổi policy trên giao diện hoặc đăng thật |
| 03/11/2026 | FMT-03 / APR-04 | Đang làm | Đề xuất chia đoạn đọc revision và bản tin trong một snapshot; test WAL xen kẽ bỏ mục chứng minh kết quả nhất quán và lưu revision cũ bị chặn | Chưa thử cuộc đua bằng hai cửa sổ trình duyệt |
| 03/11/2026 | QA-02 / APR-04 | Đang làm | Khóa vùng biên tập, danh sách và điều hướng khi thao tác/chia đoạn đang chờ; test JS xác nhận phục hồi khi lỗi. Smoke trình duyệt với service giả chậm: vùng khóa khỏi cây tương tác, nhấn điều hướng không chuyển; sau xử lý, chuyển bản hiện cảnh báo chưa lưu | Chưa thử nhấn danh sách trong lúc chờ hoặc hai lựa chọn của cảnh báo; phiên điều khiển treo ở hộp xác nhận |
| 03/11/2026 | QA-02 | Đang làm | Mở bản tin từ danh sách dùng cùng khóa trong lúc chờ tải; test helper xác nhận khóa tới khi phản hồi hoàn tất | Chưa smoke request mở bản tin chậm trên trình duyệt |
| 03/11/2026 | BASE-03 / TEXT-02 | Đang làm | [Hướng dẫn X](https://help.x.com/en/using-twitter/how-to-tweet-a-link.html) xác nhận URL tính 23 ký tự; test URL ngắn/dài và biên 280/281 đạt | Chưa chứng minh mọi URL, emoji mới, cách đếm Threads hoặc hành vi nền tảng thực tế |
| 03/11/2026 | TEXT-03 / SAFE-01 | Đang làm | Mở rộng test HTTP cho high/low surrogate đơn lẻ trên cả ba kênh: trả 400, không đổi revision/nội dung, emoji hợp lệ lưu được | Chưa bao phủ mọi chuỗi Unicode hoặc cách tính trên nền tảng thật |
| 03/11/2026 | APR-03 / APR-04 | Đang làm | Nút copy đoạn kiểm tra lại export, đối chiếu ID duyệt và văn bản với nội dung đang hiển thị; từ chối nếu khác hoặc đang sửa chưa lưu. Smoke hai tab: sửa bản tin ở tab hai hủy duyệt; copy ở tab một báo không còn bản duyệt | Chưa thử duyệt lại và clipboard thật sau thay đổi; không loại bỏ thay đổi sau phản hồi export |
| 03/11/2026 | APR-03 / QA-02 | Đang làm | Smoke bản X hợp lệ sau sửa: nút copy báo thành công | Công cụ báo clipboard ảo không có dữ liệu khi thử dán; chưa xác nhận nội dung clipboard thực tế hoặc fallback từ chối quyền |
| 03/11/2026 | BASE-02 / NEWS-01 | Đang làm | Test kho giả xác nhận 10/11 mục, 3/4 nguồn mỗi mục và 20/21 URL khác nhau; URL dùng chung không tăng số URL, trường hợp bị từ chối không lưu dở, mở lại kho giữ dữ liệu | Chưa nghiệm thu mọi giới hạn qua giao diện hoặc hoàn tất hợp đồng API |
| 03/11/2026 | DIG-01 / QA-02 | Đang làm | Chụp danh sách ID một lần cho toàn lượt tạo bản tin; khóa thêm Hộp tin khi thao tác đang chờ và chỉ bỏ lựa chọn thuộc lượt tạo thành công. Smoke Edge trên kho tạm, service tạo chậm 35 giây: chọn tin B, thử chọn A trong lúc chờ, bản tin kết quả chỉ có B | Test helper và hồi quy đạt; chưa thử mọi đường lỗi và thao tác bàn phím trong lúc chờ |
| 03/11/2026 | NEWS-06 / BASE-02 | Đang làm | Test HTTP tạo bản tin bằng JSON UTF-8 đúng 128.000 byte trả 201; vượt một byte trả 413, không tạo thêm hoặc sửa bản tin. Bộ hồi quy 145/145 Python và 10/10 JS đạt | Đệm bằng trường không sử dụng; chưa smoke yêu cầu quá ngưỡng qua UI hoặc hoàn tất hợp đồng API |
| 03/11/2026 | BASE-02 / DOC-01 | Đang làm | Thêm bản đồ API đa kênh theo route và mã service hiện hành, gồm revision, giới hạn, ghi nhận và lỗi thường gặp | Chưa liệt kê đầy đủ schema phản hồi, mọi tổ hợp lỗi hoặc có xác nhận hợp đồng; chưa đóng BASE-02 |
| 03/11/2026 | SOURCE-03 | Đang làm | Smoke Edge kho tạm: tiêu đề nguồn dạng thẻ `img` hiện thành chữ, không có phần tử con, nguồn ngắn có cảnh báo. Test gói tư liệu giữ chỉ dẫn giả và dấu kết thúc giả trong JSON; 146/146 Python, 10/10 JS đạt | Chưa kiểm chứng mọi vị trí hiển thị và mọi HTML; phân cách không bảo đảm model bên ngoài bỏ qua chỉ dẫn |
| 03/11/2026 | APR-03 / QA-02 | Đang làm | Edge, kho tạm: server thử từ chối API clipboard bằng Permissions-Policy; hộp sao chép thủ công hiện đúng đoạn và hai nguồn, chọn toàn bộ; Ctrl+C/Ctrl+V vào ô khác cùng trang giữ đúng văn bản và xuống dòng | Chưa xác nhận clipboard API thành công hoặc dán sang ứng dụng khác; không đăng và không lưu ô thử |
| 03/11/2026 | APR-03 / QA-02 | Đang làm | Edge trên kho tạm với server bình thường: sao chép một đoạn X đã duyệt, dán vào ô thử trên trang và tab Notepad trống; nội dung, xuống dòng và hai URL nguồn khớp | Một trường hợp tiếng Việt, URL giả; chưa thử mọi trình duyệt/chuỗi hay toàn bộ QA. Không đăng, không lưu tệp |
| 03/11/2026 | DOC-01 / PILOT-01 | Đang làm | Cập nhật hướng dẫn tích hợp trong giao diện về tự viết/AI tùy chọn, Facebook/Threads/X, duyệt và tự đăng; nhãn 0.4 đang phát triển. Test HTTP và hồi quy 147/147 Python, 10/10 JS đạt | Điều khiển Edge không phản hồi khi mở kho thử; chưa smoke nội dung mới, chưa bắt đầu hoặc đo pilot |
| 03/11/2026 | BASE-03 / PUB-02 | Đang làm | Đối chiếu mã chuẩn hóa và so trùng URL, ghi tập host/đường dẫn hiện nhận trong `API-BAN-TIN-DA-KENH.md`; tài liệu X xác nhận cách lấy URL bài và minh họa một dạng URL | Chưa xác minh đầy đủ mẫu/alias nền tảng; các dạng Facebook khác nhau có thể trỏ cùng bài mà không bị nhận diện trùng, URL legacy ngoài validator không được đối chiếu. Cần đối soát thủ công và tiếp tục khảo sát; không đóng gate |
| 03/11/2026 | PILOT-01 | Đang làm | Kho demo tạm qua trình duyệt tích hợp: chọn, soạn, xác nhận giả lập, duyệt và tải tệp cho Facebook một mục tiếng Việt (56,9 giây), Threads hai mục tiếng Việt/Anh (56,7 giây); đọc lại tệp khớp văn bản và nguồn giả | Thời gian gồm điều khiển công cụ; chưa đủ ba pilot, chưa kiểm chứng nguồn thật hay quy tắc nền tảng, chưa kiểm thử X ở lượt này; xem `KIEM-THU.md` |
| 03/11/2026 | PILOT-01 | Hoàn tất phạm vi thử | Lượt thứ ba: kho demo mới, X ba mục tiếng Việt, đề xuất chia năm đoạn, duyệt và tải tệp; 87,0 giây, tệp khớp các đoạn hiển thị và nguồn giả | Cả ba nguồn được giữ trong mỗi đoạn, cần biên tập lại nếu không liên quan; thời gian gồm điều khiển công cụ. Đây không phải xác minh nền tảng thật hoặc nghiệm thu phát hành |
| 03/11/2026 | POST-04/05 / QA-02 | Đang làm | Kho fixture tạm: nhập URL X giả và bấm ghi nhận đoạn một; hộp xác nhận hiển thị đúng đoạn/kênh/URL. Đọc HTTP riêng thấy danh sách publication rỗng | Điều khiển bị kẹt tại hộp xác nhận; chưa ghi nhận thành công, chưa thử hủy/ghi lại hoặc reload ở lượt này |
| 03/11/2026 | BASE-02 / DOC-01 | Đang làm | Bổ sung cấu trúc phản hồi bản tin, phiên bản, preview, split, export, publication và thống kê theo mã hiện hành; chỉ rõ `payload`/`snapshot` là chuỗi JSON | Bản đồ tĩnh, chưa xác nhận mọi schema và tổ hợp lỗi qua HTTP; BASE-02 tiếp tục mở |
| 03/11/2026 | BASE-02 / QA-01 | Đang làm | Test HTTP kho tạm xác nhận một vòng đời hai đoạn, export/preview/archive, ghi nhận, số liệu, hủy và lịch sử; 16/16 test HTTP, 148/148 Python và 10/10 JS đạt | Fixture được chuẩn bị bằng service; không bao phủ mọi schema/lỗi, thao tác UI hay nền tảng thật; xem `KIEM-THU.md` |
| 03/11/2026 | PUB-02 / POST-03 | Đang làm | Thêm cảnh báo đối soát các nhóm URL trùng trong bài cũ bằng overlay chỉ đọc; test service/HTTP giữ nguyên dữ liệu, smoke kho giả hiện ID và URL; Python 150/150, JS 10/10 | Chỉ phát hiện mẫu nhận diện được hoặc cùng đường dẫn/query chuẩn hóa; chưa đóng policy URL, chưa thử trên bản sao vận hành được phép |
| 03/11/2026 | PUB-02 / POST-03 | Đang làm | Xung đột URL trả định danh bản tin, phiên bản, đoạn và lượt ghi nhận hoặc ID bài cũ; kiểm tra đính chính bị trùng hoàn tác thay đổi | Giao diện hiện chỉ hiện thông báo tạm, chưa có nút mở bản ghi đối soát; tiếp tục bảo vệ URL và nội dung chưa lưu khi điều hướng. Policy URL và QA vận hành vẫn mở |
| 03/11/2026 | PUB-02 / POST-03 | Đang làm | Thêm cảnh báo cố định và liên kết mở bản ghi xung đột trong thẻ mới cho ghi nhận, đính chính và bài cũ; kiểm tra đích trực tiếp trên kho giả | Chưa kiểm tra toàn bộ luồng nhấn ghi nhận qua hộp xác nhận; cần QA giao diện, policy URL và bản sao vận hành được phép |
| 03/11/2026 | FMT-03 / FMT-04 | Đang làm | Cảnh báo cạnh từng đoạn chọn nhiều mục, tự ẩn/hiện theo lựa chọn; thông báo chia đoạn nói rõ giữ mục và nguồn gốc. Kiểm tra trên kho giả và test đơn vị | Không suy đoán nguồn nào liên quan đến câu; người biên tập vẫn phải đối chiếu từng đoạn, QA bộ đếm và nền tảng còn mở |
| 03/11/2026 | SAFE-01 / QA-01 | Đang làm | Ma trận HTTP kiểm tra 14 route POST đa kênh với cookie, CSRF, Origin và Host sai/thiếu; xác nhận chặn trước handler và header hợp lệ đi đúng handler. Python 151/151, JS 12/12 | Route kiểm thử được liệt kê tường minh; phải bổ sung khi có route mới. Không thay thế QA giao diện và nghiệm thu vận hành |
| 03/11/2026 | FMT-02 / BASE-03 | Đang làm | Đặt cảnh báo giới hạn trực tiếp ở vùng phiên bản; thử hiển thị Threads trên kho giả và đối chiếu tài liệu Meta/X. Python 151/151, JS 13/13 | Threads vẫn là ước lượng; chưa xác minh mọi emoji hoặc tình trạng/tính năng tài khoản thực tế |
| 03/11/2026 | APR-03 / APPROVE-03 | Đang làm | Kiểm tra hash và cấu trúc snapshot trước khi dùng, lỗi rõ ràng khi JSON hỏng; test service/HTTP không ghi nhận hoặc xuất bản duyệt hỏng. Python 152/152, JS 13/13 | Cần QA giao diện và phục hồi trên bản sao vận hành được phép; không suy rộng cho mọi lỗi database |
| 03/11/2026 | QA-03 / NEWS-03 | Đang làm | Test liên thông trên kho giả: bản tin ba mục, ba kênh, một phần chuỗi X và số liệu qua backup/restore; đối chiếu thứ tự, nguồn, snapshot, trạng thái, lịch sử, export. Python 153/153, JS 13/13 | Cần bản sao dữ liệu vận hành được phép để thử migration/restore riêng; chưa thay thế QA giao diện |
| 03/11/2026 | QA-02 / NEWS-03 | Đang làm | Kho demo tạm: Space chọn ba tin, Enter tạo và đổi thứ tự; tải lại giữ thứ tự. Sửa nút đổi thứ tự có tên mục/hướng và giữ tiêu điểm tại mục vừa di chuyển, kể cả khi chạm đầu danh sách. Python 153/153, JS 14/14 | Chưa kiểm tra mọi thao tác bàn phím, trình đọc màn hình hay khởi động lại server trong lượt này; QA-02 vẫn mở |
| 03/11/2026 | PUB-03 / POST-05 | Đang làm | Giữ lý do và URL đính chính khi server báo lỗi, kể cả lỗi không có đích trùng; điền lại khi thử trên cùng trang và nhắc kiểm tra trạng thái. Python 153/153, JS 15/15 | Dữ liệu chưa lưu mất khi tải lại/chuyển phiên bản; công cụ trình duyệt bị gián đoạn tại hộp xác nhận, chưa thử trọn luồng giao diện |
| 03/11/2026 | PUB-03 / POST-04/05 | Đang làm | Đánh dấu phần đính chính đang nhập là chưa lưu, có nút bỏ; chặn các thao tác có thể ghi đè và dùng cảnh báo rời trang sẵn có. Python 153/153, JS 16/16 | Chưa smoke luồng prompt/cảnh báo trên trình duyệt; chấp nhận rời trang hoặc tải lại vẫn bỏ phần chưa lưu |
| 03/11/2026 | PUB-03 / POST-04/05 | Đang làm | Test handler thực tế với DOM/API giả: hủy nhập URL, cảnh báo rời trang, thử lại gặp lỗi và bỏ đính chính. Python 153/153, JS 17/17; cập nhật lệnh test trong README | Trình duyệt không phản hồi; chưa smoke hộp thoại và luồng đính chính thành công |
| 03/11/2026 | PUB-04 / POST-06 | Đang làm | Thêm số liệu trả lời/đăng lại/trích dẫn nhập tay; nhãn/tập trường theo kênh, giữ hiển thị số liệu cũ. Python 154/154, JS 18/18 | Chưa smoke UI hoặc xác minh số liệu trên tài khoản thật; không tự đồng bộ nền tảng |
| 03/11/2026 | PUB-04 / POST-06 / QA-03 | Đang làm | Test handler X bằng DOM/API giả, HTTP ghi/đọc và chặn giá trị sai, backup/restore các trường mới trên kho giả. Python 154/154, JS 19/19 | Chưa smoke UI trên trình duyệt hay kiểm thử bản sao vận hành |
| 03/11/2026 | PUB-04 / QA-02 | Đang làm | Giữ số liệu đang nhập khi hủy hoặc gặp lỗi, cảnh báo chưa lưu và có nút bỏ; test DOM/API giả, Python 154/154, JS 20/20 | Chưa smoke trình duyệt; lỗi kết nối có thể làm kết quả lưu không rõ, cần đối chiếu trước khi thử lại |
| 03/11/2026 | PUB-04 / QA-02 | Đang làm | Thêm key chống ghi trùng cho retry số liệu trong cùng trang; test đồng thời, xung đột, HTTP và handler giả; Python 155/155, JS 20/20 | Chưa smoke trình duyệt hoặc mất mạng thật; key mất sau tải lại, cần đối chiếu lịch sử khi kết quả không rõ |
| 03/11/2026 | QA-02 / BASE-03 | Đang làm | Chuẩn bị server fixture X hai đoạn; đối chiếu lại tài liệu chính thức X về giới hạn 280 và URL 23 ký tự, chi tiết tại `KIEM-THU.md` | Trình duyệt tích hợp timeout; Edge báo `GetCursorPos failed: Access is denied` sau lần thử khôi phục. Chưa thực hiện được luồng UI; chưa xác minh bộ đếm thực tế và Threads |
| 03/11/2026 | PUB-01/04 | Đang làm | Chuẩn hóa thời điểm ghi nhận và số liệu mới về UTC; retry cùng thời điểm từ offset khác và bản ghi cũ giữ nguyên hash/timestamp lịch sử; Python 156/156, JS 20/20 | Test fixture service và HTTP; chưa smoke múi giờ trên trình duyệt hoặc bản sao vận hành |
| 03/11/2026 | FMT-03 / TEXT-04 | Đang làm | Sửa đề xuất chia làm mất các dòng trống liên tiếp bên trong đoạn; kiểm thử không chia và chia hai đoạn; Python 157/157, JS 20/20 | Khoảng trắng ở ranh giới giữa các đoạn vẫn được cắt như trước; chưa smoke trình duyệt |
| 03/11/2026 | SOURCE-01/02 | Đang làm | Cập nhật URL không kèm evidence sẽ bỏ hash cũ ở nguồn hiện hành; snapshot bản tin đã lưu giữ nguyên. Test fixture API → RSS; Python 158/158, JS 20/20 | Không tự phát hiện hay sửa evidence/snapshot đã lưu trước sửa; chưa thử nguồn thật hoặc kho vận hành |
| 03/11/2026 | NEWS-04 | Đang làm | Test hai mục cùng URL: bỏ một mục, mở lại kho fixture, kiểm tra nguồn và ID mục còn lại trong dữ liệu, gói tư liệu và preview X; Python 159/159, JS 20/20 | Chưa thao tác qua giao diện hoặc thử mọi đường sửa nguồn |
| 03/11/2026 | SOURCE-01/02 / APR-01 | Đang làm | Chặn duyệt mới nếu SHA-256 trích đoạn không khớp hash của nguồn được dùng; test sai/đúng và nguồn không dùng, Python 160/160, JS 20/20 | Không tự rà soát bản duyệt đã có; hash khớp không chứng minh nguồn thật; chưa smoke giao diện |
| 03/11/2026 | SOURCE-02 | Đang làm | Thông báo hash không khớp chỉ rõ thứ tự mục và nguồn; bổ sung hướng dẫn đối chiếu và thay nguồn khi mục chỉ có một nguồn; Python 160/160, JS 20/20 | Chưa smoke thông báo qua giao diện |
| 03/11/2026 | MIG-04 / QA-03 | Đang làm | Restore schema 4 kiểm tra cột, FK, unique/index điều kiện và dữ liệu vi phạm FK trước khi tạo đích; fixture lỗi cấu trúc/mồ côi bị từ chối; Python 161/161, JS 20/20 | Schema 1–3 giữ kiểm tra cũ; chưa kiểm tra mọi payload hoặc thử bản sao vận hành được phép |
| 03/11/2026 | MIG-04 / QA-03 | Đang làm | Thêm kiểm tra bảng/cột legacy cần thiết trong backup schema 4; test restore từ fixture schema 3 và schema 1/2 mô phỏng đã nâng cấp giữ xuất legacy; Python 161/161, JS 20/20 | Không kiểm tra toàn bộ ràng buộc/payload legacy; chưa thử bản sao vận hành được phép |
| 03/11/2026 | BASE-03 / PUB-01/02 | Đang làm | Đối chiếu Meta Embeds và hỗ trợ Threads `/t/{shortcode}` cùng so trùng hai chiều với dạng đầy đủ; Python 162/162, JS 20/20 | Nguồn là tài liệu định dạng nhúng; chưa xác minh mọi alias hoặc tính duy nhất shortcode trên nền tảng thật |
| 03/11/2026 | POST-05 / BASE-03 | Đang làm | Test đính chính Threads giữa hai dạng URL: trùng cùng bài/bài khác, rollback, sửa, hủy và ghi lại; Python 163/163, JS 20/20 | Fixture service, chưa kiểm chứng shortcode thực tế hay luồng giao diện |
| 03/11/2026 | QA-02 / POST-04/06 | Đang làm | Trình duyệt tích hợp, kho fixture: URL giả chưa lưu của đoạn hai được giữ khi thử nhập số liệu đoạn một; ứng dụng chặn và hiện thông báo xử lý thay đổi trước | Chưa kiểm tra lưu số liệu qua hộp thoại, đổi kênh hoặc rời trang trong lượt này; QA-02 vẫn mở |
| 04/11/2026 | QA-02 / BASE-03 | Đang làm | Edge mở fixture X hai đoạn và thấy trạng thái 1/2; hồi quy 163 Python và 20 JS đạt; đối chiếu nguồn chính thức Meta/X tại `DOI-CHIEU-NGHIEM-THU-0.4.md` | Công cụ kẹt khi chuyển hộp nhập số liệu; chưa xác nhận lưu, đính chính hay toàn bộ QA. Bộ đếm và URL còn giới hạn đã ghi |
| 04/11/2026 | QA-02 / POST-04 | Đang làm | Mở lại trên thẻ trình duyệt tích hợp cùng server fixture thấy 2/2 và hai URL giả đúng đoạn | Đoạn 1 chuẩn bị bằng service; không xác định được thao tác xác nhận nào hoàn tất đoạn 2. Chưa thử restart server hoặc hoàn tất đính chính/số liệu |
| 04/11/2026 | FMT-01 / QA-02 | Đang làm | Trình duyệt tích hợp tạo, lưu hai bản nháp Facebook/Threads khác nội dung trên fixture; chuyển Facebook → Threads → X giữ nội dung riêng và hai URL X đúng đoạn. Hồi quy 163 Python, 20 JS đạt | Chưa thử duyệt hai bản nháp này, rời trang khi chưa lưu hoặc restart server; dữ liệu và URL đều giả |
| 04/11/2026 | APR-01 / FMT-02 | Đang làm | Duyệt hai bản nháp Facebook/Threads trên fixture qua UI; xem trước từng bản khớp nội dung xuất hiển thị và nguồn giả, có nhãn giới hạn tương ứng | Xác nhận và nguồn giả; chưa kiểm tra clipboard, tệp tải hoặc tài khoản nền tảng trong lượt này |
| 04/11/2026 | APR-03 / QA-02 | Đang làm | Tải hai tệp Facebook/Threads từ UI kho fixture, đọc UTF-8 và đối chiếu nội dung, xuống dòng, hai nguồn giả với bản hiển thị | Chưa kiểm tra clipboard ở lượt này hay tính đúng bộ đếm trên nền tảng thật |
| 04/11/2026 | PUB-04 / QA-02 | Đang làm | Tách phân tích các giá trị số liệu để chuẩn bị biểu mẫu có nhãn; thêm test trước và giữ test handler hiện có. Sau sửa 163 Python, 21 JS đạt | Prompt vẫn còn; chưa triển khai biểu mẫu hoặc smoke trình duyệt, tiếp tục giữ kiểm tra và idempotency |
| 04/11/2026 | QA-02 / POST-04 | Đang làm | Fixture riêng X hai đoạn: dừng, khởi động lại server cùng kho rồi mở lại UI; giữ trạng thái 1/2, URL giả đoạn 1 và nội dung/nguồn hai đoạn | Ghi nhận ban đầu chuẩn bị bằng service; không thử mất điện, dữ liệu vận hành, nhập số liệu hoặc đính chính |
| 04/11/2026 | QA-03 | Không áp dụng trong đợt này | Người dùng xác nhận chưa có dữ liệu SQLite cũ; bỏ bước thử trên bản sao dữ liệu cũ | Fixture migration/restore vẫn được kiểm thử; không khẳng định đã thử dữ liệu vận hành |
| 04/11/2026 | PUB-04 / QA-02 | Đang làm | Thay prompt bằng biểu mẫu có nhãn; smoke trên trình duyệt tích hợp với fixture X lưu 10 lượt xem, 0 lượt thích và các giá trị chưa biết. Sửa lỗi sự kiện nhập khiến vùng phiên bản bị đánh dấu sửa; có test hồi quy | Chưa thử mọi kênh, mất mạng thật hoặc toàn bộ QA; cần đối chiếu số liệu sau khi tải lại nếu kết quả lưu không rõ |
| 04/11/2026 | PUB-03 / QA-02 | Đang làm | Biểu mẫu đính chính có xác nhận và giữ nội dung khi lỗi. Trình duyệt trên kho giả chặn URL trùng, yêu cầu xác nhận lại khi sửa, lưu URL mới đúng đoạn và hiện lịch sử URL cũ | Chưa thử hủy ghi nhận qua UI, mọi kênh hoặc mất mạng thật; không tác động bài trên mạng xã hội |
| 04/11/2026 | PUB-03 / QA-02 | Đang làm | Hủy hai ghi nhận giả qua UI: 2/2 → 1/2 → 0/2, lịch sử giữ lý do và URL, nội dung vẫn khóa sau mở lại. Bổ sung tên truy cập riêng cho ô URL từng đoạn và kiểm tra cây accessibility | Chưa thử trình đọc màn hình, mọi kênh, ghi lại qua hộp xác nhận hoặc mất mạng thật |
| 04/11/2026 | PUB-03/04 / QA-02 | Đang làm | Lịch sử hiện sự kiện dễ đọc và số liệu của lượt cũ; thử trên fixture X sau đính chính/hủy, đối chiếu 10 lượt xem và 0 lượt thích. Test sự kiện lạ và payload lỗi giữ thông tin thô; Python 163/163, JS 26/26 | Chưa thử mọi dữ liệu hỏng, trình đọc màn hình hay các kênh khác |
| 04/11/2026 | PUB-02 / POST-03/05 | Đang làm | Sau phản hồi ghi nhận thành công, xóa khóa chống lặp trong trang để lượt ghi mới sau hủy không dùng lại khóa cũ. Test handler giả xác nhận retry sau lỗi giữ khóa và lượt mới dùng khóa khác | Chưa thử chuỗi đầy đủ qua hộp xác nhận trình duyệt hoặc mất mạng thật; tiếp tục đối chiếu trạng thái khi kết quả không rõ |
| 04/11/2026 | PUB-02 / POST-03/05 / QA-02 | Đang làm | Vùng xác nhận ghi nhận nêu đoạn, kênh, URL; thay URL vô hiệu xác nhận. Trên cùng trang fixture X: ghi → hủy → ghi lại cùng URL thành công, 0/2 → 1/2 → 0/2 → 1/2; test handler retry và thay URL | Chưa thử mất mạng thật, mọi kênh hoặc toàn bộ QA bàn phím |

Mỗi lần cập nhật nên ghi: task ID; file/commit; lệnh test và kết quả; dữ liệu dùng là fixture/kho thử/bản sao; giới hạn chưa kiểm chứng. Không đưa khóa, cookie, dữ liệu riêng, nội dung bản nháp chưa công bố hoặc DB vào repo công khai.

## 12. Sổ quyết định

| Ngày / ID | Quyết định | Trạng thái / căn cứ |
| --- | --- | --- |
| 03/11/2026 / SCOPE | Giữ người dùng duyệt và tự đăng; chưa AI API/tự đăng | Đề xuất mặc định của kế hoạch; phù hợp workflow hiện có |
| 03/11/2026 / DATA | Additive schema 4 + legacy nguyên vẹn; clone không kế thừa approval | Đề xuất để giảm rủi ro dữ liệu |
| 03/11/2026 / LIMIT | 1–10 mục, 3 nguồn/mục, 20 URL khác nhau, packet 64 KiB, tối đa 20 đoạn | Các ngưỡng được áp dụng và có test biên mức service; không phải hạn mức nền tảng. BASE-02 vẫn mở cho hợp đồng API và xác nhận còn lại |
| 04/11/2026 / D02-D03 | Chọn giới hạn kỹ thuật 1–10 mục, 1–3 nguồn mỗi mục và tối đa 20 URL khác nhau cho bản tin. Mức 3–5 mục là gợi ý biên tập, không phải điều kiện bắt buộc; draft cũ giữ workflow và giới hạn riêng. | Đối chiếu `MAX_ITEMS`, `MAX_SOURCES_PER_ITEM`, `MAX_SOURCE_URLS` trong `newsroom/bulletins.py`; test `test_item_and_source_limits_at_boundaries_are_atomic`. Chỉ chốt quyết định phạm vi; BASE-02 tiếp tục mở cho phần hợp đồng API còn cần đối chiếu đầy đủ. |
| 04/11/2026 / BASE-03 NFC | [Tài liệu X](https://docs.x.com/fundamentals/counting-characters) mô tả đếm sau chuẩn hóa NFC và khuyến nghị `twitter-text`. Mã vendored chuẩn hóa NFC trước khi nhận diện URL/emoji và tính trọng số; gọi `count_text('x', ...)` với `café` dạng tổ hợp và dạng tách đều trả `(4, True)`. | Đây là kiểm tra một ví dụ cục bộ, không xác minh toàn bộ Unicode, URL, emoji mới hoặc composer X; Threads vẫn là ước lượng. BASE-03 và điều kiện phát hành liên quan tiếp tục mở. |
| 04/11/2026 / REQUEST | Chọn tối đa 128.000 byte UTF-8 cho JSON POST và 65.536 byte UTF-8 cho toàn bộ packet; vượt giới hạn phải báo lỗi thay vì cắt. | Đối chiếu `MAX_BODY` trong `newsroom/server.py`, `MAX_PACKET_BYTES` trong `newsroom/bulletins.py`; test `test_bulletin_request_utf8_size_boundary_over_http` và `test_packet_limit_counts_complete_utf8_output_and_identifies_large_items`. Hai giới hạn có phạm vi khác nhau, không phải giới hạn nền tảng. |
| 03/11/2026 / COUNTER | X dùng twitter-text vendored với dữ liệu emoji Unicode 15.1; 24 fixture upstream có commit và giấy phép ghim trong `tests/fixtures/TWITTER-TEXT-README.md`. Threads dùng ước lượng có thể đếm thiếu | Chưa đóng BASE-03: hành vi X thực tế, emoji mới hơn và cách đếm Threads chưa được xác minh đầy đủ; phải đóng trước gate G3 |
| — / URL | Mẫu URL bài đăng và alias hợp lệ Facebook/Threads/X | Chưa chốt; BASE-03/PUB-01 |
| — / RELEASE | Bằng chứng pilot và chấp thuận dùng trên DB chính | Chưa có; G6 |

## 13. Tài liệu liên quan

- [README](../README.md): cách chạy và phạm vi đang có.
- [Kiến trúc hiện hành](KIEN-TRUC.md): schema, snapshot, bảo mật và giới hạn thu thập.
- [Hướng dẫn sử dụng hiện hành](HUONG-DAN-SU-DUNG.md): luồng thủ công và backup/restore.
- [Bằng chứng kiểm thử](KIEM-THU.md): tách test phần mềm, nguồn thật và giới hạn chưa xác nhận.
- [API bản tin đa kênh](API-BAN-TIN-DA-KENH.md): bản đồ route và điều kiện chính của nhánh phát triển.

Tài liệu này bổ sung roadmap kỹ thuật; không thay thế mô tả chức năng hiện đang có trong README cho tới khi từng mốc thực sự được triển khai và kiểm thử.
