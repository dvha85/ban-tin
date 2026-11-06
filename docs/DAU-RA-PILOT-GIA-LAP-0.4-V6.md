# Đầu ra giả lập để xem — bản 0.4 policy v6

> **Chỉ để kiểm thử:** nội dung, nguồn và các xác nhận đều giả lập; không dùng làm tin thật hoặc đăng. Không có bài đăng mạng xã hội.

Ngày 06/11/2026: ba bản tin có 1, 2 và 3 mục, được chuẩn bị bằng service trong SQLite tạm. Từ các bản nháp đã chuẩn bị sẵn, đã chọn và duyệt từng kênh qua giao diện trình duyệt; nội dung dưới đây trích nguyên văn từ snapshot duyệt, sau khi kiểm tra hash và policy. Đây không phải tệp của ba pilot có đo thời gian trước, cũng không phải lần thử đầu-cuối từ bước chọn tin.

## Facebook · 1 mục

Policy: `2026-11-05-v6`. Số đoạn: 1.

### Đoạn 1

Bộ đếm ứng dụng: 151/12000.

```text
GIẢ LẬP — Bắt đầu ngày làm việc bằng danh sách ưu tiên. Hãy tự kiểm tra dữ liệu và nguồn trước khi áp dụng.

Nguồn: https://example.com/pilot-1/nguon-1
```

## Threads · 2 mục

Policy: `2026-11-05-v6`. Số đoạn: 1.

### Đoạn 1

Bộ đếm ứng dụng: 165/500.

```text
GIẢ LẬP — Tóm tắt điều đã làm, rồi đối chiếu nguồn. Example only; verify real claims.

Nguồn: https://example.com/pilot-2/nguon-1 https://example.com/pilot-2/nguon-2
```

## X · 3 mục

Policy: `2026-11-05-v6`. Số đoạn: 2.

### Đoạn 1

Bộ đếm ứng dụng: 144/280.

```text
1/2 GIẢ LẬP — Chọn đầu việc cần làm trước và lưu nguồn để có thể đối chiếu.

Nguồn: https://example.com/pilot-3/nguon-1 https://example.com/pilot-3/nguon-2
```

### Đoạn 2

Bộ đếm ứng dụng: 111/280.

```text
2/2 GIẢ LẬP — Rà soát kết quả sau cùng; không coi ví dụ này là tin thật.

Nguồn: https://example.com/pilot-3/nguon-3
```

## Giới hạn

- Các dấu kiểm và khẳng định chỉ phục vụ thử fixture; không phải việc kiểm chứng nguồn thật.
- Bộ đếm Threads là ước lượng; X có thể khác với emoji mới. Kiểm tra trên nền tảng trước khi đăng nội dung thật.
- Việc duyệt trên kho thử không phải quyết định triển khai kho vận hành.
