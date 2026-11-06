# API bản tin đa kênh — bản mô tả theo mã hiện tại

Tài liệu này mô tả API nội bộ của nhánh phát triển 0.4, chưa phải API công khai hay hợp đồng ổn định. Nguồn đối chiếu: `newsroom/server.py`, `bulletins.py`, `variants.py`, `publications.py` và `social_formats.py`. ID, revision và dữ liệu ví dụ chỉ dùng cho kho thử; không gọi đăng bài lên mạng xã hội.

## Phiên, lỗi và kích thước

- Mở `GET /` để nhận cookie phiên, rồi `GET /api/state` lấy `csrf_token`. Các API dữ liệu cần cookie; POST cần thêm `X-CSRF-Token`, `Origin` hợp lệ và `Content-Type: application/json`. Server ràng buộc Host/Origin vào phiên cục bộ.
- Kiểm tra phiên và CSRF dùng cùng đường dẫn đã phân tích với bộ định tuyến, kể cả khi HTTP request target là URL đầy đủ. Target không phân tích được trả 400; URL đầy đủ không thay thế kiểm tra Host, cookie hoặc Origin.
- POST yêu cầu JSON object với `Content-Length` xác định, tối đa **128.000 byte** sau mã hóa UTF-8; không nhận `Transfer-Encoding`. Gói tư liệu có giới hạn riêng **65.536 byte** cho toàn bộ văn bản, bao gồm hướng dẫn.
- Nếu kết nối kết thúc trước khi nhận đủ số byte đã khai báo, POST trả 400 và không thực hiện thao tác, kể cả phần đã nhận là JSON hoàn chỉnh. Nếu hết thời gian chờ khi đọc, yêu cầu cũng bị từ chối; phản hồi có thể không tới được client đã ngắt kết nối.
- ID số trên đường dẫn phải gồm tối đa 19 chữ số ASCII và không vượt `9223372036854775807`. Route bản tin, phiên bản, ghi nhận và bản nháp từ chối ID sai bằng 404; route tác vụ thu thập trả 400. Quy tắc này không xác nhận ID có tồn tại.
- JSON lồng vượt khả năng giải mã của Python được từ chối bằng HTTP 400 và không thực thi thao tác; độ sâu tối đa phụ thuộc runtime, không phải giới hạn cố định của API.
- POST từ chối các token không thuộc JSON `NaN`, `Infinity`, `-Infinity` và số thực vượt phạm vi hữu hạn của runtime bằng HTTP 400 trước khi thực thi; các từ này trong chuỗi văn bản vẫn hợp lệ.
- URL nhập mới không được chứa userinfo ở phần authority, kể cả username/mật khẩu rỗng như `https://@example.com/`; ký tự `@` trong đường dẫn hoặc query không bị cấm vì lý do này. Bộ kiểm tra dùng chung cho nguồn và URL ghi nhận. Không tự viết lại dữ liệu đã lưu; test ghi nhận phạm vi URL giả đã thử tại `KIEM-THU.md`.
- Lỗi JSON có dạng `{"error":"..."}`. Các mã thường gặp: 400 dữ liệu/điều kiện nghiệp vụ không hợp lệ, 401 thiếu phiên, 403 phiên/CSRF/Origin/Host không hợp lệ, 404 route không tồn tại, 409 xung đột revision hoặc trạng thái, 413 kích thước không hợp lệ, 503 lỗi lưu/đọc. Không coi mọi mã 400 là lỗi trường riêng lẻ.
- Sau mỗi mutation thành công, dùng revision trong phản hồi mới. Nếu 409, giữ trang và nội dung đang soạn; mở bản ghi hiện tại ở thẻ khác để đối chiếu, hoặc sao chép nội dung ra nơi an toàn trước khi tải lại. Không tự ghi đè dữ liệu mới. Khi kết quả yêu cầu trước không rõ, đối chiếu trạng thái/lịch sử trước khi thử lại; riêng retry có khóa phải giữ nguyên payload và khóa theo hợp đồng tương ứng.
- Riêng 409 do URL đã được ghi nhận có thêm `target`: `{kind: "publication", bulletin_id, variant_id, publication_id, position}` (vị trí từ 0) hoặc `{kind: "legacy_draft", draft_id}`. Trường `error` vẫn có mô tả để client cũ sử dụng. Các 409 khác không nhất thiết có `target`; dữ liệu này chỉ xác định bản ghi nội bộ, không xác minh bài trên nền tảng.

