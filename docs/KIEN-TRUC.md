# Kiến trúc Bàn tin

## Phần mở rộng 0.4 đang phát triển

- `migrations.py` quản lý nâng cấp schema 4 và sao lưu SQLite trước migration. Sau khi tạo bảng, runner kiểm tra cấu trúc cần thiết và khóa ngoại trong cùng transaction trước khi ghi version 4; lỗi làm rollback. Khi mở kho đã ở version 4, runner cũng kiểm tra hợp đồng cấu trúc trên một read snapshot và dừng nếu không hợp lệ. Kiểm tra này không thay cho kiểm tra toàn bộ nội dung hoặc `integrity_check`; các bảng cũ vẫn được giữ.
- Sao lưu thông thường và sao lưu trước migration dùng `backup_utils.py` để dành tên tệp theo chế độ tạo độc quyền; nếu trùng tên sẽ thử tên mới tối đa mười lần, không mở tệp đã có làm đích. Nếu thao tác phát sinh ngoại lệ, ứng dụng cố gắng dọn tệp chưa hoàn tất và báo thêm nếu dọn thất bại. Không coi đây là bảo đảm đối với mất điện hoặc tiến trình bị kết thúc cưỡng bức.
- `bulletins.py` quản lý bản tin, mục, snapshot nguồn, revision và gói tư liệu. `variants.py` quản lý biến thể, xác nhận và snapshot duyệt; `social_formats.py` tạo văn bản cuối, đếm và đề xuất chia đoạn. `publications.py` lưu URL, sự kiện đính chính và số liệu do người dùng nhập.
- Lưu trữ bản tin là trạng thái tổ chức có thể đảo ngược: sự kiện `bulletin_archived`/`bulletin_unarchived` trong `bulletin_history` xác định trạng thái, với ID sự kiện làm `archive_revision` để phát hiện xung đột. Nó không tăng revision nội dung, không xóa hay vô hiệu bản duyệt/ghi nhận và không khóa chỉnh sửa. Thống kê vẫn tính cả bản tin lưu trữ. Không thêm bảng hoặc đổi schema; bản sao lưu phải giữ lịch sử để giữ trạng thái này. Phiên bản mã cũ không biết ẩn bản tin đã lưu trữ.
- Mỗi phiên bản duyệt có hash và policy/renderer version. Sau ghi nhận đoạn đầu, nội dung bị khóa; bản sao là đối tượng chỉnh sửa mới. Export thông thường và bản lưu lịch sử là hai đường riêng.
- Preview bản nháp dựng từ bản tin và phiên bản trong cùng read snapshot; các mục bị lược được trả bằng ID và UI chỉ ghép tên khi revision bản tin hiển thị khớp. UI bỏ phản hồi khi bản tin/kênh, đoạn/nguồn hoặc hộp hiển thị đã đổi trong lúc chờ. Chia đoạn là đề xuất chưa lưu, giữ quan hệ mục/nguồn từ đoạn gốc; người biên tập phải rà từng đoạn. Lưu, duyệt, export và bản lịch sử dùng revision hoặc snapshot tương ứng, không coi preview là bản đã duyệt.
- Form giữ nguyên chuỗi CRLF/CR và cấu trúc chọn nguồn mặc định khi dữ liệu hiển thị không đổi; thay đổi thực sự được gửi lại như dữ liệu mới. Sao chép/tải bản duyệt đọc lại và đối chiếu snapshot hiển thị, còn retry trong hộp thủ công kiểm tra hộp và ngữ cảnh đang chọn. Các kiểm tra là tại thời điểm phản hồi, không thu hồi thao tác clipboard đã bắt đầu, không kiểm soát Ctrl+C trực tiếp và không ngăn client/đường tải cũ.
- Vùng xuất tải phiên bản, snapshot và ghi nhận bằng các request riêng; trước khi ghép chúng trên trang, UI kiểm tra ID bản duyệt ở phiên bản và snapshot, cùng ID bản duyệt và vị trí của các ghi nhận hiệu lực. UI đọc lại phiên bản và đối chiếu ID, revision, ID bản duyệt; vùng sửa phiên bản đã duyệt tạm thời không tương tác trong lúc kiểm tra. Nếu không khớp, UI yêu cầu mở lại. Đây là kiểm tra tại thời điểm các phản hồi được nhận, không khóa các cửa sổ khác hoặc bảo đảm mọi thay đổi sau đó được phát hiện.
- Không có kết nối xuất bản xã hội. Bộ đếm Threads v6 ước lượng theo số điểm mã Unicode, dựa trên một số mẫu đã đối chiếu composer; bộ đếm X dùng `twitter-text` vendored với bộ nhận diện emoji Unicode 15.1 riêng. Chưa đủ bằng chứng để bảo đảm mọi chuỗi hoặc hành vi của nền tảng hiện hành. Chưa coi kiến trúc đang phát triển là bản 0.4 đã nghiệm thu.

