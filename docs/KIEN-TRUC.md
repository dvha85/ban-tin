# Thiết kế bản 0.3

## Phần mở rộng 0.4 đang phát triển

- `migrations.py` quản lý nâng cấp schema 4 và sao lưu SQLite trước migration. Các bảng cũ vẫn được giữ; cần tiếp tục kiểm tra fixture, rollback và khôi phục trước khi dùng với kho vận hành.
- `bulletins.py` quản lý bản tin, mục, snapshot nguồn, revision và gói tư liệu. `variants.py` quản lý biến thể, xác nhận và snapshot duyệt; `social_formats.py` tạo văn bản cuối, đếm và đề xuất chia đoạn. `publications.py` lưu URL, sự kiện đính chính và số liệu do người dùng nhập.
- Mỗi phiên bản duyệt có hash và policy/renderer version. Sau ghi nhận đoạn đầu, nội dung bị khóa; bản sao là đối tượng chỉnh sửa mới. Export thông thường và bản lưu lịch sử là hai đường riêng.
- Không có kết nối xuất bản xã hội. Bộ đếm Threads hiện là ước lượng; bộ đếm X dùng `twitter-text` vendored với bộ nhận diện emoji Unicode 15.1 riêng. Chưa đủ bằng chứng để bảo đảm mọi chuỗi hoặc hành vi của nền tảng hiện hành. Chưa coi kiến trúc đang phát triển là bản 0.4 đã nghiệm thu.

## Phạm vi

Một người vận hành, một máy Windows, một Facebook Page công khai dưới thương hiệu riêng. Chỉ biên tập và xuất bài chữ. Không có OAuth / Meta SDK / publish worker. Kết nối model dành riêng cho trình duyệt là tùy chọn, mặc định chưa cấu hình; không dùng đăng nhập cá nhân sẵn có.

Lõi: Python 3.11+, thư viện chuẩn, SQLite WAL, máy chủ HTTP chỉ bind `127.0.0.1`, HTML/CSS/JavaScript cục bộ. Không tải font, ảnh hay mã JavaScript giao diện từ CDN. Công cụ web nằm trong venv riêng (`requirements-web.txt`); Hermes dùng SDK trong môi trường đã cài của nó và hồ sơ tạm mới cho từng lượt. Máy chủ tích hợp chỉ dành cho môi trường cá nhân này, không dùng cho website công khai.

## Luồng dữ liệu

Danh mục RSS/API → hoặc Crawl4AI cho nguồn web → nếu thực sự cần tương tác: hàng đợi bền vững → **người dùng xác nhận lượt model** → Hermes + Browser Use bị giới hạn → tin ứng viên + các nguồn trùng → bản nháp với ảnh chụp tư liệu → gói văn bản → **người dùng chuyển sang ChatGPT** → **người dùng nhập kết quả** → lưu → kiểm tra → duyệt phiên bản → xuất văn bản → **người dùng tự đăng Facebook** → ghi nhận lời xác nhận đã đăng / số liệu do người dùng nhập.

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

SQLite gồm `articles`, `article_sources`, `drafts`, `history`, `source_health`, `metrics`, `collection_settings`, `collection_jobs`, `collection_evidence`, `collection_attempts` và `custom_sources` (schema3). Mỗi thao tác mở một kết nối có thời hạn, đóng rõ ràng sau khi dùng để tránh giữ tệp trên Windows. Các thao tác sửa/duyệt dùng `BEGIN IMMEDIATE` + revision để không mất cập nhật giữa hai cửa sổ.

Schema v1/v2 → v3: SQLite backup API tạo bản trước nâng cấp (`pre-v02` cho v1, `pre-v03` cho v2), thêm bảng/index rồi đặt `user_version=3`; không viết lại payload/hash bản nháp. Không tự hạ cấp dữ liệu v3 bằng mã cũ. Muốn khôi phục bản trước, dùng bản sao lưu sang thư mục mới sau khi dừng ứng dụng; không ghi đè DB đang hoạt động.

`POST /api/collection/sources` yêu cầu phiên + CSRF + Origin + `confirmed=true`, chỉ chạy khi không có lượt thu thập khác. Đọc mạng kiểm tra trước giao dịch; lưu nguồn + bật nguồn trong cùng `BEGIN IMMEDIATE`, kiểm tra lại trùng/giới hạn20 dưới khóa. Không tự sửa/xóa nguồn hoặc đổi bản nhập tay thành theo dõi. Worker của nguồn tùy chỉnh nhận snapshot cấu hình đã kiểm tra qua stdin, kiểm tra lại HTTPS/host/path/loại rss|web ở worker; không đọc DB. Danh mục có sẵn không bị snapshot ghi đè. RSS cũ giữ luồng cũ; RSS tùy chỉnh dùng transport ghim IP, chặn proxy môi trường và redirect khác miền, kiểm tra lại robots trên redirect được phép.

## Các hợp đồng quan trọng

1. Chuẩn hóa URL bỏ fragment, một số tham số tracking, giữ tham số có ý nghĩa. Trùng URL được gom; tiêu đề chuẩn hóa giống hệt chỉ được gom khi có ngày nguồn cách nhau tối đa 48 giờ. Không dùng nhận diện ngữ nghĩa. Tin khác nhau vẫn có thể bị gom nhầm nếu tiêu đề / ngày giống nhau, nên phải kiểm tra nguồn.
2. RSS được tải tối đa 3 MB, HTTPS, timeout, chỉ tên miền cố định của từng nguồn. Redirect ngoài miền bị từ chối, không vượt tường phí. Từ chối DTD/entity; trích văn bản bỏ script/style. RSS không tải URL bài viết hoặc ảnh; adapter web có đọc HTML tạm để lấy trích đoạn, không lưu toàn văn vào DB. URL nhập thủ công không được fetch; các ghi chú nhập lại được gắn nhãn thủ công.
3. Ngày nguồn, loại ngày (đăng/cập nhật/chưa rõ) và ngày lấy tư liệu được giữ riêng. Không lấy ngày fetch giả thành ngày công bố. Ngày hiển thị dùng múi giờ Việt Nam.
4. Draft có ảnh chụp nguồn; cập nhật RSS về sau không sửa ảnh chụp của draft. Có thể cập nhật nguồn bằng thao tác sửa bản nháp và duyệt lại.
5. Duyệt gắn hash của tiêu đề, nội dung, góc nhìn, nhóm, Page, nguồn và 5 xác nhận. Sửa nội dung hủy hash và đặt lại xác nhận; chỉ xuất đúng hash. Bài đã ghi nhận đăng là bất biến về nội dung, số liệu là dữ liệu riêng có thể cập nhật.
6. Đích Page là nhãn do người dùng nhập, không chứng minh quyền quản trị. URL Facebook là lời xác nhận thủ công, không được truy cập để xác minh. Không có external send để retry hay cần đối soát tự động.
7. Cookie ngẫu nhiên theo phiên tiến trình và cổng, HttpOnly/SameSite=Strict. Tác vụ thay đổi cần cookie + CSRF token + Origin nội bộ; kiểm tra Host chống rebinding, không CORS, CSP ngăn script ngoài/inline và frame. Không có bảo vệ khỏi chương trình chạy cùng tài khoản Windows.
8. Request tối đa 128 KB. Với lỗi đầu vào, chỉ drain lượng body nhỏ có khai báo để Windows trả lỗi HTTP ổn định; không đọc không giới hạn.
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
