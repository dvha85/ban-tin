# Bằng chứng kiểm thử — cập nhật 16/10/2026

## Phần 0.4 đang phát triển (03/11/2026)

- Lần chạy 03/11/2026: `python -B -m unittest discover -s tests` đạt 103/103; `node --test tests/draft-state.test.js` đạt 2/2; `node --check newsroom/static/app.js` đạt. Có test lỗi rollback/restore, snapshot duyệt, URL, số liệu `null`/`0`, HTTP/CSRF và chia đoạn 9 → 10, giữ nguồn, từ chối câu quá dài.
- Kiểm tra thủ công trên ứng dụng qua trình duyệt trong máy, với kho fixture nằm tại thư mục tạm tách khỏi kho vận hành: chọn ba tin, tạo bản tin, lưu và xác nhận một mục, tạo và duyệt một phiên bản X, ghi nhận URL X giả và tải lại trang. Không có bài đăng thật.
- Nút sao chép hiển thị thành công nhưng lần đọc clipboard trong trình duyệt kiểm thử trả về rỗng; **chưa xác nhận nội dung clipboard thực tế**. Chưa kiểm tra đầy đủ bàn phím, fallback clipboard, file tải, restart tiến trình, ba pilot, mọi chính sách ký tự hoặc kho vận hành.
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
