# Thu thập nhiều tầng — Bàn tin 0.3

## Nên bắt đầu thế nào?

Giữ cách soạn bài hiện tại: chọn tin → đọc nguồn → chuyển tư liệu sang ChatGPT → biên tập → duyệt → xuất để tự đăng. Bản nâng cấp chỉ mở rộng cách **đưa tư liệu vào**; không giao quyền đăng bài cho agent.

Chưa cần cấu hình Hermes. Hãy dùng RSS và thử một nguồn web trước; không mất phí model ở các tầng này. Dành giờ làm việc mỗi ngày cho một bài có kiểm chứng, không tăng số bài chỉ vì có thêm nguồn.

## Ba tầng hoạt động ra sao?

| Tầng | Dùng để làm gì | Cần bạn làm gì |
| --- | --- | --- |
| RSS/API công khai | Đọc dữ liệu có cấu trúc từ nguồn cố định | Bật nguồn muốn theo dõi |
| Crawl4AI cục bộ | Mở chuyên mục và đọc các bài web công khai | Cài công cụ một lần, bật nguồn web |
| Hermes + Browser Use | Chọn liên kết, cuộn hoặc nút tải thêm khi đọc web thông thường chưa đủ | Kết nối model riêng, đặt hạn mức và xác nhận từng lượt |

Không coi lỗi mạng, lỗi cài đặt, robots.txt từ chối, CAPTCHA, tường phí hoặc trang chặn truy cập là lý do chuyển sang AI. Với các trường hợp đó, đọc hợp lệ rồi dùng **Nhập bài thủ công** để ghi chú thủ công, hoặc bỏ nguồn.

Một tầng chạy thành công không kéo theo tầng tiếp theo: API đọc được thì không dùng browser; Crawl4AI đọc được thì không dùng model. Nguồn nào thuộc loại nào được cấu hình trước trong danh mục, không dò quét cả Internet để tìm RSS/API.

## Bật nguồn mới

Từ bản 0.3 có hai lựa chọn khác nhau:

- **Nguồn tin → Thêm nguồn theo dõi**: tên + URL website/feed + cách đọc + xác nhận. Mặc định tìm RSS/Atom cùng tên miền (URL ban đầu và tối đa 3 ứng viên), có robots/HTTPS ghim IP công khai. Không tự dò API hoặc nới tên miền; nếu không tìm thấy RSS thì báo lỗi để bạn chọn URL RSS khác hoặc chế độ web. Nguồn được thêm/bật trong một giao dịch, kiểm tra trùng URL sau chuẩn hóa; chỉ đưa bài vào Hộp tin khi chạy lượt đọc sau đó. Tối đa 20 nguồn tùy chỉnh.
- **Nhập bài thủ công**: URL của một bài + ghi chú, không tải URL và không tạo nguồn theo dõi. Các mục cũ giữ nguyên, không tự chuyển đổi.

Nguồn web tùy chỉnh cần đường dẫn phạm vi bắt đầu/kết thúc bằng `/`, ví dụ `/news/`. `/` cho phép cả tên miền, hãy giới hạn hẹp khi có thể. Chỉ đọc URL danh sách bạn nhập và các bài trong phạm vi; 3 bài mới/lượt, không gọi model khi thêm nguồn. API có sẵn tiếp tục dùng adapter đã kiểm tra, chưa có giao diện cấu hình API tùy ý.

### Bật nguồn có sẵn

1. Nếu đang dùng bản cũ, **lưu bài** trước. Dừng cửa sổ Bàn tin bằng Ctrl+C, mở lại `MO-BAN-TIN.cmd`, rồi tải lại trang.
2. Vào **Nguồn tin**. Bạn thấy loại nguồn, trạng thái, lần đọc gần nhất và nút bật/tắt.
3. Bật **TypeSafe AI — Blog** hoặc **Anthropic — News** và đọc xác nhận phạm vi. Đây là nguồn của hãng, không phải đánh giá độc lập.
4. Nhấn **Lấy tin mới**. Có thể tiếp tục biên tập trong lúc chờ. Các lượt thu thập từ giao diện không chạy chồng nhau.
5. Xem thông báo nguồn. Tin mới sẽ về **Hộp tin**, có URL, trích đoạn, ngày thu thập, loại ngày và dấu vết phương pháp. **Chưa rõ ngày** có nghĩa là trang chưa cung cấp mốc được bộ đọc nhận diện, không phải tin vừa công bố.
6. Tắt nguồn nếu chưa cần. Các tin và bản nháp đã lưu vẫn giữ nguyên. Tắt nguồn không thu hồi một tác vụ đang chạy; lượt đó vẫn có thể hoàn tất. Nút bật/tắt bị khóa khi giao diện đang thu thập.