## Bản tin và mục

| Phương thức và đường dẫn | Đầu vào chính | Kết quả / lưu ý |
| --- | --- | --- |
| `GET /api/bulletins` | — | Danh sách bản tin. |
| `GET /api/bulletins/{id}` | — | Bản tin và `items`, mỗi mục có revision và snapshot nguồn. |
| `GET /api/bulletins/{id}/packet` | — | Object gồm `text` là gói tư liệu và `bulletin_revision` của chính bản tin trong gói; vượt giới hạn trả lỗi, không cắt nội dung. |
| `GET /api/bulletins/{id}/history` | — | Lịch sử bản tin. |
| `GET /api/bulletin-stats` | — | Thống kê bản tin và ghi nhận đa kênh. |
| `GET /api/legacy-publication-duplicates` | — | Mảng nhóm `{match, drafts}` đối soát bài cũ; mỗi draft có `id`, `url` gốc. `match` là `recognized` hoặc `exact`; chỉ đọc, không sửa dữ liệu. |
| `POST /api/bulletins` | `article_ids` (1–10 ID nguyên khác nhau), tùy chọn `title`, `edition_date`, `source_selection` | 201 và bản tin mới. `source_selection` là object khóa theo article ID dạng chuỗi; nguồn phải thuộc tin. |
| `POST /api/bulletins/{id}/archive` | `revision`, `archive_revision`, `archived` boolean | Lưu trữ khi `true`, khôi phục khi `false`; trả bản tin. `archived` hoặc `archive_revision` sai kiểu trả 400; `revision` nội dung sai kiểu hoặc không khớp và `archive_revision` cũ trả 409. |
| `POST /api/bulletins/{id}/save` | `revision`; tùy chọn `title`, `edition_date`, `introduction`, `conclusion`, `item_ids` | Trả bản tin. `item_ids` xác định thứ tự đầy đủ các mục hiện có. |
| `POST /api/bulletins/{id}/items` | `revision` và một trong `article_id` hoặc `remove_item_id`; khi thêm có thể gửi `source_selection` | Trả bản tin. Không thêm trùng article; phải giữ ít nhất một mục. |
| `POST /api/bulletins/{id}/items/{item_id}/save` | `bulletin_revision`, revision của mục trong `revision`; các trường cần sửa | Trả toàn bộ bản tin mới, bao gồm revision mới của mục và bản tin. |

Danh sách và chi tiết bản tin trả thêm `archived` (boolean) và `archive_revision` (số nguyên; 0 nếu chưa đổi trạng thái). API danh sách vẫn trả cả bản tin lưu trữ; giao diện ẩn theo cờ trừ khi người dùng chọn hiện. Lưu trữ/khôi phục là thao tác tổ chức, không đổi revision nội dung, bản duyệt hay thống kê và không khóa chỉnh sửa. Gửi cùng trạng thái với `archive_revision` hiện tại là no-op; sau phản hồi chưa rõ phải đọc lại trước khi thử lại. Mã cũ không biết lọc cờ lưu trữ.

Giao diện so sánh `bulletin_revision` của gói với bản tin đang hiển thị và kiểm tra thay đổi chưa lưu, chuyển bản tin hoặc thay đổi kho trong khi chờ; nếu không khớp thì không sao chép. Đây là kiểm tra tại lúc nhận phản hồi, không ngăn bản tin thay đổi ngay sau đó. Client cũ vẫn có thể đọc `text` và phải tự đối chiếu revision nếu cần.

Nếu clipboard bị từ chối, nút thử sao chép trong hộp thủ công lấy và đối chiếu lại gói; thao tác Ctrl+C trực tiếp trong ô không kiểm tra revision. Khi bản tin có thể đã thay đổi, đóng hộp và đối chiếu trước khi dùng nội dung.

Các trường mục có thể gửi gồm `title`, `body`, `angle`, `verification_note`, `verified`, `claims`, `add_source`, `remove_source_id`. `claims` gồm tối đa 10 object `{text, evidence, checked}`. `add_source` gồm `url`, `title`, `summary`; mỗi mục giữ 1–3 nguồn và toàn bản tin tối đa 20 URL nguồn khác nhau. Sửa nội dung hoặc nguồn bỏ xác nhận mục và các xác nhận khẳng định; xác nhận lại sau khi lưu. Không nhầm revision bản tin với revision mục.

