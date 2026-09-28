# Tổng kết quá trình phát triển hệ thống từ G1 đến G3

| Trường | Nội dung |
|---|---|
| Cập nhật | 10/09/2026 |
| Phạm vi | Quá trình phát triển và kết quả demo G1–G3 |
| Trạng thái | G3 hoàn thành nền tảng demo nội bộ |

## Mục đích

File này giúp thành viên trong nhóm hiểu nhanh hệ thống đã phát triển như thế
nào, hiện demo được gì và bước tiếp theo là gì.

## Bức tranh chung

Dự án không xây toàn bộ ngay từ đầu. Mỗi giai đoạn bổ sung một lớp mới:

```text
G1: Làm cho Web, Backend, AI giả lập và Database chạy xuyên suốt
 ↓
G2: Thêm RAG và trích dẫn bằng dữ liệu giả lập
 ↓
G3: Thay bằng dữ liệu công ty và Qwen chạy local
```

Nói ngắn gọn: **G1 dựng khung, G2 kiểm tra cách tìm nguồn, G3 đưa dữ liệu và
model thật vào khung đó.**

## Giai đoạn 1 – Dựng đường ống cơ bản

### Mục tiêu

Chứng minh ba phần Web, Backend và AI Service có thể kết nối với nhau, đồng thời
lưu được dữ liệu vào PostgreSQL.

### Đã làm

- Web chat bằng React.
- Backend API bằng FastAPI.
- AI Service giả lập, chưa dùng model thật.
- Đăng nhập bằng tên để demo.
- Tách lịch sử giữa các người dùng.
- Lưu conversation và message vào PostgreSQL.
- Chạy toàn bộ hệ thống bằng Docker Compose.

### Demo đạt được

Người dùng gửi tin nhắn, nhận phản hồi giả lập, tải lại trang vẫn còn lịch sử.
Đăng nhập bằng người khác thì không nhìn thấy cuộc trò chuyện của người trước.

### Ý nghĩa

G1 chưa giải quyết nghiệp vụ hành chính. Nó chứng minh **khung ứng dụng và luồng
lưu trữ hoạt động đúng** trước khi thêm RAG hoặc model thật.

## Giai đoạn 2 – Thêm RAG bằng dữ liệu giả lập

### Mục tiêu

Kiểm tra hệ thống có thể tìm thông tin từ dữ liệu, đưa evidence cho AI và hiển
thị nguồn hay không.

### Đã làm

- Tạo corpus giả gồm 3 thủ tục, 24 fragments và 33 câu hỏi đánh giá.
- Chuẩn hóa schema cho source, procedure, fragment và gold question.
- Tìm kiếm bằng exact match và BM25.
- Tạo `EvidenceBundle` để AI chỉ được trả lời từ nguồn tìm thấy.
- Backend kiểm tra citation trước khi lưu câu trả lời.
- Web hiển thị nguồn và cảnh báo đây là dữ liệu mô phỏng.

### Demo đạt được

Hệ thống tìm đúng thủ tục giả lập, trả lời có nguồn, biết hỏi lại khi câu hỏi mơ
hồ và biết từ chối khi không có dữ liệu.

### Ý nghĩa

G2 chứng minh **kiến trúc RAG và citation hoạt động**, nhưng chưa chứng minh câu
trả lời hành chính ngoài đời là đúng vì toàn bộ dữ liệu vẫn là giả lập.

## Giai đoạn 3 – Dữ liệu thật và Qwen local

### Mục tiêu

Đưa một phần dữ liệu công ty vào hệ thống và thay AI giả lập bằng model
lightweight chạy trên máy nội bộ.

### Đã làm

- Audit workbook công ty và xây pipeline tiền xử lý.
- Tách source, procedure, fragment, conflict và câu hỏi đánh giá.
- Chọn subset demo gồm 10 thủ tục và 49 fragments.
- Chia DEV/TEST theo thủ tục và khóa TEST để hạn chế data leakage.
- Dùng Qwen3-1.7B Q8_0 qua llama.cpp, không gửi dữ liệu tới API bên ngoài.
- Mount dữ liệu thật ở chế độ read-only, kiểm tra version và SHA-256.
- Cải thiện router để hiểu tên thủ tục khi người dùng bỏ chữ “Thủ tục” hoặc dùng
  cách nói “Tôi muốn làm...”.