Nguồn mới mặc định tắt để bạn chọn trước khi ứng dụng đọc định kỳ. Bốn RSS cũ mặc định bật. **Crawl4AI — GitHub Releases** là nguồn API mẫu về cập nhật công cụ; không phải danh sách tin thịnh hành.

Khi mở, ứng dụng đọc các nguồn đang bật và lặp lại mỗi 2 giờ. Đóng ứng dụng hoặc cho máy ngủ sẽ dừng đọc. Hàng đợi AI không tự chạy theo lịch này.

## Cài công cụ web một lần

1. Trong thư mục mã nguồn, chạy `CAI-CONG-CU-WEB.cmd`.
2. Chờ tải thư viện và Chromium. Cần Internet và dung lượng đĩa; lần đầu có thể mất vài phút. Không yêu cầu đăng nhập, khóa model hoặc Docker/WSL.
3. Khi báo hoàn tất, mở lại Bàn tin. Mục **Nguồn tin** báo có môi trường công cụ riêng; kết quả từng nguồn mới xác nhận lượt đọc thực sự.

Trình cài dùng môi trường riêng `%USERPROFILE%\AppData\Local\BanTinTools\crawl-0.9.5`, ghim `crawl4ai==0.9.5` và `browser-use==0.13.1`. Không cài đè vào môi trường Hermes. Có thể dùng `BANTIN_TOOLS_PYTHON` để chỉ tới `Scripts\python.exe` của môi trường khác do bạn quản lý.

Windows có thể ánh xạ thư mục khi chạy từ Codex đóng gói. Công cụ đã cài trong phiên Codex không bảo đảm hiện ra ở phiên mở từ Explorer. Nếu báo thiếu, chạy trình cài từ chính môi trường bạn dùng để mở Bàn tin; không di chuyển hoặc ghi đè cơ sở dữ liệu đang chạy. Nếu thấy dữ liệu khác giữa hai cách mở, dừng và đối chiếu đường dẫn trước, đừng nhập lại hàng loạt.

## Tác vụ trình duyệt AI: mặc định chưa bật

Khi nguồn thực sự cần điều hướng, **Nguồn tin → Tác vụ trình duyệt cần xem xét** xuất hiện một dòng chờ. Hệ thống không tự chuyển các dòng này thành cuộc gọi model.

- **Chờ xử lý:** chưa chạy model; có thể đóng nếu không cần.
- **Đang chạy:** đã ghi nhận một lượt; không chạy lần thứ hai hoặc hủy giữa chừng từ UI. Tối đa 12 vòng agent, 20 thao tác trình duyệt, 180 giây, 3 bài/lượt.
- **Đã nhận tư liệu:** chỉ nhập tư liệu vào Hộp tin. Chưa tạo, duyệt hoặc đăng bài.
- **Mất dấu:** chưa xác nhận kết thúc; lượt có thể đã dùng hạn mức. Không tự thử lại. Kiểm tra mức sử dụng ở nhà cung cấp, chờ tiến trình dừng, rồi chỉ đóng tác vụ nếu đã hiểu kết quả. Đóng tác vụ không hoàn lại lượt đã dùng.

Một nguồn chỉ có một tác vụ chờ/đang chạy/mất dấu. Lượt đang chạy bị gián đoạn được chuyển thành mất dấu sau 10 phút, không trở lại hàng chờ. Khởi động lại ứng dụng không đặt lại hạn mức 24 giờ.

### Kết nối tùy chọn — chỉ làm khi đã chọn ngân sách

