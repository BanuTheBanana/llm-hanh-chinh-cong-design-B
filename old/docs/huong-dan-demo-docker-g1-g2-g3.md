# Hướng dẫn mở demo G1, G2 và G3 trên Docker Desktop

## Trạng thái đã chuẩn bị

Ba project độc lập đã được tạo trên máy:

| Project | Nội dung demo |
|---|---|
| `hanh-chinh-g1` | Web + Backend + PostgreSQL + Mock AI |
| `hanh-chinh-g2` | G1 + RAG và nguồn từ dữ liệu giả lập |
| `hanh-chinh-g3` | Dữ liệu công ty đã xử lý + RAG + Qwen3-1.7B chạy trong Docker |

## Cách chuyển giai đoạn

Do ba project cùng dùng địa chỉ `http://localhost:3000`, chỉ chạy một project tại
một thời điểm:

1. Bấm **Stop** project đang chạy và chờ tất cả container dừng.
2. Bấm **Start** project muốn demo.
3. Chờ các container báo `Healthy`.
4. Mở [http://localhost:3000](http://localhost:3000).

Không bấm biểu tượng thùng rác và không xóa volume vì volume chứa lịch sử riêng
của từng giai đoạn.

## Dấu hiệu nhận biết đúng giai đoạn

- G1 có 4 container; câu trả lời ghi nội dung mô phỏng và không có nguồn RAG.
- G2 có thêm `rag-init`; container này `Exited (0)` sau khi nạp dữ liệu là bình
  thường. Câu trả lời dùng dữ liệu giả lập và hiển thị nguồn.
- G3 có `llama-server`; đây là runtime đang chạy model Qwen. G3 có thể cần khoảng
  một phút để nạp model trước khi các container còn lại chuyển sang `Healthy`.

## Lưu ý khi báo cáo

G1 và G2 không dùng Qwen vì mục tiêu của chúng lần lượt là kiểm tra đường ống ứng
dụng và kiểm tra RAG. G3 mới là giai đoạn tích hợp Qwen thật. `llama-server` chỉ
là phần mềm chạy file `Qwen3-1.7B-Q8_0.gguf`, không phải một model khác.

