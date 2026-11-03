# API bản tin đa kênh — bản mô tả theo mã hiện tại

Tài liệu này mô tả API nội bộ của nhánh phát triển 0.4, chưa phải API công khai hay hợp đồng ổn định. Nguồn đối chiếu: `newsroom/server.py`, `bulletins.py`, `variants.py`, `publications.py` và `social_formats.py`. ID, revision và dữ liệu ví dụ chỉ dùng cho kho thử; không gọi đăng bài lên mạng xã hội.

## Phiên, lỗi và kích thước

- Mở `GET /` để nhận cookie phiên, rồi `GET /api/state` lấy `csrf_token`. Các API dữ liệu cần cookie; POST cần thêm `X-CSRF-Token`, `Origin` hợp lệ và `Content-Type: application/json`. Server ràng buộc Host/Origin vào phiên cục bộ.
- POST yêu cầu JSON object với `Content-Length` xác định, tối đa **128.000 byte** sau mã hóa UTF-8; không nhận `Transfer-Encoding`. Gói tư liệu có giới hạn riêng **65.536 byte** cho toàn bộ văn bản, bao gồm hướng dẫn.
- Lỗi JSON có dạng `{"error":"..."}`. Các mã thường gặp: 400 dữ liệu/điều kiện nghiệp vụ không hợp lệ, 401 thiếu phiên, 403 phiên/CSRF/Origin/Host không hợp lệ, 404 route không tồn tại, 409 xung đột revision hoặc trạng thái, 413 kích thước không hợp lệ, 503 lỗi lưu/đọc. Không coi mọi mã 400 là lỗi trường riêng lẻ.
- Sau mỗi mutation thành công, dùng revision trong phản hồi mới; nếu 409, giữ nội dung đang soạn và tải lại để người dùng đối chiếu. Không tự ghi đè dữ liệu mới.

## Bản tin và mục

| Phương thức và đường dẫn | Đầu vào chính | Kết quả / lưu ý |
| --- | --- | --- |
| `GET /api/bulletins` | — | Danh sách bản tin. |
| `GET /api/bulletins/{id}` | — | Bản tin và `items`, mỗi mục có revision và snapshot nguồn. |
| `GET /api/bulletins/{id}/packet` | — | Object `text` là gói tư liệu; vượt giới hạn trả lỗi, không cắt nội dung. |
| `GET /api/bulletins/{id}/history` | — | Lịch sử bản tin. |
| `GET /api/bulletin-stats` | — | Thống kê bản tin và ghi nhận đa kênh. |
| `POST /api/bulletins` | `article_ids` (1–10 ID nguyên khác nhau), tùy chọn `title`, `edition_date`, `source_selection` | 201 và bản tin mới. `source_selection` là object khóa theo article ID dạng chuỗi; nguồn phải thuộc tin. |
| `POST /api/bulletins/{id}/save` | `revision`; tùy chọn `title`, `edition_date`, `introduction`, `conclusion`, `item_ids` | Trả bản tin. `item_ids` xác định thứ tự đầy đủ các mục hiện có. |
| `POST /api/bulletins/{id}/items` | `revision` và một trong `article_id` hoặc `remove_item_id`; khi thêm có thể gửi `source_selection` | Trả bản tin. Không thêm trùng article; phải giữ ít nhất một mục. |
| `POST /api/bulletins/{id}/items/{item_id}/save` | `bulletin_revision`, revision của mục trong `revision`; các trường cần sửa | Trả toàn bộ bản tin mới, bao gồm revision mới của mục và bản tin. |

Các trường mục có thể gửi gồm `title`, `body`, `angle`, `verification_note`, `verified`, `claims`, `add_source`, `remove_source_id`. `claims` gồm tối đa 10 object `{text, evidence, checked}`. `add_source` gồm `url`, `title`, `summary`; mỗi mục giữ 1–3 nguồn và toàn bản tin tối đa 20 URL nguồn khác nhau. Sửa nội dung hoặc nguồn bỏ xác nhận mục và các xác nhận khẳng định; xác nhận lại sau khi lưu. Không nhầm revision bản tin với revision mục.

