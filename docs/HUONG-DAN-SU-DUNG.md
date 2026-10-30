# Hướng dẫn cho người mới

## 1. Mở, dừng và mở lại

Mở thư mục mã nguồn, nhấp đúp `MO-BAN-TIN.cmd`. Một cửa sổ chạy và một trang trình duyệt sẽ xuất hiện. Đây là ứng dụng của riêng bạn, không cần tài khoản để mở bàn biên tập.

Địa chỉ chính: [http://127.0.0.1:8877/](http://127.0.0.1:8877/). Không gửi địa chỉ này cho người khác: nó chỉ có ý nghĩa trên máy của bạn.

- Giữ cửa sổ chạy mở. Đóng riêng tab trình duyệt không nhất thiết dừng ứng dụng.
- Muốn dừng: lưu bản nháp trước, quay lại cửa sổ chạy và nhấn Ctrl+C hoặc đóng cửa sổ đó.
- Máy tắt / ngủ: ứng dụng không tiếp tục thu thập tin. Mở lại để tiếp tục với dữ liệu đã lưu.
- Bản chính lấy RSS/API/web đang bật khi khởi động và mỗi 2 giờ khi tiến trình còn chạy. Có thể nhấn **Lấy tin mới** bất kỳ lúc nào; các lượt đọc qua giao diện không chạy chồng nhau. Tác vụ AI không tự chạy theo lịch.
- Chỉ đọc những liên kết còn xuất hiện trong feed/API/chuyên mục đã chọn, không bảo đảm bù đầy đủ tin đã bỏ lỡ trong thời gian máy nghỉ.
- Không có tác vụ khởi động cùng Windows hay lịch chạy ẩn được cài đặt.

Nếu thiếu Python trên máy khác, cài Python 3.11 trở lên từ [python.org](https://www.python.org/downloads/windows/) và bật tùy chọn thêm Python vào PATH. Máy đang dùng đã có Python; không cần cài lại để thử bản này.

## 2. Chọn tin trong 10 phút

**Hộp tin** có bộ lọc chủ đề, tìm kiếm và khoảng thời gian. Hệ thống hiển thị tối đa 500 tin gần nhất; cơ sở dữ liệu vẫn giữ các tin cũ. Tin chưa rõ ngày không bị giả thành tin mới; giao diện ghi rõ tình trạng này.

Chọn một tin rồi nhấn **Mở nguồn gốc**. Kiểm tra:

- Đây là thông báo thật, có ngày rõ ràng, hay chỉ là tin đồn?
- Tính năng / sản phẩm đã phát hành hay mới được giới thiệu?
- Có dùng được ở Việt Nam không? Nếu chưa biết, cần ghi rõ chưa biết.
- Bài của mình giúp người đọc hiểu hoặc làm được điều gì?

Điểm tối đa 95 là tổng điểm quy tắc, không phải phần trăm tin đúng. Điểm cao không có nghĩa là chủ đề được quan tâm nhất. Nhóm AI / thiết bị cũng có thể phân loại sai, bạn có thể đổi nhóm khi biên tập.

Nếu nguồn lỗi hoặc có tin khác bạn muốn viết: nhấn **Nhập bài thủ công**, điền URL HTTPS của bài viết, tiêu đề và ghi chú ngắn bạn đã tự đọc. Bài xuất hiện ở **Hộp tin**, không phải **Nguồn tin**. Ứng dụng không tự truy cập URL vừa nhập hoặc theo dõi website đó. Không nhập nội dung riêng tư, toàn văn bài có tường phí hoặc tài liệu bạn không có quyền sử dụng.

### Theo dõi một website mới

1. Vào **Nguồn tin**, nhấn **Thêm nguồn theo dõi**.
2. Điền tên nguồn và URL HTTPS của website hoặc RSS. Ví dụ tên `DEV Community`, URL `https://dev.to/`.
3. Để **Tự tìm RSS/Atom**. Đọc xác nhận rồi đánh dấu đồng ý trước khi **Kiểm tra và thêm nguồn**. Chờ thông báo, không nhấn thêm nhiều lần.
4. Nguồn hiện ngay tại **Nguồn tin** với nhãn **Bạn đã thêm** và nút **Tắt nguồn**. Nhấn **Lấy tin mới** để đọc bài vào Hộp tin. Bước kiểm tra thêm nguồn chỉ kiểm tra RSS/website, không tự tạo bài/bản nháp.
5. Nếu báo đã tồn tại, đóng biểu mẫu và bật nguồn đã có thay vì nhập lại. Nếu không tìm thấy RSS, tìm URL RSS từ chính website hoặc chọn **Đọc web bằng Crawl4AI** và nhập phạm vi, ví dụ `/blog/`. Dùng `/` nghĩa là cả tên miền, không phải chỉ một chuyên mục.

Chỉ nhận HTTPS công khai, không URL chứa mật khẩu/khóa bí mật, IP nội bộ, chuyển hướng hoặc feed sang tên miền khác. Nếu website dùng tên miền RSS khác, tự kiểm tra rồi nhập trực tiếp URL HTTPS của feed đó như một nguồn riêng. Không dùng trình duyệt AI để vượt robots, CAPTCHA, tường phí hay lỗi mạng.

Nguồn mới được bật sau xác nhận, lưu khi mở lại; đọc theo lịch hiện có khi ứng dụng đang chạy. Có tối đa 20 nguồn do bạn thêm. Tắt nguồn không xóa tin hoặc bản nháp; chưa có sửa/xóa nguồn. **Nhập bài thủ công** và **Thêm nguồn theo dõi** không thay thế nhau, cũng không tự chuyển đổi dữ liệu cũ.

Để bật nguồn không có RSS hoặc hiểu tác vụ trình duyệt, xem [Thu thập nhiều tầng](THU-THAP-DA-TANG.md). Không cần cấu hình Hermes để dùng RSS/API và Crawl4AI cục bộ.

## 3. Chuyển sang ChatGPT Plus

Nhấn **Tạo bản nháp**, mở **1. Sang ChatGPT**. Gói tư liệu có nguồn, trích đoạn, mốc thời gian và các yêu cầu chống bịa thông tin, không dịch nguyên bài, không giả trải nghiệm cá nhân.

1. Nhấn **Sao chép sang ChatGPT**.
2. Mở ChatGPT bằng nút bên cạnh hoặc cửa sổ bạn đang dùng, tự đăng nhập Plus.
3. Dán gói tư liệu và gửi yêu cầu.
4. Nếu ChatGPT không mở được nguồn, tự đọc nguồn rồi bổ sung ghi chú; không tin lời khẳng định “đã đọc” khi chưa có bằng chứng.
5. Nếu Plus chạm hạn mức, chờ hoặc tiếp tục biên tập thủ công. Ứng dụng không tự mua tín dụng hoặc chuyển sang API mất phí.

Nếu không dán được sau khi nhấn sao chép: chọn ô tư liệu, nhấn Ctrl+A rồi Ctrl+C, chuyển sang ChatGPT và Ctrl+V. Có phương án chọn và sao chép thủ công ngay trong giao diện.

Không cần đưa mật khẩu, cookie hoặc khóa truy cập ChatGPT vào ứng dụng. Ứng dụng không điều khiển tài khoản hay đọc lịch sử của bạn. Việc bạn dán tư liệu sang ChatGPT là thao tác chủ động gửi dữ liệu đến dịch vụ đó; phần AI không chạy ngoại tuyến trên máy.

## 4. Nhập lại và biên tập trong 25 phút

Ở **2. Biên tập**:

- Điền **Tên Page dự kiến đăng**: tên thương hiệu, không phải yêu cầu liên kết tài khoản cá nhân.
- Chọn nhóm bài để cân đối thử nghiệm 15 bài AI và 15 bài thiết bị / phần mềm.
- Dán riêng tiêu đề và phần bài đăng; không dán toàn bộ bảng kiểm chứng, yêu cầu hay nhận xét của ChatGPT.
- Ghi **Góc nhìn riêng**: ví dụ ai sẽ tiết kiệm công sức, khi nào không nên dùng, điều kiện nào cần kiểm tra.
- Mở **Nguồn tham khảo & ghi chú kiểm chứng** để bổ sung thông tin đã đối chiếu. Có thể lưu tối đa 8 nguồn / bài; liên kết tự bổ sung tại đây không được tải tự động. Nếu sửa trích đoạn tự thu thập, bản sửa được gắn nhãn biên tập thủ công và bỏ hash/phương pháp gốc.
- Nhấn **Lưu bản nháp**. Trình duyệt không tự lưu từng ký tự; luôn lưu trước khi đóng.

Không bịa trải nghiệm “tôi đã dùng” nếu chưa dùng. Cần kiểm tra số liệu, tên sản phẩm, điều kiện phát hành và thời gian. Nếu không xác minh được một thông tin thì bỏ nó hoặc trình bày rõ giới hạn. Ứng dụng chặn duyệt khi phần bài còn dấu `[CẦN KIỂM TRA]` hoặc `[CHƯA XÁC MINH]`, nhưng không thể tự phát hiện mọi thông tin sai.

## 5. Duyệt và tự đăng trong 15 phút

Mở **3. Duyệt & xuất**, đọc lại tên Page, tiêu đề, nội dung và nguồn. Hoàn tất 5 mục kiểm tra rồi nhấn **Duyệt phiên bản này**.

Điều kiện tối thiểu của phần mềm: có tiêu đề, nội dung tối thiểu 80 ký tự, góc nhìn, tên Page, ít nhất một ghi chú nguồn đủ dài và cả 5 xác nhận. Đây chỉ là điều kiện thao tác, không chứng minh bài đủ chất lượng, đủ quyền hay đủ điều kiện kiếm tiền.

Nhấn **Sao chép bài đã duyệt**, chọn **Sao chép nội dung** hoặc **Tải tệp .txt**. Tự mở Facebook, chọn đúng Page và đăng. Kiểm tra định dạng lần cuối.

- Không có nút tự đăng, lịch tự đăng hay kết nối tài khoản Meta.
- Nếu sửa nội dung / nguồn / tên Page trong Bàn tin, duyệt cũ bị hủy, cần kiểm tra lại.
- Nếu bạn sửa trực tiếp trong Facebook, ứng dụng không biết thay đổi đó. Quay lại sửa và duyệt lại để hồ sơ khớp bản thực tế.
- Bản này chỉ lưu bài chữ. Nếu thêm ảnh, tự kiểm tra quyền, nguồn và sự phù hợp của ảnh; việc duyệt bài chữ không phải duyệt ảnh.

Sau khi đã tự đăng, dán URL bài Facebook và nhấn **Ghi nhận tôi đã đăng thủ công**. Việc này chỉ lưu lời xác nhận của bạn, không gửi yêu cầu đến Facebook và không chứng minh bài công khai / kiếm tiền được. Bản nội dung đã ghi nhận đăng không sửa đè được; tạo bản nháp mới từ tin để làm bài mới.

## 6. Theo dõi trong 10 phút

Nhập lượt lưu, chia sẻ, người theo dõi mới quan sát được và số phút chuẩn bị. Ghi cả thời điểm quan sát, ví dụ “sau 24 giờ”. Số liệu không được lấy tự động và không chứng minh quan hệ nhân quả với bài viết.

Thanh 30 bài dùng số bài do bạn ghi nhận đăng trong **30 ngày gần nhất**, không phải lịch cố định đã bắt đầu hay hạn mức được nền tảng bảo đảm. Đừng đánh dấu ví dụ minh họa là bài thật.

## 7. Sao lưu và khôi phục

Mỗi ngày hoặc sau vài bài:

1. Vào **Cách sử dụng → Tạo bản sao lưu**.
2. Sao chép đường dẫn tệp vừa tạo.
3. Mở vị trí đó trong File Explorer, chép **tệp sao lưu** sang một ổ khác hoặc thư mục sao lưu OneDrive.
4. Không di chuyển thư mục dữ liệu đang chạy vào OneDrive, không chỉ chép riêng tệp SQLite đang mở và bỏ qua dữ liệu WAL.

Sao lưu mặc định ở thư mục `backups` bên trong thư mục dữ liệu hiển thị trong giao diện. Bản sao được tạo bằng chức năng sao lưu SQLite rồi kiểm tra toàn vẹn. Không có xóa bản cũ tự động; cần quản lý dung lượng và giữ ít nhất một bản ở nơi khác. Tệp chứa cả lịch sử sửa bài, không được mã hóa: không chia sẻ công khai.

Khôi phục là thao tác ít dùng. Nếu chưa quen, nhờ trợ lý thực hiện cùng. Mở PowerShell trong thư mục mã nguồn và dùng tệp sao lưu thực tế; đích bắt buộc là **thư mục mới chưa tồn tại**, ngoài OneDrive:

```powershell
python -m newsroom --restore "C:\duong-dan\bantin-ban-sao-luu.sqlite3" --data-dir "C:\Users\hadv\AppData\Local\BanTinLocal-KhoiPhuc-Moi"
python -m newsroom --data-dir "C:\Users\hadv\AppData\Local\BanTinLocal-KhoiPhuc-Moi" --port 8879
```

Thay đường dẫn mẫu bằng đường dẫn của bạn, không chạy nguyên ví dụ. Không ghi đè thư mục bản chính. Mở bản khôi phục để kiểm tra các bài trước khi quyết định sử dụng nó; bản chính vẫn được giữ lại.

## 8. Xử lý các trường hợp thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| Trình duyệt không mở / báo mất kết nối | Kiểm tra cửa sổ chạy còn mở; mở lại `MO-BAN-TIN.cmd`, vào địa chỉ 8877. |
| Báo cổng đang dùng | Có thể ứng dụng đã chạy; thử mở địa chỉ 8877, không chạy thêm nhiều cửa sổ. Nếu đó là phần mềm khác, nhờ hỗ trợ đổi cổng. |
| Phiên hết hạn sau khi khởi động lại | Giữ / sao chép phần chưa lưu trước, rồi tải lại trang. Không có tự phục hồi chữ chưa lưu. |
| Nguồn lỗi | Xem mục **Nguồn tin**, thử lại sau hoặc nhập URL và ghi chú thủ công. Dữ liệu đã có không bị xóa. |
| Không thấy tin cũ | Đổi khoảng thời gian sang **Tất cả**; danh sách vẫn giới hạn 500 tin gần nhất. |
| Bản duyệt bị hủy | Có thay đổi nội dung, nguồn, Page hoặc xác nhận kiểm tra; lưu và duyệt lại. |
| Bài thay đổi ở cửa sổ khác | Sao chép phần đang sửa ra nơi riêng, tải lại bài rồi ghép thay đổi. Không cố ghi đè bản cũ. |
| Không sao chép được | Dùng Ctrl+A / Ctrl+C trong ô tư liệu hoặc ô bài đã duyệt; với bài duyệt còn có tải `.txt`. |
| RSS chỉ có mô tả ảnh / “TBD” | Đọc bài gốc và bổ sung ghi chú; không để AI suy diễn thành tin. |
| Thư mục dữ liệu báo không hợp lệ | Không dùng OneDrive hoặc ổ mạng cho dữ liệu hoạt động. Bỏ tùy chọn thư mục riêng để dùng mặc định. |

Không sửa / xóa cơ sở dữ liệu trực tiếp để bỏ qua bước duyệt. Không mở máy chủ này ra Internet. Các chương trình khác chạy dưới cùng tài khoản Windows vẫn có thể đọc dữ liệu; đây không phải ứng dụng bảo mật cho nhiều người dùng.
