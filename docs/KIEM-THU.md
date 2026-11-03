# Bằng chứng kiểm thử — cập nhật 16/10/2026

## Phần 0.4 đang phát triển (03/11/2026)

- Lần chạy 03/11/2026: `python -B -m unittest discover -s tests` đạt 138/138; `node --test tests/draft-state.test.js tests/source-warnings.test.js tests/request-size.test.js tests/inbox-utils.test.js` đạt 7/7; `node --check newsroom/static/app.js` đạt. Có test lỗi rollback/restore, từ chối khi không thể sao lưu, snapshot duyệt, lưu không thay đổi không hủy duyệt, sao chép bài cũ, URL, số liệu `null`/`0`, HTTP/CSRF và chia đoạn 9 → 10, giữ nguồn, từ chối câu quá dài.
- Kiểm tra thủ công trên ứng dụng qua trình duyệt trong máy, với kho fixture nằm tại thư mục tạm tách khỏi kho vận hành: chọn ba tin, tạo bản tin, lưu và xác nhận một mục, tạo và duyệt một phiên bản X, ghi nhận URL X giả, khởi động lại, và tạo bản sao từ một bài cũ trống. Không có bài đăng thật.
- Fixture `tests/fixtures/legacy-v3.sql` và expected JSON được tạo từ mã commit `a180354` bằng dữ liệu giả: có bài draft/approved/published, history, metrics và nguồn tùy chỉnh. Test migration đối chiếu nguyên hàng cũ, hash trong hàng draft và nội dung xuất, đồng thời kiểm tra bản backup schema 3.
- Schema 1 và 2 được kiểm tra bằng fixture **mô phỏng** từ schema 3 đã bỏ các bảng về sau; đây không phải snapshot từ bản phát hành lịch sử. Có kiểm thử hủy migration nếu một kết nối khác ghi trong lúc sao lưu.
- Restore: test giả lập lỗi sau khi đã ghi một phần DB đích; tệp dở và thư mục rỗng được dọn, sau đó khôi phục lại vào cùng tên thư mục thành công. Nếu xuất hiện một tệp khác trong thư mục, test xác nhận tệp đó được giữ lại và lỗi ghi chú rằng không dọn được thư mục. Test dùng exception có kiểm soát, chưa mô phỏng mất điện hoặc tiến trình bị buộc kết thúc.
- Bộ đếm X được đối chiếu với 24 trường hợp từ bộ [twitter-text conformance](https://github.com/twitter/twitter-text/blob/30e2430d90cff3b46393ea54caf511441983c260/conformance/validate.yml), gồm URL, chuẩn hóa, ký tự CJK, emoji ghép và ký tự không hợp lệ; nguồn, hash và giấy phép ở `tests/fixtures/TWITTER-TEXT-README.md`. Bộ fixture không chứng minh tính đúng với mọi emoji mới.
- Đối chiếu 7 chuỗi với `twitter-text` JavaScript 3.1.0 và `twemoji-parser` 11.0.2 cài ở thư mục tạm: bộ đó và extractor gốc của thư viện Python trả 9 cho 🫱🏽‍🫲🏻 và 5 cho ❤️‍🔥. Bộ đếm X đã được cập nhật bằng [emoji-test Unicode 15.1](https://unicode.org/Public/emoji/15.1/emoji-test.txt), SHA-256 `d876ee249aa28eaa76cfa6dfaa702847a8d13b062aa488d465d0395ee8137ed9`, để trả 2 cho các chuỗi này theo quy tắc chung trong [tài liệu X](https://docs.x.com/fundamentals/counting-characters); có test biên 280/282 và 24 fixture cũ. Chưa kiểm tra được hành vi ứng dụng X thực tế, emoji sau 15.1 hoặc mọi chuỗi không RGI. Giấy phép dữ liệu nằm tại `newsroom/data/UNICODE-LICENSE.txt`.
- [Tài liệu X](https://docs.x.com/fundamentals/counting-characters) mô tả trọng số và rút gọn URL; [Meta](https://about.fb.com/news/2025/09/attach-text-threads-posts-share-longer-perspectives/) mô tả bài Threads 500 ký tự và tính năng đính kèm văn bản dài. Ứng dụng này chỉ hỗ trợ văn bản chính, chưa hỗ trợ tính năng đính kèm; chưa tìm được đặc tả đủ chi tiết để xác minh cách đếm mọi emoji trên Threads.
- Bộ đếm Threads hiện dùng danh sách emoji cũ: ví dụ U+1FAE8 cho kết quả 1, trong khi biểu diễn UTF-8 chiếm 4 byte. Điều này chứng minh phép ước lượng không phải giới hạn trên của số byte; chưa có bằng chứng rằng Threads thực tế đếm trường hợp này theo byte hay theo quy tắc nào khác.
- HTTP test gửi một surrogate Unicode đơn lẻ tới phiên bản X, xác nhận trả 400 với thông báo phù hợp, không lưu dở; emoji hợp lệ vẫn lưu được. Test này không kiểm chứng tất cả chuỗi Unicode trên các nền tảng.
- Trên Edge, tải `.txt` cho một đoạn X đã duyệt từ kho thử và đọc tệp UTF-8: nội dung và URL nguồn khớp đoạn hiển thị. Đây mới là một trường hợp một đoạn.
- Khi sửa tiêu đề chưa lưu rồi chuyển bản tin, Edge đã hiện hộp xác nhận bỏ thay đổi. Phiên điều khiển bị dừng tại hộp xác nhận nên chưa xác minh cả hai nhánh tiếp tục/hủy.
- Bổ sung nhắc kiểm tra nguồn thiếu/ngắn, ngày không rõ/tương lai/cũ hơn 7 ngày. Chạy `node --test tests/draft-state.test.js tests/source-warnings.test.js` đạt 3/3; test HTTP riêng xác nhận tệp JS được phục vụ và vẫn chặn traversal. Đây là nhắc biên tập, không phải kiểm chứng độ tin cậy. Chưa smoke giao diện sau thay đổi này.
- Trên kho thử, Hộp tin hiển thị số bản tin đã dùng; khi tạo bản tin mới có cảnh báo, chọn hủy giữ nguyên lựa chọn, chọn tiếp tục tạo được bản mới. Thêm một tin đã dùng vào bản tin đó cũng hiện xác nhận và lưu thành hai mục. Test backend đối chiếu số sử dụng sau tạo và bỏ mục; chưa thử cạnh tranh đồng thời giữa nhiều cửa sổ.
- Giới hạn request phía trình duyệt đếm byte UTF-8 sau khi đóng gói JSON và báo trước khi gửi nếu vượt 128.000 byte; test JS kiểm tra đúng ngưỡng, vượt một byte và Unicode. Server vẫn kiểm tra độc lập; chưa smoke trường hợp quá ngưỡng qua giao diện.
- Test gói tư liệu kiểm tra toàn bộ đầu ra đúng 65.536 byte và vượt 3 byte Unicode; trường hợp vượt nêu mục lớn và không cắt nội dung. Trên kho thử đã chọn tin, đổi nhóm và thấy số tin đã chọn đang ẩn; nút bỏ lựa chọn xóa cả tin ẩn. Bộ lọc tùy chọn hiện ô số ngày và báo lỗi khi nhập 0; test JS kiểm tra biên ngày, tin thiếu ngày, tương lai và số lựa chọn bị ẩn.
- Sửa bản sao khi mục/nguồn gốc đã bị bỏ: kiểm thử backend giữ đủ các đoạn, không tự gán nguồn khác, chặn lưu/duyệt cho tới khi đối chiếu; bản ghi cũ được giữ. Trên kho thử, sau khi bỏ mục bằng mã kiểm thử và tạo bản sao trên giao diện, nội dung vẫn hiện đầy đủ, cảnh báo xuất hiện và lưu khi chưa xác nhận bị chặn. Chưa kiểm tra mọi tổ hợp thay đổi nguồn trên giao diện.
- Sau khi bản tin gốc mất một mục, giao diện phiên bản X đã ghi nhận hiển thị lại đúng mục và URL nguồn từ snapshot đã duyệt; xem trước lịch sử khớp văn bản và số đếm lưu tại thời điểm duyệt. Test backend kiểm tra provenance/lựa chọn/checklist từ snapshot, chặn dựng lại preview của phiên bản đã khóa bằng bản tin hiện tại. Kho thử và URL giả, không đăng công khai.
- Smoke legacy trên kho thử: nhập URL giả của bài A rồi xác nhận bỏ phần chưa lưu để mở B; ô URL B rỗng. Ghi nhận URL giả cho A qua hộp xác nhận có tiêu đề, Page và URL; mở B thấy ô rỗng, quay A thấy đúng link đã lưu. Nhập URL giả vào B, chọn A rồi hủy cảnh báo: vẫn ở B và giữ nguyên URL đang nhập. Test service xác nhận URL rỗng, tên miền khác hoặc trang chủ Facebook bị từ chối và không đổi draft, lịch sử hay thống kê; chưa kiểm tra những lỗi này trên giao diện.
- Test trùng URL Facebook giữa legacy và biến thể: kiểm tra hai thứ tự ghi, hai bài legacy, alias `m.facebook.com` và tham số chia sẻ; chạy đồng thời hai giao dịch cho cùng URL thì một thành công và một conflict. Phạm vi nhận diện chỉ gồm các dạng URL Facebook mà validator đa kênh hiện hỗ trợ; legacy vẫn chấp nhận các dạng URL khác và chưa thể xác định trùng cho chúng.
- Thử giao diện trên bản tin minh họa hai mục: sửa đồng thời hai mục khiến lưu bị chặn để tránh mất nội dung; đưa mục thứ nhất về giá trị đã lưu thì lưu mục thứ hai thành công, nội dung thứ hai được giữ. Test JS kiểm tra trả lại giá trị gốc của text và checkbox. Hiện vẫn phải xử lý từng phần; chưa hỗ trợ lưu nhiều phần đang sửa cùng lúc. Đây là lượt thử từng bước, chưa tính là pilot hoàn chỉnh có đo thời gian.
- Lượt thử tiếp từ bản tin hai mục đã soạn sẵn: tạo, lưu và duyệt riêng Facebook, Threads và X; các xác nhận kiểm chứng được giả lập với dữ liệu `example.com`, không phải kiểm chứng nguồn thật. X có hai đoạn tiếng Việt/Anh; tệp UTF-8 tải từ giao diện có `1/2`, `2/2`, nội dung và nguồn khớp hai đoạn hiển thị. Đo từ lúc mở bản đang soạn tới lúc tải tệp: 127,3 giây, gồm thời gian điều khiển và chờ; không gồm tạo/chọn tin và soạn mục trước đó, nên không xem là thời gian hoàn chỉnh của pilot. Nhập đồng thời URL giả vào cả hai đoạn thì thao tác ghi nhận bị chặn, tránh ghi nhầm; hộp xác nhận cho đoạn đầu hiển thị đúng kênh, đích và URL nhưng phiên điều khiển bị gián đoạn trước khi xác minh kết quả, không kết luận đã ghi nhận.
- Test xen kẽ trên SQLite WAL: trong lúc xuất, một kết nối khác sửa bản tin và hủy duyệt; lần xuất đã bắt đầu trả snapshot đã duyệt nhất quán trước sửa, lần xuất tiếp theo bị từ chối. Trong lúc xem trước, một kết nối khác bỏ mục; preview vẫn đọc phiên bản và bản tin từ cùng snapshot trước thay đổi. Đây là test mức service, không chứng minh mọi tình huống race HTTP hoặc hành vi sao chép ở trình duyệt.
- Test service xác nhận khi sửa bản tin gốc, checklist của biến thể chưa ghi nhận được bỏ ngay và bản đã ghi nhận giữ nguyên snapshot; khi đổi version policy hoặc renderer, không thể duyệt lại bằng checklist cũ. Smoke Edge với cùng kho demo qua server v1 rồi server v2: biến thể Facebook chưa ghi nhận hiển thị cảnh báo và bản lịch sử, không có nút copy/tải để đăng; nút xem bản đã duyệt báo cần duyệt lại. Lưu phiên bản bỏ năm xác nhận, sau đó đánh dấu lại, lưu và duyệt thành công theo v2. Chưa thử tình huống đổi policy của biến thể đã ghi nhận một phần qua giao diện.
- Checklist từng khẳng định: test service kiểm tra dữ liệu không hợp lệ, lưu/restart, bỏ xác nhận khi đổi nội dung/nguồn và từ chối duyệt mục chưa có bằng chứng/kiểm tra. Trên kho demo mới đã thêm một khẳng định, thấy xác nhận bị bỏ sau khi sửa nội dung rồi đánh dấu và lưu lại thành công. Sau đó dùng Edge tạo, lưu và duyệt thành công một biến thể Facebook từ mục này theo v1 và duyệt lại theo v2; checklist nguồn và quyền đều là xác nhận giả trên dữ liệu `example.com`. Chưa smoke checklist này với các kênh khác.
- Nút sao chép hiển thị thành công nhưng lần đọc clipboard trong trình duyệt kiểm thử trả về rỗng; thử dán bằng trình điều khiển Edge cũng báo vùng clipboard của phiên thử không có dữ liệu. **Chưa xác nhận nội dung clipboard thực tế**, và kết quả này chưa đủ để kết luận clipboard của người dùng bị lỗi. Chưa kiểm tra đầy đủ bàn phím, fallback clipboard, ba pilot, mọi chính sách ký tự hoặc kho vận hành.
- Để chạy: `python -B -m unittest discover -s tests -v` và `node --test tests/draft-state.test.js`. Kết quả cụ thể cần ghi lại sau lần chạy cuối trước phát hành.

## Bản 0.3 — thêm nguồn theo dõi (16/10/2026)

- Baseline64/64 trước sửa. Thêm hồi quy nhập bài thủ công không tạo nguồn theo dõi/không đổi bản duyệt, chạy19/19 bài kiểm tra workflow trước triển khai. Viết hợp đồng tính năng mới trước module; quan sát lỗi chưa có chức năng, sau đó triển khai.
- Bộ cuối **88/88 đạt**, 11.480 giây; Python compileall và Node syntax check đạt. Không nới điều kiện duyệt bài cũ để làm test đạt.
- Nguồn mới: tự tìm RSS/Atom cùng miền hoặc URL feed trực tiếp; HTML thiếu thuộc tính được xử lý; tối đa3 ứng viên; web cần prefix rõ; chưa tìm feed không tự chuyển thành AI. Thêm nguồn không tạo article/draft, chỉ bật theo dõi; refresh đọc bằng transport ghim IP. Tắt nguồn ngừng lượt sau, không xóa tin. Restart giữ nguồn và bật/tắt.
- An toàn: kiểm tra URL/private DNS, SNI/địa chỉ kết nối, không đi qua proxy môi trường trong collector mới; redirect ngoài host bị chặn trước kết nối tiếp theo; redirect dấu `/` cùng đường dẫn cần robots lần nữa. 404 ứng viên có thể thử ứng viên kế tiếp; robots/403 dừng, không coi là thiếu tương tác. Không chấp nhận API tùy ý hoặc khóa bí mật trong URL.
- Giao dịch: trùng URL trang/feed/catalog sau canonical hóa, thêm đồng thời và kiểm tra lại dưới khóa; giới hạn20. HTTP cần session/CSRF/Origin/confirmed, khóa lượt thu thập được giải phóng cả khi lỗi, không nhận thêm nguồn lúc đang chạy thu thập.
- Fixture schema2 →3: backup `pre-v03` còn schema2/toàn vẹn; payload/hash/bản xuất đã duyệt giữ nguyên. Restore schema3 sang thư mục mới khôi phục cả nguồn và bản duyệt. Giữ kiểm tra schema1 cũ và toàn bộ quy trình biên tập/duyệt/xuất/đăng thủ công.
- Native + GUI, kho thử riêng ngoài OneDrive, cổng8879: thêm DEV Community từ trang chủ, phát hiện RSS, hiển thị đầu danh sách với **Bạn đã thêm**, reload giữ nguồn; nhập trùng báo lỗi; nhấn **Lấy tin mới** thêm12 tin. Không draft/job AI. Đã quan sát nhãn/form nhập bài thủ công và phạm vi web tự gợi ý `/news/`; console cuối không có lỗi/cảnh báo. [Ảnh bản thử](images/nguon-tin-v03.png).
- Native custom-source Crawl4AI worker: đọc TypeSafe Blog được3 bài, không cảnh báo. Không model. Hermes truyền snapshot/chặn chưa xác nhận được kiểm tra bằng fixture/mock, chưa có model thật.
- **Chưa dừng/mở lại hay nâng cấp DB chính của người dùng; chưa tự thêm DEV vào nguồn theo dõi chính.** Không đổi mục đã nhập thủ công, chưa kiểm chứng mọi website hoặc lịch chạy dài ngày. Không đăng nhập/tạo tài khoản, chi tiêu, Docker/WSL hay đăng bài.
- Giới hạn:20 nguồn tùy chỉnh, chưa sửa/xóa; liên miền cần dán feed trực tiếp như nguồn riêng, không hỗ trợ đường dẫn mã hóa/phần trăm/non-ASCII; nguồn có kiểm soát truy cập không được vượt chặn. AI vẫn là lane tùy chọn cần cấu hình và duyệt lượt riêng.

## Bản 0.1 — đã thực hiện trước nâng cấp

- Môi trường Windows hiện tại, Python 3.13.13.
- Thư mục ban đầu trống. Viết hợp đồng kiểm thử trước khi triển khai; lần đầu thất bại vì chưa có module. Sau triển khai ban đầu: 20 kiểm thử đạt.
- Bổ sung kiểm thử trước các sửa đổi về tin sửa từ nguồn, trùng tiêu đề khác ngày, dấu cần kiểm chứng, nguồn ghi chú thủ công và header bất thường.
- Bộ cuối: **30 kiểm thử đạt**, đã chạy lặp lại. Bao gồm RSS/Atom, Unicode/XML, chuẩn hóa URL, lọc trùng, cập nhật nguồn không đổi snapshot, kiểm tra duyệt, hủy duyệt, xung đột / lưu đồng thời, bài đã đăng bất biến, số liệu nhập tay, nguồn lỗi một phần, backup/restore, cookie/CSRF/Origin/Host và giới hạn request.
- Kiểm tra cú pháp JavaScript bằng Node.js: đạt. Node không phải yêu cầu để sử dụng ứng dụng.
- Đọc RSS thật: Google 20, Windows 10, Apple 20, Mozilla 20; tổng **70 tin**, 4/4 nguồn trả feed đọc được. Đọc lại không tạo thêm bản trùng. Số lượng là ảnh chụp thời điểm thử, không phải số tin luôn có.
- Trình duyệt trong ứng dụng: mở bản chính, xem 70 tin và 4 nguồn; mở demo riêng, tạo bản nháp, lấy gói tư liệu, nhập tiếng Việt, lưu, duyệt, xem bản xuất kèm nguồn, sửa và xác nhận hủy duyệt; thử chặn bài ngắn, sửa rồi lưu tiếp; khởi động lại và mở lại dữ liệu.
- Đã thử nút sao lưu từ giao diện demo. Bản chính cuối không có lỗi/cảnh báo console được công cụ trình duyệt ghi nhận. [Ảnh giao diện thực tế](images/ban-tin-local.jpg).

## Bản 0.2 — thu thập nhiều tầng

- Baseline trước thay đổi chức năng: 30/30 đạt. Sau bổ sung collector: 44/44; sau các kiểm tra an toàn/nâng cấp/cấu hình: 64/64 (gồm 2 kiểm tra tiến trình Windows thật). Chạy cuối ghi trong WORKLOG.
- Kiểm tra mới: nguồn mới mặc định tắt; bật cần xác nhận và ID trong danh mục; API mẫu chỉ nhận repo được chọn; URL/path/DNS riêng bị từ chối; robots từ chối/lỗi dừng an toàn; WAF/tường phí không chuyển sang AI; lỗi công cụ/mạng không bị coi là cần tương tác; worker timeout không được tự chạy lại; giao thức kết quả sai và exit code lỗi bị từ chối.
- Hàng đợi: một tác vụ hoạt động/nguồn, unknown không tự xếp lại; hết quota trả HTTP lỗi trước `started`; hủy unknown/khởi động lại vẫn tính lượt; đang chạy không hủy hoặc chạy hai lần. Kết quả model giả lập sai, quá lớn, khác miền hoặc một phần hợp lệ không được nhập một phần. Thu tư liệu không tạo/duyệt/đăng bản nháp.
- Migration: dựng DB đúng hình dạng v1 với bản đã duyệt, nâng lên v2, kiểm tra backup trước nâng cấp có schema1/toàn vẹn, bản xuất giữ nguyên. Lặp khởi tạo không sao lưu nâng cấp thêm lần nữa. Lỗi giữ tệp backup trên Windows được tái hiện bằng test rồi sửa đóng kết nối rõ ràng.
- Snapshot: cập nhật tin ứng viên giữ nguyên bản duyệt/hash nguồn cũ; lưu lại nguồn không đổi vẫn giữ duyệt; sửa ghi chú hủy duyệt và bỏ dấu vết collector của trích đoạn đã sửa.
- Native Windows: worker bị dừng thì JobObject dừng tiến trình con do chính test tạo; parent thoát thì watchdog kết thúc worker. Không dừng tiến trình người dùng hay trình duyệt cá nhân trong test này.
- Native public API/web, kho thử riêng ngoài OneDrive: GitHub Releases 10 tin, TypeSafe Blog 3, Anthropic News 3. Nhập lại cùng 16 kết quả: thêm 0, trùng 16. Không có bản nháp hoặc tác vụ AI phát sinh. Kho thử tạm đã được dọn sau kiểm tra.
- Native Crawl4AI: đọc index và HTML bài thật; có trích đoạn/hash, ngày không nhận diện được để unknown. Kết quả xác nhận khả năng đọc ở thời điểm thử, không kiểm chứng sự thật/pháp lý của bài.
- Native Browser Use: Chromium hồ sơ mới → quan sát 8 controls ở TypeSafe → click control 0 đã quan sát → capture HTML bài → kết thúc, 1 trang. **Không dùng model**, không đăng nhập, không gọi Hermes suy luận.
- Hermes v0.20.0 SDK ngoại tuyến: khóa giả và mạng bị khóa trong tiến trình probe; tạo agent thành công, schema chỉ có `news_browser`. Phát hiện SDK mặc định chuyển plugin thành tool-search bridge; đã tắt indirection đó riêng trong hồ sơ tạm và kiểm tra lại. Không thay đổi cấu hình Hermes cá nhân.
- SDK Hermes phát cảnh báo SQLite3.45.1 trong môi trường riêng của nó và tự dùng journal DELETE cho DB tạm; chưa nâng hoặc sửa môi trường Hermes. Đây là cảnh báo cần cân nhắc trước khi bật lane model, không phải lỗi DB chính Bàn tin.
- Giao diện bản thử cổng8879/dữ liệu riêng: danh mục 7 nguồn, thông báo thiếu kết nối model, nút AI bị khóa. Đã quan sát nguồn web bật; tắt TypeSafe bằng UI chuyển nguồn về tắt và tác vụ chờ thành đã đóng, 3 tin fixture vẫn giữ. Công cụ browser có timeout khi xử lý hộp xác nhận; sau kết nối lại quan sát được trạng thái. Không dùng timeout làm bằng chứng thành công trước khi quan sát lại. Lượt kiểm tra cuối không có console error.
- [Ảnh màn hình kiểm thử nguồn web/hàng đợi](images/nguon-tin-v02-viewport.jpg), dữ liệu minh họa, không phải nguồn/bài chính của người dùng.
- Cú pháp Python/JavaScript đã kiểm tra. Trình cài đã thực hiện các bước tương đương bằng lệnh: tạo venv riêng, pip install hai phiên bản ghim, tải Chromium thành công. Chưa bấm chạy toàn bộ `.cmd` từ Explorer hoặc xác nhận ánh xạ thư mục giữa Explorer/Codex.
- **Chưa khởi động lại/nâng cấp DB chính của người dùng trong lần này**. Người dùng cần lưu phần đang sửa, dừng cửa sổ cũ rồi mở lại để nạp xử lý v0.2; chỉ reload trang không đủ. Migration được kiểm tra trên fixture, không được ghi là đã áp dụng DB chính.

## Không được suy ra từ kết quả trên

- Không có bài nào được gửi tới Facebook, không thử tài khoản, điều kiện kiếm tiền hoặc doanh thu.
- Không đăng nhập hay gửi yêu cầu đến ChatGPT; việc nhận bản nháp từ Plus là thao tác người dùng sẽ làm.
- Nút sao chép có báo thành công trong trình duyệt, nhưng công cụ kiểm tra clipboard của trình duyệt trong ứng dụng trả chuỗi rỗng. Chưa xác nhận được thao tác dán sang ứng dụng khác / clipboard Windows. Đã cung cấp Ctrl+A/Ctrl+C và tải tệp `.txt` dự phòng; cần người dùng thử dán thực tế.
- Kiểm tra nguồn xác nhận RSS/API/web đọc được tại thời điểm thử, không xác minh từng thông tin, giấy phép nội dung hoặc tính khả dụng sản phẩm ở Việt Nam.
- Không có khóa model thật, không chạy suy luận Hermes, không kiểm thử hóa đơn/hạn mức model, chất lượng lựa chọn controls, prompt-injection với model thật hay luồng agent end-to-end. Không coi Browser Use transport hoặc SDK init ngoại tuyến là bằng chứng lane AI đã hoạt động.
- Chưa đo tài nguyên dài ngày, hoàn thành pilot, thử mọi trang, tab popup hay thay đổi giao diện nguồn trong tương lai. Bộ giới hạn không phải sandbox OS hoặc bảo đảm bảo mật tuyệt đối.
- Không phải kiểm thử triển khai công khai, an ninh nhiều người dùng, ổ đĩa hỏng, màn hình nhỏ hoặc pilot 7/30 ngày.

## Tự chạy lại

Trong thư mục mã nguồn:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q newsroom tests
```

Kiểm tra mạng chủ động, đọc RSS/API/web đang bật và lưu vào bản chính (không tự chạy hàng đợi model):

```powershell
python -m newsroom --collect
```

Để thử bằng mắt mà không làm lẫn tin thật: mở `MO-BAN-MINH-HOA.cmd`. Mọi ví dụ trong demo có nhãn minh họa; không dùng để xuất bản.