Các giới hạn dưới đây được đối chiếu với `create_bulletin`, `save_bulletin` và `save_bulletin_item` trong `newsroom/bulletins.py`. Với những trường văn bản này, server kiểm tra độ dài chuỗi Python và ký tự NUL trước khi bỏ khoảng trắng đầu/cuối; đây là giới hạn của ứng dụng, không phải giới hạn byte UTF-8 hay của nền tảng.

| Nhóm | Trường và giới hạn ký tự tối đa |
| --- | --- |
| Bản tin | `title`: 180; `introduction`, `conclusion`: 4.000 mỗi trường; `edition_date`: 10, đồng thời phải đúng ngày `YYYY-MM-DD`. |
| Mục | `title`: 300; `body`: 4.000; `angle`: 1.000; `verification_note`: 3.000. `verified` nếu gửi phải là boolean. |
| Khẳng định | Tối đa 10; mỗi `text`: 500 và không rỗng sau khi bỏ khoảng trắng; `evidence`: 1.000; `checked` phải là boolean. Để duyệt, khẳng định của mục được sử dụng còn phải có bằng chứng và được xác nhận. |
| Nguồn thêm thủ công | `title`: 300; `summary`: 3.000; `url` phải qua kiểm tra URL HTTPS và thuộc giới hạn URL của ứng dụng. |

Khi tạo bản tin, `source_selection` là object có khóa là biểu diễn thập phân chính xác của ID tin trong `article_ids`, giá trị là mảng URL của tin đó. Khóa không thuộc danh sách đã chọn, khóa viết khác biểu diễn ID hoặc giá trị không phải mảng (kể cả `null`) bị từ chối. Có thể bỏ khóa của một tin để dùng nguồn có sẵn của tin đó. Khi thêm một tin qua `/items` hoặc sao chép bài cũ qua `/copy-bulletin`, trường cùng tên nếu được gửi phải là mảng URL trực tiếp; `null` bị từ chối. Nếu bỏ trường lựa chọn nguồn, server dùng các nguồn có sẵn và vẫn yêu cầu 1–3 nguồn. Việc gửi lựa chọn sai hoặc vượt giới hạn bị từ chối; không mặc định chọn lại.

## Phiên bản theo kênh

| Phương thức và đường dẫn | Đầu vào chính | Kết quả / lưu ý |
| --- | --- | --- |
| `GET /api/bulletins/{id}/variants` | — | Danh sách phiên bản của bản tin. |
| `POST /api/bulletins/{id}/variants` | `bulletin_revision`, `platform` là chuỗi `facebook`, `threads` hoặc `x`, `account_label` | Tạo phiên bản nháp riêng; không ghi đè phiên bản khác. Kiểu hoặc tên nền tảng không hợp lệ trả 400 và không tạo bản ghi. |
| `GET /api/variants/{id}` | — | Phiên bản, revision, trạng thái và cờ cần cập nhật. |
| `POST /api/variants/{id}/save` | `revision`, tùy chọn `expected_bulletin_revision`, `account_label`, `segments`, `checks` | Lưu và trả phiên bản; khi bản tin gốc đổi cần `adopt_bulletin_revision: true`; bản sao cần đối chiếu nguồn có thể yêu cầu `attribution_reviewed: true`. |
| `POST /api/variants/{id}/preview` | Tùy chọn `segments` | Kết quả renderer và các mục bị lược; không lưu. Phiên bản đã khóa xem bằng bản duyệt lịch sử. |
| `POST /api/variants/{id}/split` | `revision`, tùy chọn `expected_bulletin_revision`, `segments` | Đề xuất `segments` và `preview`, không tự lưu. Không chia phiên bản khóa hoặc cần cập nhật. |
| `POST /api/variants/{id}/approve` | `revision`, tùy chọn `expected_bulletin_revision` | Kiểm tra nội dung, nguồn, xác nhận và policy rồi tạo snapshot duyệt. |
| `POST /api/variants/{id}/clone` | `revision`, tùy chọn `expected_bulletin_revision`, `account_label` | Tạo bản sao chưa duyệt; có thể cần xác nhận lại quan hệ mục/nguồn. |
| `GET /api/variants/{id}/export` | — | Xuất snapshot đã duyệt hợp lệ theo policy hiện hành. |
| `GET /api/variants/{id}/archive` | — | Đọc snapshot duyệt lịch sử; không đồng nghĩa nội dung hợp lệ để đăng theo policy hiện hành. |
| `GET /api/variants/{id}/download` | — | Tệp UTF-8 từ export hợp lệ, các đoạn ngăn bởi `---`. |