## Phạm vi

Một người vận hành trên một máy Windows. Luồng bài cũ hướng đến một Facebook Page; phần mở rộng 0.4 đang phát triển cho phép biên tập các phiên bản chữ riêng cho Facebook, Threads và X. Nhãn đích do người dùng nhập, không chứng minh quyền quản trị tài khoản. Không có OAuth / Meta SDK / publish worker và ứng dụng không tự đăng. Kết nối model dành riêng cho trình duyệt là tùy chọn, mặc định chưa cấu hình; không dùng đăng nhập cá nhân sẵn có.

Lõi: Python 3.11+, thư viện chuẩn, SQLite WAL, máy chủ HTTP chỉ bind `127.0.0.1`, HTML/CSS/JavaScript cục bộ. Không tải font, ảnh hay mã JavaScript giao diện từ CDN. Công cụ web nằm trong venv riêng (`requirements-web.txt`); Hermes dùng SDK trong môi trường đã cài của nó và hồ sơ tạm mới cho từng lượt. Máy chủ tích hợp chỉ dành cho môi trường cá nhân này, không dùng cho website công khai.

## Luồng dữ liệu

Danh mục RSS/API → hoặc Crawl4AI cho nguồn web → nếu thực sự cần tương tác: hàng đợi bền vững → **người dùng xác nhận lượt model** → Hermes + Browser Use bị giới hạn → tin ứng viên và nguồn.

Từ đây, luồng bài cũ tạo bản nháp một bài cho Facebook. Luồng 0.4 tạo bản tin có một hoặc nhiều mục, giữ snapshot nguồn và cho phép tạo phiên bản riêng theo kênh. Người dùng tự biên tập hoặc chuyển gói tư liệu sang công cụ AI rồi nhập lại kết quả; sau đó kiểm chứng, duyệt, xuất và **tự đăng**. URL và số liệu được ghi theo thông tin người dùng nhập, không được ứng dụng xác minh với nền tảng.

Nguồn danh mục dùng adapter đã cấu hình. Khi người dùng thêm website, dò RSS/Atom có giới hạn cùng tên miền trước, không tự dò API. Web chỉ được chọn rõ với phạm vi đường dẫn; tầng AI vẫn cần xác nhận riêng. Lỗi cài đặt/mạng/chặn truy cập không tự chuyển thành lượt AI.

## Tệp và dữ liệu

- `newsroom/config.py`: nguồn RSS cố định, vị trí dữ liệu ngoài OneDrive/UNC.
- `newsroom/feeds.py`: RSS/Atom, trích đoạn tối đa 1.200 ký tự, chuẩn hóa URL, quy tắc ưu tiên.
- `newsroom/collection.py`: danh mục bật/tắt, API công khai, HTTPS ghim IP công khai, robots, trích HTML, kiểm tra giao thức tiến trình.
- `newsroom/collection_service.py`: cài đặt nguồn, hàng đợi, hạn mức lượt 24 giờ, sổ lượt chạy, lưu bằng chứng thu thập.
- `newsroom/subscriptions.py`: kiểm tra URL/phạm vi nguồn tùy chỉnh, dò feed từ HTML hoặc tối đa 3 đường dẫn cùng miền, đọc RSS mới qua HTTPS ghim IP + robots. Không đọc bài trong RSS hoặc gọi model khi thêm nguồn.
- `newsroom/collect_worker.py`: Crawl4AI / Browser Use trong tiến trình con; Hermes chỉ có `news_browser`. Không trao cho model hàm SQL hoặc HTTP của Bàn tin.
- `newsroom/service.py`: giao dịch, bản nháp, lịch sử, duyệt, xuất, số liệu và backup.
- `newsroom/server.py`: phiên cục bộ, chống yêu cầu chéo nguồn, giới hạn kích thước, các điểm giao tiếp.
- `newsroom/__main__.py`: chạy, chu kỳ đọc nguồn 2 giờ, backup, restore sang thư mục mới, demo riêng.
- `newsroom/static/`: giao diện, không chứa khóa API.
- `tests/`: kiểm thử không gọi mạng xã hội / API AI.