Chưa thực hiện kết nối hoặc lượt model thật trong lần triển khai này. Bạn có thể nhờ trợ lý hỗ trợ bước này sau; **không gửi khóa bí mật vào cuộc trò chuyện**.

Adapter hiện giới hạn **OpenRouter** và bản Hermes đã kiểm tra cục bộ. Cần một model hỗ trợ gọi công cụ. Không tự chọn model, tự tạo tài khoản, dùng đăng nhập Hermes cá nhân hoặc tự chuyển nhà cung cấp khi lỗi.

Trong thư mục dữ liệu Bàn tin thực tế (xem **Cách sử dụng → Dữ liệu ở đâu?**), tạo `browser-connection.json` theo mẫu và điền model bạn đã chọn:

```json
{
  "enabled": true,
  "provider": "openrouter",
  "model": "DIEN-MODEL-ID-DA-CHON",
  "max_jobs_per_day": 1,
  "hermes_root": "C:\\path\\to\\hermes-agent"
}
```

Đường dẫn Hermes trên là vị trí đã tìm thấy ở máy này; máy khác phải thay bằng thư mục có `run_agent.py` và `venv\Scripts\python.exe`. Khi nâng phiên bản Hermes, cần kiểm tra lại cầu nối; không coi cấu hình còn tồn tại là bằng chứng tương thích.

Đặt khóa riêng trong biến môi trường `BANTIN_BROWSER_API_KEY` của tiến trình Bàn tin, hoặc tệp `browser-key.txt` ngay cạnh cấu hình. Tệp này chứa bí mật dạng văn bản: chỉ dùng trên tài khoản Windows riêng, không đặt ở OneDrive/mã nguồn, không chia sẻ hoặc chụp màn hình. Bản sao lưu SQLite của Bàn tin **không chứa** tệp khóa/cấu hình này. Phần mềm chạy cùng tài khoản Windows vẫn có thể đọc chúng; đây không phải két mật khẩu.

Đặt giới hạn tín dụng ở nhà cung cấp trước. `max_jobs_per_day` cho phép 1–3 lượt trong 24 giờ trượt, mặc định đề nghị 1. **Giới hạn lượt/vòng/thời gian không phải trần tiền**; một lượt có thể chứa nhiều yêu cầu và retry bên trong SDK. Chưa có đo lường chi phí hoặc ngắt theo số tiền trong ứng dụng.

Sau khi cấu hình hợp lệ, UI chỉ báo **đủ cấu hình**, không báo đã kiểm chứng model. Để thử thật cần bạn chọn một tác vụ, đọc xác nhận phát sinh phí/hạn mức và bấm **Chạy 1 lượt trình duyệt AI**. Dữ liệu trang công khai và yêu cầu điều hướng được gửi tới nhà cung cấp model đã cấu hình; không phải tới ChatGPT đang mở. Nếu không muốn gửi dữ liệu đó, giữ tầng này tắt.

## Những gì agent được và không được làm

Hermes nhận duy nhất công cụ `news_browser`: đọc, chọn nút/liên kết đã quan sát, cuộn và chụp tư liệu trang. Không nhận công cụ dòng lệnh, đọc tệp, cơ sở dữ liệu, duyệt bài hoặc mạng xã hội. Mỗi lượt dùng hồ sơ tạm mới, không mở Chrome/Edge cá nhân, không dùng cookie/đăng nhập đã lưu.

Browser Use mở Chromium riêng; lớp giới hạn dùng Playwright để chỉ cho thao tác đọc trong chuyên mục đã chọn. Không dùng Browser Use cloud hoặc model riêng của Browser Use. Mã trang vẫn chạy trong Chromium; lớp kiểm soát này **không phải sandbox hệ điều hành** và không bảo đảm mọi website đều tương thích.

Chỉ GET/HEAD, tên miền HTTPS trong danh mục, kiểm tra robots.txt, chặn tài nguyên khác miền, ảnh/media/font, WebSocket và yêu cầu gửi biểu mẫu. Không điều hướng ngoài chuyên mục, đăng nhập, gửi biểu mẫu, mua, tải ảnh, vượt CAPTCHA/tường phí. Trang có chỉ dẫn cho agent được coi là **dữ liệu không tin cậy**.

