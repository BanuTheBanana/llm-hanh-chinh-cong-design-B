# Bàn giao sau khi hợp nhất phần Minh — G4-02 và G4-04

Tài liệu này để Hoan báo lại cho Minh. Phần intent, retrieval và context vẫn được
tính là công việc của Minh; các sửa đổi dưới đây là bước review và tích hợp chung.

## Phần của Minh được giữ lại

- Tách nhận diện tên thủ tục khỏi field người dùng hỏi.
- Binding evidence theo đúng field, dự trữ ít nhất một fragment cho mỗi field trong
  câu hỏi nhiều ý và giữ Top-5.
- `QueryContext`, `ConversationContext` cùng message ID nguồn của fact.
- Lưu context bằng cột JSONB `conversations.rag_context` và migration
  `0003_g4_context`.
- Cách ly context theo user/conversation, xử lý retry idempotent, đổi thủ tục và reset
  khi đổi corpus.
- Loader phục vụ không mở gold/evaluation; công cụ so sánh G3/G4 và regression hư cấu.

## Phần đã sửa khi review

1. Ghép `field_intents` từ QueryContext trực tiếp vào AnswerPlan để retrieval và
   verifier không tự phân tích field theo hai cách khác nhau.
2. Bổ sung các cách hỏi “mang giấy tờ”, “cách nộp” và từ nối của câu follow-up; câu
   chung chung không còn bị nhận nhầm thành tên thủ tục.
3. Với placeholder nguồn chỉ có `0.0` hoặc `05`, buộc trả
   `INSUFFICIENT_DATA`; không để Qwen diễn giải thành mức phí/thời hạn.
4. Nâng evaluator từ 64 câu một lượt lên đủ 80 DEV, trong đó 16 câu nhiều lượt.
   Context được dựng chỉ từ lượt user; text assistant mẫu không được dùng làm fact.
5. Sửa test tích hợp: câu hỏi field không có thủ tục phải yêu cầu làm rõ, không trả
   thiếu dữ liệu chung chung.
6. Đổi fingerprint phục vụ sang `g4-serving-corpus-v1`, cập nhật Compose và biến mẫu;
   gold/DEV/TEST không còn ảnh hưởng hash runtime.
7. Bổ sung smoke API nhiều lượt và Chromium thật; cập nhật tài liệu chạy Docker và
   công cụ release TEST_V2 một-lần.

## Kết quả sau hợp nhất trên DEV

| Chỉ số | G3 trước sửa, 64 câu một lượt | G4 sau sửa, 80 câu |
|---|---:|---:|
| Field accuracy | 48,44% | 100% |
| Routing accuracy | 100% | 100% |
| Status accuracy | 84,38% | 100% |
| Recall@5 | 73,47% | 100% |
| MRR@5 | 0,6776 | 1,0000 |
| Scenario nhiều lượt được chấm | 0 | 16/16 |

Số DEV chỉ dùng để phát triển, không phải kết quả độc lập. AnswerPlan trên DEV đạt
80/80; không có lỗi claim trọng yếu về phí, thời gian hoặc nơi tiếp nhận.

## Xác minh kỹ thuật

- Backend: 213 passed, 1 skipped; Ruff sạch.
- AI service: 68 passed; Ruff sạch.
- Web: 12 passed; build và ESLint sạch.
- PostgreSQL thật: migration ở `0003_g4_context`; test API/context/cách ly qua.
- Docker Qwen local: 16/16 DEV multi-turn qua, gồm 13 answer và 3 safe abstention.
- Chromium: đăng nhập, gửi câu, hiện nội dung/citation và reload history qua.

## GitHub

Không phát hiện branch Minh riêng trên remote tại lúc review. Code từ
`G4_Minh_Backend`/patch đã được đối chiếu và hợp nhất vào `g4/integration`; không chép
đè repo hoặc đưa dữ liệu riêng lên Git.