Schema 3 có `articles`, `article_sources`, `drafts`, `history`, `source_health`, `metrics`, `collection_settings`, `collection_jobs`, `collection_evidence`, `collection_attempts` và `custom_sources`. Schema 4 bổ sung `bulletins`, `bulletin_items`, `content_variants`, `variant_approvals`, `publications`, `publication_events`, `publication_metrics` và `bulletin_history`. Mỗi thao tác mở một kết nối có thời hạn, đóng rõ ràng sau khi dùng để tránh giữ tệp trên Windows. Các thao tác sửa/duyệt dùng `BEGIN IMMEDIATE` + revision để phát hiện xung đột; client cũ không gửi `expected_bulletin_revision` cho một số thao tác phiên bản không có kiểm tra bổ sung đối với bản tin đang hiển thị.

Schema v1/v2 → v3: SQLite backup API tạo bản trước nâng cấp (`pre-v02` cho v1, `pre-v03` cho v2), thêm bảng/index rồi đặt `user_version=3`; không viết lại payload/hash bản nháp. Không tự hạ cấp dữ liệu v3 bằng mã cũ. Muốn khôi phục bản trước, dùng bản sao lưu sang thư mục mới sau khi dừng ứng dụng; không ghi đè DB đang hoạt động.

`POST /api/collection/sources` yêu cầu phiên + CSRF + Origin + `confirmed=true`, chỉ chạy khi không có lượt thu thập khác. Đọc mạng kiểm tra trước giao dịch; lưu nguồn + bật nguồn trong cùng `BEGIN IMMEDIATE`, kiểm tra lại trùng/giới hạn20 dưới khóa. Không tự sửa/xóa nguồn hoặc đổi bản nhập tay thành theo dõi. Worker của nguồn tùy chỉnh nhận snapshot cấu hình đã kiểm tra qua stdin, kiểm tra lại HTTPS/host/path/loại rss|web ở worker; không đọc DB. Danh mục có sẵn không bị snapshot ghi đè. RSS cũ giữ luồng cũ; RSS tùy chỉnh dùng transport ghim IP, chặn proxy môi trường và redirect khác miền, kiểm tra lại robots trên redirect được phép.

## Các hợp đồng quan trọng