Mỗi segment có `text` và `item_ids`; `source_ids` có thể chỉ định nguồn được dùng. Sửa nội dung hoặc đích bỏ checklist và duyệt tương ứng; khi lưu thay đổi, không giả định các giá trị `checks` gửi cùng sẽ được xác nhận. Kiểm tra nội dung và xác nhận checklist ở lượt lưu tiếp theo. Phiên bản đã có ghi nhận bị khóa; muốn sửa hãy tạo bản sao.

Chi tiết đầu vào đối chiếu với `save_variant` và `render_segments`:

- `account_label` là chuỗi tối đa 120 ký tự trước khi bỏ khoảng trắng; khi duyệt phải có tên khác rỗng.
- `segments` là mảng từ 1 đến 20 object; Facebook chỉ nhận một đoạn. Mỗi `text` là chuỗi tối đa 12.000 ký tự, không chứa NUL. Khi lưu có thể để nội dung trống, nhưng duyệt yêu cầu mọi đoạn có nội dung và đầu ra đầy đủ nằm trong giới hạn của policy.
- Mỗi `item_ids` là mảng không rỗng gồm ID nguyên khác nhau, thuộc bản tin. Nếu gửi `source_ids`, đây là mảng ID nguồn dạng chuỗi, không trùng, thuộc các mục đã chọn và có ít nhất một nguồn cho mỗi mục. Nếu bỏ hoặc gửi `null`, renderer dùng mọi nguồn của các mục đó.
- Khi không có thay đổi nội dung, `checks` nếu gửi phải là object; năm khóa được xác nhận chỉ khi giá trị là boolean `true`, khóa thiếu hoặc giá trị khác trở thành `false`. Khi nội dung, đích, bản tin gốc hoặc policy thay đổi, server bỏ cả năm xác nhận và không dùng các giá trị `checks` gửi cùng. Nếu trạng thái và checklist không đổi, lưu trả phiên bản hiện có mà không tăng revision.
- `revision` phải là số nguyên khớp revision hiện tại; sai hoặc thiếu trả 409. Sau thay đổi bản tin gốc cần xác nhận `adopt_bulletin_revision: true`; nếu bản sao yêu cầu đối chiếu nguồn thì cần `attribution_reviewed: true`. Đây là hợp đồng theo mã hiện tại, chưa chứng minh mọi tổ hợp qua HTTP.
- `expected_bulletin_revision`, nếu gửi khi lưu, chia, duyệt hoặc tạo bản sao, phải là số nguyên khớp revision của bản tin hiện tại; nếu sai kiểu hoặc không khớp, server trả 409. Giao diện gửi revision của bản tin đang hiển thị để tránh thao tác dựa trên tư liệu cũ. Trường này vẫn tùy chọn để tương thích client cũ; client bỏ trường không có bảo vệ bổ sung này và phải tự đối chiếu bản tin.

Test HTTP `test_variant_save_contract_over_http` kiểm tra riêng reset checklist khi sửa, xác nhận lại ở lượt sau, lưu không đổi, nguồn rỗng/không thuộc mục và revision cũ. Các trường hợp bị từ chối giữ nguyên phiên bản trên kho thử; test này không bao phủ toàn bộ tổ hợp hoặc giao diện trình duyệt.

Test HTTP `test_preview_and_split_response_contract_over_http` đối chiếu tên các trường của preview và split với một đoạn Threads giả, kiểm tra revision và mục bị lược, so sánh kết quả renderer và xác nhận bản tin, phiên bản, lịch sử không đổi. Test không bao phủ mọi cách chia hoặc mọi trường hợp lỗi.