- Thêm verifier, retry và chế độ trích xuất evidence an toàn khi Qwen trả sai
  contract.

### Demo đạt được

- Hỏi về một thủ tục trong phạm vi demo và nhận câu trả lời có citation.
- Hỏi các nhóm thông tin như hồ sơ, thời gian hoặc lệ phí.
- 10/10 thủ tục được nhận diện bằng cách gọi tên trực tiếp và mẫu hội thoại cơ bản.
- Câu thiếu tên thủ tục được hỏi lại; câu ngoài corpus bị từ chối.
- Lịch sử vẫn được lưu sau khi tải lại trang.
- Toàn bộ dữ liệu công ty và model đều ở local.

### Kết quả kiểm thử chính

| Nội dung | Kết quả |
|---|---:|
| Backend | 149 pass, 1 skip đặc thù Windows |
| AI Service | 66 pass |
| Data pipeline | 7 pass |
| Web | 11 pass, lint và build pass |
| DEV routing | 100% trong tập hiện tại |
| DEV citation binding | 100% |
| External AI call với dữ liệu thật | 0 |

Các con số trên chứng minh hệ thống chạy đúng theo contract hiện tại. Chúng
không phải chứng nhận rằng mọi câu trả lời đều đúng nghiệp vụ hoặc pháp lý.

## Hệ thống hiện tại đã ở mức nào?

Có thể xem G3 là **hệ thống cơ bản hoàn chỉnh để demo nội bộ**:

```text
Người dùng
→ Web
→ Backend xác định session và lưu message
→ RAG tìm procedure + evidence
→ Qwen local diễn giải
→ Verifier kiểm tra citation
→ PostgreSQL lưu kết quả
→ Web hiển thị câu trả lời và nguồn
```

Hệ thống chưa phải sản phẩm production và chưa phải trợ lý thông minh hoàn chỉnh.
Ví dụ đã phát hiện trường hợp hỏi “nộp hồ sơ ở đâu” nhưng evidence được chọn chưa
đúng loại. Đây là lỗi intent–evidence cần sửa ở giai đoạn tiếp theo, không phải
lỗi kết nối của nền tảng.

## Hướng phát triển tiếp theo

Ưu tiên một số việc chính:

1. Làm intent và evidence binding chính xác hơn.
2. Hiểu câu hỏi nối tiếp và ghi nhớ thủ tục đang nói tới.
3. Mở rộng từ subset 10 thủ tục sang corpus đã được nghiệp vụ duyệt.
4. Tạo TEST_V2 mới và có người nghiệp vụ đánh giá câu trả lời.
5. Chỉ thêm dense retrieval, reranker hoặc fine-tune khi kết quả phân tích lỗi cho
   thấy chúng thực sự cần thiết.

Các phần như đăng nhập thật, phân quyền, queue, Socket.IO, monitoring và triển
khai production sẽ thực hiện sau khi độ chính xác nghiệp vụ đủ tốt.

## Vì sao G3 chưa fine-tune?

Các lỗi đã gặp chủ yếu nằm ở routing, intent, dữ liệu và output contract. Những
lỗi này sửa bằng pipeline và rule hiệu quả hơn so với fine-tune. Qwen hiện chỉ
làm nhiệm vụ diễn giải evidence. Nhóm chỉ nên fine-tune khi có đủ dữ liệu đã duyệt
và chứng minh model thường xuyên diễn giải sai dù evidence đã đúng.

## Đoạn trình bày ngắn

> Ở G1, nhóm dựng Web, Backend, AI Service giả lập và PostgreSQL để chứng minh
> toàn bộ đường ống chat và lưu lịch sử hoạt động. Sang G2, nhóm thêm RAG, dữ liệu
> giả lập và citation verifier để kiểm tra AI chỉ trả lời từ nguồn. Đến G3, nhóm
> đưa một subset dữ liệu công ty vào local, thay AI giả bằng Qwen3-1.7B và bổ sung
> các cổng chống data leakage. Hiện hệ thống đã đủ để demo nội bộ: nhận câu hỏi,
> tìm thủ tục, trả lời có nguồn và lưu lịch sử. Giai đoạn tiếp theo sẽ tập trung
> vào độ chính xác intent–evidence, ngữ cảnh hội thoại và mở rộng dữ liệu, thay vì
> vội fine-tune model.