1. Chuẩn hóa URL bỏ fragment, một số tham số tracking, giữ tham số có ý nghĩa. Trùng URL được gom; tiêu đề chuẩn hóa giống hệt chỉ được gom khi có ngày nguồn cách nhau tối đa 48 giờ. Không dùng nhận diện ngữ nghĩa. Tin khác nhau vẫn có thể bị gom nhầm nếu tiêu đề / ngày giống nhau, nên phải kiểm tra nguồn.
2. RSS được tải tối đa 3 MB, HTTPS, timeout, chỉ tên miền cố định của từng nguồn. Redirect ngoài miền bị từ chối, không vượt tường phí. Từ chối DTD/entity; trích văn bản bỏ script/style. RSS không tải URL bài viết hoặc ảnh; adapter web có đọc HTML tạm để lấy trích đoạn, không lưu toàn văn vào DB. URL nhập thủ công không được fetch; các ghi chú nhập lại được gắn nhãn thủ công.
3. Ngày nguồn, loại ngày (đăng/cập nhật/chưa rõ) và ngày lấy tư liệu được giữ riêng. Không lấy ngày fetch giả thành ngày công bố. Ngày hiển thị dùng múi giờ Việt Nam.
4. Draft cũ và mục bản tin có ảnh chụp nguồn; cập nhật nguồn về sau không sửa ảnh chụp đã lưu. Thay đổi nội dung hoặc nguồn cần được kiểm tra và duyệt lại theo luồng tương ứng.
5. Bản duyệt gắn hash và các xác nhận; thay đổi liên quan hủy duyệt theo phạm vi. Sau ghi nhận, nội dung phiên bản bị khóa và snapshot được giữ; số liệu là dữ liệu riêng. Bản sao cho phép tiếp tục biên tập.
6. Đích đăng là nhãn do người dùng nhập, không chứng minh quyền quản trị. URL ghi nhận là thông tin thủ công, không được truy cập để xác minh. Không có external send để retry hay cần đối soát tự động.
7. Cookie ngẫu nhiên theo phiên tiến trình và cổng, HttpOnly/SameSite=Strict. Tác vụ thay đổi cần cookie + CSRF token + Origin nội bộ; kiểm tra Host chống rebinding, không CORS, CSP ngăn script ngoài/inline và frame. Không có bảo vệ khỏi chương trình chạy cùng tài khoản Windows.

   Khi có lỗi phiên, giao diện cho phép lấy lại cookie và token mà không gửi lại thao tác hoặc thay nội dung đang nhập. Trạng thái nền và khôi phục đối chiếu đường dẫn kho ban đầu và ID tệp đã biết trong phiên; `store_file_id` là hash của thiết bị và file ID do hệ điều hành trả về. Khi phát hiện khác, trang chặn các yêu cầu ghi tiếp theo và yêu cầu sao chép nội dung trước khi tải lại. Nếu token phiên thay đổi mà thiếu ID để so sánh, trang không nhận token, giữ phần đang soạn và chặn ghi cùng các nút xuất bản duyệt của bài cũ/đa kênh đến khi người dùng khôi phục thành công. Đây là chặn trong UI, không ngăn client khác, URL tải trực tiếp hoặc Ctrl+C. Trong cùng phiên, một lần thiếu ID vẫn được phép và không xóa ID đã biết. Tín hiệu này không phát hiện ghi đè nội dung trên cùng tệp; file ID có thể thiếu, thay đổi hoặc được tái sử dụng. Không hủy yêu cầu đã gửi và không thay thế đối chiếu kết quả chưa rõ. Xem [tài liệu `os.stat`](https://docs.python.org/3/library/os.html#os.stat_result) và [giới hạn file ID của Windows](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-file_id_all_extd_dir_information).
8. JSON POST tối đa 128.000 byte UTF-8. Với lỗi đầu vào, chỉ drain lượng body nhỏ có khai báo để Windows trả lỗi HTTP ổn định; không đọc không giới hạn. Packet có giới hạn riêng 65.536 byte UTF-8.
9. Backup dùng SQLite backup API, kiểm tra toàn vẹn. Restore chỉ nhận phiên bản đúng, toàn vẹn và thư mục mới; không ghi đè bản chính. Không có xóa / luân chuyển tự động hoặc tự gửi bản sao lên cloud.
10. Chỉ cho phép một tác vụ AI đang chạy. Kiểm tra trạng thái/hạn mức và ghi `running` + attempt trong cùng giao dịch trước khi tạo tiến trình. Các lượt unknown/đã đóng vẫn tiêu thụ hạn mức. Khởi động lại không hoàn quota; không tự replay unknown. HTTP báo lỗi trước khi trả `started` nếu tác vụ không còn chờ hoặc hết lượt.
11. Windows JobObject và watchdog giới hạn vòng đời con. Worker nhận yêu cầu qua stdin, không có khóa trên dòng lệnh. Hồ sơ Hermes được parent dọn sau khi worker thoát để không vướng tệp log/DB bị giữ trên Windows. Đây không phải sandbox OS: thư viện và mã trang vẫn cần được tin cậy/cập nhật có kiểm thử.
12. Tối đa 3 bài web/lượt, 2 MB HTML/trang, 3.000 ký tự trích đoạn, 120 giây/worker Crawl4AI; lượt AI tối đa 180 giây/12 vòng, 20 thao tác. Giới hạn này không phải trần tiền hoặc bảo đảm số HTTP request của SDK. Chưa có ngắt tiền nội bộ; yêu cầu hạn mức nhà cung cấp và xác nhận từng lượt.

## Hạn chế cố ý

- Không tích hợp Google Trends, không đo độc giả, không hiểu ngữ nghĩa tin, không xác minh sự thật / bản quyền / quyền kiếm tiền.
- Không lưu toàn văn web, chỉ trích đoạn; một số RSS chỉ có mô tả ảnh. Nguồn hãng có thiên lệch quảng bá. Hash chứng minh tính nhất quán của tư liệu thu được, không chứng minh sự thật hay quyền sử dụng.
- Không tự lưu từng ký tự; người dùng phải nhấn lưu. Cảnh báo chưa lưu không thay thế việc sao lưu.
- Dữ liệu và lịch sử tăng theo thời gian. UI chỉ hiển thị 500 tin gần nhất, không có xóa hay tìm toàn bộ kho cũ ở bản đầu.
- Không có cập nhật phần mềm tự động, chạy cùng Windows, tác vụ cloud hoặc hoạt động khi máy ngủ.
- Nút sao chép phụ thuộc trình duyệt. Luôn có lựa chọn văn bản thủ công và tải tệp bài đã duyệt.
- Chưa thử trên hệ điều hành khác, màn hình di động hay chạy dài ngày. Bản đầu cần người dùng thử thực tế trước khi tăng khối lượng.
- Mới thử SDK Hermes ngoại tuyến, chưa kiểm chứng suy luận/gọi công cụ bằng model thật, token, hóa đơn hay chất lượng. Khi nâng Hermes cần kiểm tra lại schema công cụ; nếu phát hiện ngoài `news_browser` thì dừng trước suy luận.
- Chặn tài nguyên ngoài miền giúp giới hạn quyền nhưng có thể làm hỏng trang dùng CDN/đăng nhập hoặc API ngoài miền. Không tự nới quyền để lấy bằng được tin.