Khi duyệt mới, nguồn được chọn mà có `excerpt_hash` phải khớp SHA-256 của `summary` UTF-8; sai lệch trả 400, nêu thứ tự mục và nguồn trong bản tin, không tạo bản duyệt. Người biên tập cần đối chiếu nguồn, thêm nguồn chính xác và bỏ nguồn sai rồi kiểm tra lại. Mỗi mục phải giữ ít nhất một nguồn; nếu nguồn sai là nguồn duy nhất, cần thêm nguồn đối chiếu phù hợp trước khi bỏ. Khi cần nhập lại cùng URL, bỏ nguồn cũ trước rồi thêm lại URL và kiểm chứng lại mục. Nguồn không có hash vẫn cần kiểm chứng thủ công; hash khớp chỉ chứng minh trích đoạn khớp dấu vết lưu, không chứng minh tính xác thực. Bản duyệt lịch sử không được tự sửa hoặc rà soát lại bởi cổng này.

## Ghi nhận thủ công và số liệu

| Phương thức và đường dẫn | Đầu vào chính | Kết quả / lưu ý |
| --- | --- | --- |
| `GET /api/variants/{id}/publications` | — | Các ghi nhận của phiên bản. |
| `POST /api/variants/{id}/publications` | `revision`, `position` bắt đầu từ 0, `url`, `idempotency_key`, tùy chọn `reported_at` | Ghi nhận URL do người dùng cung cấp, không gọi nền tảng. Key gồm 8–100 ký tự chữ ASCII, số, `_` hoặc `-`; retry cùng key và payload hợp lệ trả bản ghi cũ, dùng lại key với payload khác trả 409. |
| `POST /api/publications/{id}/corrections` | Revision của **phiên bản** trong `revision`, `reason`, `url` thay thế hoặc chuỗi rỗng để hủy | Ghi sự kiện và trả `corrected_id`, `replacement_id`, `status`; nội dung phiên bản vẫn khóa. Bỏ trường `url` cũng được hiểu là hủy theo hợp đồng cũ; nếu có trường này, nó phải là chuỗi, `null` và các kiểu khác bị từ chối. |
| `POST /api/publications/{id}/metrics` | `observed_at`, các trường `views`, `likes`, `saves`, `shares`, `followers`, `minutes`, `note`; thêm tùy chọn `replies`, `reposts`, `quotes` | Giá trị số là số nguyên từ 0 đến 1.000.000.000 hoặc `null`; không có số liệu khác với 0. Ba trường mới chỉ xuất hiện trong payload/phản hồi nếu được gửi; payload cũ giữ nguyên. Chỉ ghi cho publication đang hiệu lực. |

Khóa ghi nhận URL có phạm vi **toàn kho**, không riêng một phiên bản. Retry cùng khóa đối chiếu phiên bản, vị trí, URL đã chuẩn hóa và thời điểm đăng đã chuẩn hóa; revision không nằm trong dữ liệu đối chiếu retry. Do đó một khóa đã dùng cho phiên bản khác trả 409, kể cả khi bản ghi cũ đã bị hủy. Trường hợp cùng khóa và dữ liệu ghi nhận trả lại bản ghi cũ, cần kiểm tra `active` và lịch sử trước khi kết luận bản ghi còn hiệu lực.

Các timestamp người dùng cung cấp phải có múi giờ hợp lệ. URL cần đúng mẫu validator của nền tảng; validator không truy cập URL để chứng minh bài đã được đăng. Sau ghi nhận hoặc đính chính, đọc lại phiên bản để lấy revision mới.

Khóa của bản ghi thay thế sau đính chính do server tạo và dùng dấu `:` để tách khỏi tập khóa client được phép gửi. Đây là chi tiết nội bộ, không dùng để gửi retry ghi nhận mới. Bản ghi đính chính cũ vẫn giữ nguyên khóa đã lưu.

`reported_at` và `observed_at` mới được chuẩn hóa về UTC trước khi lưu; UI hiển thị theo giờ Việt Nam. Bản ghi tạo trước thay đổi có thể giữ offset gốc và không được viết lại. Retry cùng key so sánh thời điểm sau quy đổi UTC, kể cả bản cũ; phản hồi retry giữ nguyên timestamp đã lưu. Thời điểm vượt phạm vi biểu diễn sau quy đổi bị từ chối.