## Phiên bản theo kênh

| Phương thức và đường dẫn | Đầu vào chính | Kết quả / lưu ý |
| --- | --- | --- |
| `GET /api/bulletins/{id}/variants` | — | Danh sách phiên bản của bản tin. |
| `POST /api/bulletins/{id}/variants` | `bulletin_revision`, `platform` là `facebook`, `threads` hoặc `x`, `account_label` | Tạo phiên bản nháp riêng; không ghi đè phiên bản khác. |
| `GET /api/variants/{id}` | — | Phiên bản, revision, trạng thái và cờ cần cập nhật. |
| `POST /api/variants/{id}/save` | `revision`, tùy chọn `account_label`, `segments`, `checks` | Lưu và trả phiên bản; khi bản tin gốc đổi cần `adopt_bulletin_revision: true`; bản sao cần đối chiếu nguồn có thể yêu cầu `attribution_reviewed: true`. |
| `POST /api/variants/{id}/preview` | Tùy chọn `segments` | Kết quả renderer và các mục bị lược; không lưu. Phiên bản đã khóa xem bằng bản duyệt lịch sử. |
| `POST /api/variants/{id}/split` | `revision`, tùy chọn `segments` | Đề xuất `segments` và `preview`, không tự lưu. Không chia phiên bản khóa hoặc cần cập nhật. |
| `POST /api/variants/{id}/approve` | `revision` | Kiểm tra nội dung, nguồn, xác nhận và policy rồi tạo snapshot duyệt. |
| `POST /api/variants/{id}/clone` | `revision`, tùy chọn `account_label` | Tạo bản sao chưa duyệt; có thể cần xác nhận lại quan hệ mục/nguồn. |
| `GET /api/variants/{id}/export` | — | Xuất snapshot đã duyệt hợp lệ theo policy hiện hành. |
| `GET /api/variants/{id}/archive` | — | Đọc snapshot duyệt lịch sử; không đồng nghĩa nội dung hợp lệ để đăng theo policy hiện hành. |
| `GET /api/variants/{id}/download` | — | Tệp UTF-8 từ export hợp lệ, các đoạn ngăn bởi `---`. |

Mỗi segment có `text` và `item_ids`; `source_ids` có thể chỉ định nguồn được dùng. Sửa nội dung hoặc đích bỏ checklist và duyệt tương ứng; khi lưu thay đổi, không giả định các giá trị `checks` gửi cùng sẽ được xác nhận. Kiểm tra nội dung và xác nhận checklist ở lượt lưu tiếp theo. Phiên bản đã có ghi nhận bị khóa; muốn sửa hãy tạo bản sao.

## Ghi nhận thủ công và số liệu

| Phương thức và đường dẫn | Đầu vào chính | Kết quả / lưu ý |
| --- | --- | --- |
| `GET /api/variants/{id}/publications` | — | Các ghi nhận của phiên bản. |
| `POST /api/variants/{id}/publications` | `revision`, `position` bắt đầu từ 0, `url`, `idempotency_key`, tùy chọn `reported_at` | Ghi nhận URL do người dùng cung cấp, không gọi nền tảng. Key gồm 8–100 ký tự chữ ASCII, số, `_` hoặc `-`; retry cùng key và payload hợp lệ trả bản ghi cũ, dùng lại key với payload khác trả 409. |
| `POST /api/publications/{id}/corrections` | Revision của **phiên bản** trong `revision`, `reason`, `url` thay thế hoặc chuỗi rỗng để hủy | Ghi sự kiện và trả `corrected_id`, `replacement_id`, `status`; nội dung phiên bản vẫn khóa. |
| `POST /api/publications/{id}/metrics` | `observed_at`, các trường `views`, `likes`, `saves`, `shares`, `followers`, `minutes`, `note` | Giá trị số là số nguyên không âm hoặc `null`; không có số liệu khác với 0. Chỉ ghi cho publication đang hiệu lực. |