Bàn tin chỉ nhập HTML thực tế do công cụ trình duyệt chụp, tự trích nội dung và kiểm tra URL/giới hạn; không dùng câu trả lời cuối của model làm bằng chứng trang đã được đọc. Hash ghi nhận đúng trích đoạn thu được, không chứng minh thông tin là thật hoặc nguồn được phép tái sử dụng.

## Giới hạn nội dung và lưu trữ

- Web: tối đa 3 liên kết chưa có dấu vết thu thập mỗi nguồn/lượt, từ tối đa 30 liên kết trong trang chuyên mục. Không duyệt vô hạn hay tải cả kho. API mẫu: tối đa 10 bản phát hành công khai.
- RSS giữ tối đa 1.200 ký tự; API/web tối đa 3.000 ký tự mỗi trích đoạn. HTML được đọc tạm trong tiến trình nhưng không lưu toàn văn vào SQLite.
- Lưu URL, tên nguồn, thời điểm thu thập, ngày đăng/cập nhật nếu nhận diện được, phương pháp, phạm vi trích đoạn và SHA256. Không lấy thời điểm đọc thay ngày công bố.
- Nguồn có dấu vết web đã thu thập sẽ được bỏ qua ở các lượt đọc chuyên mục sau; không theo dõi đầy đủ mọi sửa đổi của bài cũ. RSS/API có thể cập nhật ứng viên; bản nháp giữ ảnh chụp riêng. Bổ sung ghi chú sau khi tự đối chiếu nếu cần cập nhật bài cũ.
- Sửa tiêu đề/liên kết/trích đoạn của nguồn trong bản nháp sẽ bỏ dấu vết tự động của bản đó, gắn nhãn biên tập thủ công và hủy duyệt. Thu thập thêm tin không tự sửa bài đã duyệt.
- Dẫn nguồn và robots.txt cho phép truy cập không đồng nghĩa quyền dịch nguyên bài hoặc dùng ảnh. Bản này hỗ trợ viết tóm tắt/góc nhìn riêng với liên kết; người vận hành vẫn phải kiểm tra quyền và chất lượng.

## Gặp lỗi thì làm gì?

| Hiện tượng | Cách xử lý |
| --- | --- |
| Chưa có Crawl4AI | Chạy trình cài ở trên; RSS/API vẫn dùng được |
| robots/CAPTCHA/tường phí/chặn truy cập | Không thử bằng proxy hoặc AI; nhập ghi chú từ việc đọc hợp lệ hoặc bỏ nguồn |
| Hỏng mạng/công cụ/quá thời gian | Kiểm tra thông báo nguồn và cài đặt; không tự tạo lượt AI để chữa lỗi này |
| Chưa thấy tin mới | Kiểm tra nguồn đã bật, bộ lọc thời gian; tối đa 3 bài/lượt, có thể cần vài lượt để đọc các liên kết khác |
| Có tin nhưng ngày chưa rõ | Tự mở nguồn kiểm tra; không tự coi là mới hôm nay |
| Nút chạy AI bị khóa | Chưa đủ cấu hình hoặc đang có lượt thu thập; không cần bật để tiếp tục soạn thủ công |
| Đã hết lượt trong 24 giờ | Chờ; không hủy tác vụ/khởi động lại để đặt lại lượt |
| Mất dấu | Kiểm tra nhà cung cấp và tiến trình; không bấm chạy lại hàng loạt |
| Có tin cũ nhưng web lỗi | Tin/bài đã lưu vẫn giữ; không xóa cơ sở dữ liệu để sửa lỗi nguồn |

## Tài liệu gốc để bảo trì

- [Crawl4AI — Simple Crawling](https://docs.crawl4ai.com/core/simple-crawling/)
- [Browser Use — mã nguồn](https://github.com/browser-use/browser-use)
- [Hermes — browser tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser)
- [GitHub — Releases API](https://docs.github.com/en/rest/releases/releases)

Các sản phẩm thay đổi theo thời gian; phiên bản công cụ ở trên là bản đã cài và thử ngày 15/10/2026, không phải cam kết tương thích sau nâng cấp.