Số liệu có thể gửi thêm `idempotency_key` gồm 8–100 ký tự ASCII chữ, số, `_` hoặc `-`, phạm vi theo từng publication. Cùng key và dữ liệu đã chuẩn hóa trả lại kết quả cũ kể cả sau khi publication bị hủy; cùng key với dữ liệu khác trả 409. Lượt ghi mới vẫn yêu cầu publication hiệu lực. Key được lưu trong chuỗi JSON `payload` dưới tên `_idempotency_key` và không có trong phản hồi ghi; client cũ không gửi key vẫn hoạt động như trước, không được bảo đảm chống trùng. Giao diện chỉ giữ key trong trang đang mở: sau tải lại hoặc sửa dữ liệu cần đối chiếu lịch sử nếu kết quả trước đó không rõ.

Test HTTP `test_publication_fields_reject_invalid_input_without_partial_writes` đối chiếu một phiên bản X đã duyệt: đầu vào sai của ghi nhận, đính chính và chín trường số liệu trả 400; revision sai trả 409. Sau từng yêu cầu, test so lại bản tin, phiên bản, publication kèm sự kiện/số liệu, lịch sử và thống kê. Đây là tập trường hợp trên kho giả, không khẳng định mọi payload hay mọi nền tảng đã được kiểm tra.

### Phạm vi URL ghi nhận hiện tại

Đây là hành vi đọc từ `normalize_post_url` và `_post_identity` trong `newsroom/publications.py`, không phải danh mục URL chính thức hay đầy đủ của các nền tảng. Mẫu bên dưới dùng dữ liệu giả. URL phải là HTTPS, không có thông tin đăng nhập hoặc cổng khác 443; dấu `/` cuối được bỏ trước khi kiểm tra.

| Kênh | Host và đường dẫn được mã hiện tại chấp nhận | Chuẩn hóa và so trùng |
| --- | --- | --- |
| Facebook | `facebook.com`, `www.facebook.com`, `m.facebook.com`; đường dẫn dạng `/page/posts/123`, `/share/p/abc`, hoặc `/permalink.php`, `/story.php` có `story_fbid` khác rỗng. | Host về `www.facebook.com`; bỏ query trừ `story_fbid` và `id` của hai đường dẫn PHP. So trùng theo đường dẫn không phân biệt hoa thường và query còn lại. |
| Threads | `threads.net`, `www.threads.net`, `threads.com`, `www.threads.com`; dạng `/@user/post/abc` hoặc `/t/abc`. Với `/t/`, đoạn mã chỉ gồm chữ ASCII, số, `_`, `-`; dạng `/@user/post/...` hiện chấp nhận mọi đoạn không rỗng không chứa dấu `/` trực tiếp, kể cả chuỗi mã hóa phần trăm như `a%2Fb`. | Host về `www.threads.com`, bỏ query. Khi so trùng shortcode, giải mã một lần `%XX` cho chữ ASCII, số và `-._~`; giữ nguyên mã hóa ký tự dành riêng như `%2F`, `%25` và phân biệt hoa/thường. URL lưu giữ nguyên cách biểu diễn đường dẫn. |
| X | `x.com`, `www.x.com`, `twitter.com`, `www.twitter.com`; dạng `/user/status/123`, tên gồm 1–15 chữ ASCII, số hoặc `_`, mã bài là số. | Host về `x.com`, bỏ query; so trùng theo mã bài, kể cả khi tên tài khoản trong URL khác nhau. |

Kiểm tra trùng bao gồm ghi nhận đa kênh đang hiệu lực và URL Facebook legacy mà validator nhận diện được. Hai URL Facebook khác dạng, chẳng hạn `/share/p/...` và `/page/posts/...`, có thể cùng dẫn đến một bài nhưng không được suy ra là trùng; URL legacy ngoài tập mẫu cũng không được đối chiếu. Không tự sửa dữ liệu cũ để xử lý các trường hợp này. Trước khi dùng cần đối soát thủ công, thu thập ví dụ được phép và xác minh alias trên nền tảng; không coi URL hợp lệ theo cú pháp là bằng chứng bài tồn tại hoặc đã đăng.