Các timestamp người dùng cung cấp phải có múi giờ hợp lệ. URL cần đúng mẫu validator của nền tảng; validator không truy cập URL để chứng minh bài đã được đăng. Sau ghi nhận hoặc đính chính, đọc lại phiên bản để lấy revision mới.

### Phạm vi URL ghi nhận hiện tại

Đây là hành vi đọc từ `normalize_post_url` và `_post_identity` trong `newsroom/publications.py`, không phải danh mục URL chính thức hay đầy đủ của các nền tảng. Mẫu bên dưới dùng dữ liệu giả. URL phải là HTTPS, không có thông tin đăng nhập hoặc cổng khác 443; dấu `/` cuối được bỏ trước khi kiểm tra.

| Kênh | Host và đường dẫn được mã hiện tại chấp nhận | Chuẩn hóa và so trùng |
| --- | --- | --- |
| Facebook | `facebook.com`, `www.facebook.com`, `m.facebook.com`; đường dẫn dạng `/page/posts/123`, `/share/p/abc`, hoặc `/permalink.php`, `/story.php` có `story_fbid` khác rỗng. | Host về `www.facebook.com`; bỏ query trừ `story_fbid` và `id` của hai đường dẫn PHP. So trùng theo đường dẫn không phân biệt hoa thường và query còn lại. |
| Threads | `threads.net`, `www.threads.net`, `threads.com`, `www.threads.com`; dạng `/@user/post/abc`. | Host về `www.threads.com`, bỏ query; so trùng theo mã đoạn cuối. |
| X | `x.com`, `www.x.com`, `twitter.com`, `www.twitter.com`; dạng `/user/status/123`, tên gồm 1–15 chữ ASCII, số hoặc `_`, mã bài là số. | Host về `x.com`, bỏ query; so trùng theo mã bài, kể cả khi tên tài khoản trong URL khác nhau. |

Kiểm tra trùng bao gồm ghi nhận đa kênh đang hiệu lực và URL Facebook legacy mà validator nhận diện được. Hai URL Facebook khác dạng, chẳng hạn `/share/p/...` và `/page/posts/...`, có thể cùng dẫn đến một bài nhưng không được suy ra là trùng; URL legacy ngoài tập mẫu cũng không được đối chiếu. Không tự sửa dữ liệu cũ để xử lý các trường hợp này. Trước khi dùng cần đối soát thủ công, thu thập ví dụ được phép và xác minh alias trên nền tảng; không coi URL hợp lệ theo cú pháp là bằng chứng bài tồn tại hoặc đã đăng.

[Hướng dẫn X về URL bài đăng](https://help.x.com/en/using-x/post-and-moment-url) mô tả cách sao chép liên kết bài; [tài liệu X về Media Studio](https://help.x.com/en/using-x/media-studio-faqs) minh họa dạng `x.com/USERNAME/STATUS/postID`. Các nguồn này chưa xác nhận toàn bộ mẫu, alias hoặc phép so trùng ở trên. Chưa có bằng chứng chính thức đầy đủ cho Facebook và Threads trong lần rà soát này; BASE-03 vẫn mở.

## Giới hạn bằng chứng

Đây là bản đồ route và điều kiện chính đọc từ mã, chưa phải đặc tả đầy đủ mọi trường trả về, tất cả tổ hợp lỗi hoặc hợp đồng đã được người dùng chấp nhận. Bộ đếm Threads là ước lượng; hành vi X thực tế, mọi mẫu URL và emoji mới chưa được xác minh đầy đủ. Xem [kế hoạch](KE-HOACH-NANG-CAP-BAN-TIN-DA-KENH.md) và [bằng chứng kiểm thử](KIEM-THU.md) trước khi dùng để quyết định phát hành.