Đặc biệt, mẫu Threads đầy đủ hiện rộng hơn mẫu `/t/`; một URL được chấp nhận có thể không phải URL bài hợp lệ trên Meta. Việc so trùng sau giải mã nhóm ký tự không dành riêng là suy luận theo [RFC 3986, mục 2.3 và 6.2.2.2](https://www.rfc-editor.org/rfc/rfc3986); không chứng minh Meta chấp nhận từng URL hoặc shortcode luôn duy nhất. Không giải mã ký tự dành riêng, mã hóa nhiều lần hoặc các dạng khác. Cần kiểm tra thủ công trên nền tảng. Các bản ghi cũ không được viết lại hoặc tự hợp nhất; nếu chúng đã trùng, cần đối soát thủ công. Cùng khóa retry vẫn phải gửi đúng URL đã chuẩn hóa như lần đầu; đổi cách mã hóa có thể bị coi là payload khác.

Danh sách đối soát legacy riêng còn nhóm các URL ngoài validator khi host Facebook được nhận diện và đường dẫn/query giống nhau sau chuẩn hóa; không đồng nghĩa cơ chế chặn ghi nhận mới đã nhận diện các dạng này. URL không hợp lệ hoặc khác host được bỏ qua. Các alias khác dạng, query có ý nghĩa chưa rõ hoặc liên kết rút gọn có thể không được phát hiện.

[Hướng dẫn X về URL bài đăng](https://help.x.com/en/using-x/post-and-moment-url) mô tả cách sao chép liên kết bài; [tài liệu X về Media Studio](https://help.x.com/en/using-x/media-studio-faqs) minh họa dạng `x.com/USERNAME/STATUS/postID`. [Meta Embeds](https://github.com/meta/meta-embeds-for-wordpress/blob/main/README.md) liệt kê hai dạng Threads `/@user/post/{shortcode}` và `/t/{shortcode}`, hỗ trợ hai tên miền và minh họa Facebook `/{user}/posts/{id}`; [Meta Newsroom](https://about.fb.com/news/2025/04/new-features-threads-web-experience/) mô tả việc chuyển Threads.net sang Threads.com. Đây là tài liệu về định dạng cho nhúng và tên miền, chưa chứng minh mọi URL hợp lệ, tính duy nhất của shortcode trên mọi ngữ cảnh hoặc bài có tồn tại; quy tắc so trùng theo shortcode là cách đối chiếu nội bộ. Chưa có bằng chứng đầy đủ cho mọi dạng Facebook/Threads; BASE-03 vẫn mở.

## Cấu trúc phản hồi thường dùng

Các trường dưới đây mô tả mã hiện tại, không phải cam kết tương thích về sau. Các đối tượng danh sách là mảng JSON; các ID và revision là số nguyên. Không suy diễn một bản ghi publication là bài tồn tại trên nền tảng.

| Phản hồi | Trường được trả về |
| --- | --- |
| `GET /api/bulletins` | Mỗi phần tử có `id`, `revision`, `title`, `edition_date`, `created_at`, `updated_at`, `item_count`, `archived`, `archive_revision`. |
| Chi tiết bản tin và mutation trả bản tin | Có `id`, `revision`, `title`, `introduction`, `conclusion`, `edition_date`, `created_at`, `updated_at`, `archived`, `archive_revision`, `items`. Mỗi item có `id`, `bulletin_id`, `article_id` (có thể `null`), `position` bắt đầu từ 0, `revision`, cùng các trường `title`, `body`, `angle`, `verification_note`, `verified`, `sources`, `claims`. |
| Phiên bản | Có `id`, `bulletin_id`, `platform`, `account_label`, `revision`, `bulletin_revision`, `status`, `approval_id`, `locked_at`, `created_at`, `updated_at`, `segments`, `checks`, `needs_update`, `policy_stale`, `publication_progress`. `approval_id` và `locked_at` có thể `null`; `publication_progress` là `null` hoặc `{active, total}`. Bản sao có thể có thêm `attribution_review_required`. |
| Preview | Có `platform`, `policy_version`, `renderer_version`, `posts`, `valid`, `warning`; API preview bổ sung `needs_update`, `bulletin_revision` của bản tin dùng để dựng, `omitted_item_ids`. Mỗi post có `position`, `text`, `body`, `item_ids`, `source_ids`, `urls`, `length`, `limit`, `valid`. `text` là đầu ra đầy đủ đã gồm số thứ tự và nguồn. |
| Split | `{segments, preview}`; `preview` là kết quả renderer và không có ba trường `needs_update`, `bulletin_revision`, `omitted_item_ids` bổ sung riêng của API preview. Kết quả chưa được lưu. |
| Export | `{approval_id, platform, account_label, policy_version, archive, posts}` với `posts` là mảng chuỗi. Archive bổ sung `items`, `rendered_posts`, `checks`; chỉ download mới trả văn bản thuần. |
| Danh sách publication | Mỗi phần tử có các trường bản ghi gồm `id`, `variant_id`, `approval_id`, `position`, `url`, `active` (số `0` hoặc `1`), `reported_at` (có thể `null`), `recorded_at`, `idempotency_key`, `request_hash`, kèm `events` và `metrics`. Trường `payload` của từng event/metric là **chuỗi JSON**, không phải object đã giải mã. API ghi nhận trả bản ghi publication không kèm hai mảng này. |
| Thống kê | `{bulletins, variants, recorded_posts, recorded_bulletins}`; hai số `recorded_*` chỉ tính ghi nhận đang hiệu lực. |

`checks` của phiên bản có năm khóa `sources`, `facts`, `original`, `rights`, `claims`. `status` có thể là `draft`, `approved`, `partially_recorded`, `recorded`; không dùng riêng `status` để suy ra quyền xuất: còn phải xét khóa, thay đổi bản tin, policy và tính toàn vẹn snapshot. `needs_update` chỉ áp dụng bản chưa khóa; bản đã khóa giữ snapshot lịch sử. Đầu ra archive là lịch sử, không xác nhận rằng policy hiện tại còn cho phép xuất để đăng.

Lịch sử bản tin trả tối đa 100 bản ghi mới nhất, gồm `id`, `entity_type`, `entity_id`, `revision`, `action`, `snapshot`, `at`; `snapshot` là chuỗi JSON. Danh sách publication gồm cả ghi nhận đã hủy hoặc đính chính, vì vậy cần xét `active` và `events`, không đếm toàn bộ phần tử là bài còn hiệu lực.

## Kiểu dữ liệu lồng thường gặp

- `claims` là mảng object `{text: string, evidence: string, checked: boolean}`; `[]` là hợp lệ khi đang soạn nhưng không đủ điều kiện duyệt mục được sử dụng. Mỗi item có `verified` boolean; xác nhận lại sau thay đổi nội dung hoặc nguồn.
- Với nguồn chụp từ tin hiện hành hoặc thêm thủ công, `source_id`, `url`, `title`, `summary`, `source_name`, `date_kind`, `retrieved_at`, `scope`, `note_kind` là chuỗi; `published_at` là chuỗi hoặc `null`. Nguồn thu thập có thể có thêm dấu vết như `collection_method` và `excerpt_hash`; bản sao từ draft cũ có thể có cấu trúc nguồn khác. Không giả định mọi trường tùy chọn đều hiện diện.
- Mỗi `segment` có `text` là chuỗi, `item_ids` là mảng ID số nguyên. Nếu bỏ `source_ids` hoặc gửi `null`, renderer dùng mọi nguồn hiện có của các mục đã chọn; muốn chỉ dùng một số nguồn phải gửi mảng ID nguồn dạng chuỗi. Mảng rỗng không đủ nguồn cho mục được sử dụng và bị từ chối. Đây là hành vi khác với `source_selection: null` khi tạo bản tin, vốn bị từ chối.
- Trong preview, `position`, `length`, `limit` là số nguyên; `valid` là boolean; `item_ids`, `source_ids`, `urls` là mảng. `text` là văn bản đầu ra đầy đủ, còn `body` là nội dung đoạn đã bỏ khoảng trắng đầu/cuối.

Test HTTP `test_invalid_multichannel_field_types_do_not_change_saved_data` kiểm tra 34 trường hợp sai kiểu ở các trường chọn tin, thứ tự, xác nhận mục, claims và segments; mỗi trường hợp trả 400, không thay bản tin, phiên bản hay lịch sử trên fixture. Test này không bao phủ mọi trường hoặc tổ hợp.

## Giới hạn bằng chứng

Đây là bản đồ route và điều kiện chính đọc từ mã, chưa phải đặc tả đầy đủ mọi trường trả về, tất cả tổ hợp lỗi hoặc hợp đồng đã được người dùng chấp nhận. Bộ đếm Threads là ước lượng; hành vi X thực tế, mọi mẫu URL và emoji mới chưa được xác minh đầy đủ. Xem [kế hoạch](KE-HOACH-NANG-CAP-BAN-TIN-DA-KENH.md) và [bằng chứng kiểm thử](KIEM-THU.md) trước khi dùng để quyết định phát hành.
