# Nâng cấp intent/context policy v8-v9 theo hướng lightweight

Ngày triển khai: **16/09/2026**
Phạm vi: Backend state, AI intent policy và regression; không mở TEST kín.

## 1. Mục tiêu

Vòng này xử lý các lỗi hội thoại thực tế mà state bốn slot cũ chưa biểu diễn đủ:

- câu xác nhận như `Vậy là 8.000 đồng một bản đúng không?`;
- câu tiếp nối như `Còn gì nữa?`, `Còn thiếu gì?`;
- người dùng thông báo đã có giấy tờ rồi hỏi phần cần bổ sung;
- tránh truyền một state sai qua các lượt sau;
- không thêm model mới và không tăng VRAM thường trú.

Đây là nâng cấp kỹ thuật trên candidate Qwen3-4B intent/context hiện tại. Nó chưa phải một
lần nghiệm thu độc lập mới.

## 2. Cơ sở kỹ thuật được lựa chọn

### 2.1. State operation thay vì sinh lại toàn bộ state

Hệ thống tiếp tục dùng patch `KEEP/SET/CLEAR`, tương ứng với hướng selective overwrite:
slot không được nhắc lại sẽ carry over; slot có bằng chứng mới mới được update hoặc delete.
Cách này giảm lỗi model viết lại và làm mất các slot đúng trước đó.

Tham khảo: [Efficient Dialogue State Tracking by Selectively Overwriting Memory](https://aclanthology.org/2020.acl-main.53/).

### 2.2. State có khả năng sửa lỗi

Correctable-DST chỉ ra rằng dùng gold state khi train nhưng dùng predicted state khi inference
tạo ra sai lệch và lan truyền lỗi. Phiên bản lightweight ở đây không thêm Slot Detector riêng;
thay vào đó Backend giữ quyền sở hữu state, kiểm tra provenance và xóa memory phụ thuộc khi
`SWITCH/RESET`.

Tham khảo: [Correctable-DST](https://aclanthology.org/2022.emnlp-main.56/).

### 2.3. Copy/carryover có kiểm soát

Các câu xác nhận hoặc câu phụ thuộc ngữ cảnh được phép carry over field gần nhất, nhưng chỉ khi
field đó đã xuất hiện trong một grounded answer thành công. Không copy từ prose tự do của model.
Đây là biến thể nhỏ của slot carryover/copy memory, phù hợp task hành chính có ontology hẹp.

Tham khảo: [TripPy](https://aclanthology.org/2020.sigdial-1.4/) và
[Improving Long Distance Slot Carryover](https://aclanthology.org/W19-4111/).

### 2.4. Conversational query resolution

Các nghiên cứu conversational query rewriting cho thấy câu hỏi phụ thuộc lịch sử nên được
chuyển thành biểu diễn độc lập trước retrieval. Vòng này chưa thêm rewriter model; Backend dùng
procedure filter và field carryover để tạo truy vấn retrieval đã đủ nghĩa. Đây là bước đầu an
toàn trước khi cân nhắc distill query rewriting vào embedding model.

Tham khảo: [CONQRR](https://arxiv.org/abs/2112.08558) và
[RCEM](https://arxiv.org/abs/2606.01697).

## 3. State mới do Backend sở hữu

`IntentContextState` được mở rộng, vẫn tương thích dữ liệu `g5-context-state-v1` cũ nhờ các
giá trị mặc định:

| Trường | Ý nghĩa | Nguồn được tin cậy |
|---|---|---|
| `last_answered_fields` | Các field vừa trả lời thành công | `grounding.checklist` |
| `last_answered_fragment_ids` | Fragment vừa dùng | `grounding.sources` |
| `known_documents` | Giấy tờ người dùng nói rõ đã có | Chính user message |
| `last_turn_mode` | Standard/xác nhận/còn lại/inventory | Bộ phân loại deterministic |

Memory có giới hạn: tối đa 8 field, 8 fragment và 16 document fact. Assistant text không bao giờ
được đọc ngược thành fact.

### 3.1. Ranh giới tin cậy

- `known_documents` chỉ được ghi khi câu có tín hiệu sở hữu rõ như `tôi đã có`, `đã chuẩn bị`,
  `có sẵn`.
- Câu hỏi `Có cần CCCD không?` không được ghi thành fact `đã có CCCD`.
- `last_answered_fields` chỉ được ghi khi grounding có status `ANSWER` và checklist server-owned.
- Model intent không được tự ghi trực tiếp các trường memory mới.
- Mỗi document fact có `source_message_id` để truy vết.

### 3.2. Vòng đời state

- `KEEP`: giữ episodic memory.
- `SWITCH` sang thủ tục khác: xóa field/fragment/document memory của thủ tục cũ.
- `RESET`: xóa toàn bộ state và provenance.
- Đổi corpus version: dùng cơ chế reset hiện có.

## 4. Policy v8-v9

`POLICY_VERSION` hiện là `g6-intent-context-policy-v9`.

AI Service nhận diện deterministic các nhóm:

- xác nhận: `vậy là`, `đúng không`, `phải không`, `thôi hả`;
- hỏi tiếp: `còn gì nữa`, `còn thiếu gì`, `còn/cần bổ sung gì`, `những mục còn lại`.

Khi đã có procedure context:

1. giữ procedure hiện tại;
2. nếu câu có field cue rõ thì SET đúng field đó;
3. nếu không, giữ field state đã xác minh;
4. ghi audit action `DETERMINISTIC_CONTEXTUAL_FOLLOWUP`;
5. không gọi Qwen3-4B cho ca chắc chắn này.

Ở Backend, nếu model/policy không trả field cho một câu xác nhận, hệ thống được phép khôi phục
`last_answered_fields` từ grounded answer gần nhất. Không carry over field chỉ do model đoán.

### 4.1. Bảo vệ chủ đề bổ sung trong policy v9

Kiểm thử thực tế phát hiện tên giấy tờ như `giấy chứng sinh`, `CCCD` có thể trùng token với tên
thủ tục khác và khiến model/router đổi procedure sai. Policy v9 bổ sung invariant tổng quát:

- khi đã có active procedure, token rời rạc trong tên giấy tờ không đủ quyền đổi procedure;
- câu hỏi xác nhận/còn thiếu/cần bổ sung giữ active procedure, trừ khi user nêu rõ thủ tục mới
  hoặc có tín hiệu sửa/chuyển chủ đề;
- so khớp procedure lỏng chỉ được dùng ở lượt đầu hoặc khi có correction/switch rõ ràng;
- nhận diện hồ sơ dùng cấu trúc khái niệm `hồ sơ/giấy tờ/tài liệu` kết hợp với
  `cần/chuẩn bị/bổ sung/kèm/mang`, thay vì phụ thuộc một câu mẫu duy nhất;
- `hồ sơ gồm các bước` vẫn được hiểu là quy trình, không bị nhận nhầm thành thành phần hồ sơ.

## 5. Những gì chưa làm

- Chưa tự động trừ từng dòng giấy tờ khỏi danh sách nguồn. Dữ liệu hiện là text có điều kiện,
  trừ máy móc có thể làm mất ngoại lệ pháp lý; hệ thống mới ghi nhận giấy tờ và vẫn hiển thị danh
  sách nguồn đầy đủ.
- Chưa đưa episodic memory vào prompt model; model vẫn chỉ thấy state compact năm trường cũ.
- Chưa huấn luyện bằng state lịch sử bị làm nhiễu như Correctable-DST.
- Chưa có query-rewriter model hoặc RCEM fine-tune; không thêm model chỉ vì paper cho kết quả tốt.
- Chưa chạy fresh holdout, vì candidate còn đang trong vòng phát triển.

## 6. Kết quả kiểm thử

### 6.1. Test code

- AI Service: **131 pass**.
- Backend: **254 pass, 1 skip có chủ đích**, dùng PostgreSQL 16 test riêng.
- Test intent/context trọng tâm: Backend **52 pass**, AI **53 pass**.
- Ruff: pass cả Backend và AI Service.

PostgreSQL test được tạo tạm, chạy migration/schema riêng và đã xóa sau khi test. Không đụng
database demo.

### 6.2. Replay DEV 60 lượt

Candidate đã replay: Qwen3-4B hard-v2 r16 + prompt v2 + policy v8 + fast route.

| Chỉ số | Kết quả |
|---|---:|
| Schema/semantic | 100% |
| Dialogue act | 100% |
| Topic action | 100% |
| Full-state | **98,33%** |
| Field macro-F1 | **99,26%** |
| Hội thoại đúng trọn chuỗi | **95%** |
| Fast path/model fallback | 39/21 lượt |
| P95 | 2,84 giây |

Kết quả bằng mức chất lượng policy v7 trên DEV cũ, do đó chưa thấy regression. DEV đã mở không
thể thay cho holdout độc lập.

Policy v9 được kiểm tra bằng unit/regression và chuỗi hội thoại end-to-end trên runtime thật;
các số DEV trong bảng vẫn thuộc policy v8 và chưa được gắn lại cho v9 khi chưa replay đầy đủ.

Artifact chi tiết:
`evaluation/reports/g7/fresh-dev-policy-v8/summary.json`.

## 7. Mã nguồn thay đổi

- `backend/app/rag/g5/intent_context.py`: episodic memory, provenance, carryover và lifecycle.
- `backend/app/chat.py`: chỉ ghi memory sau khi có grounded result.
- `ai-service/app/intent_context_policy.py`: contextual follow-up fast route và topic lock, policy v9.
- `backend/tests/test_g5_intent_context.py`: fact boundary, carryover, reset.
- `ai-service/tests/test_intent_context_policy.py`: xác nhận và remaining follow-up.

## 8. Việc tiếp theo

1. Tạo regression hội thoại thực tế 150–300 lượt, ưu tiên xác nhận claim, correction, giấy tờ
   đã có và coreference dài.
2. Sinh các state lịch sử bị lỗi có kiểm soát để train model tự sửa state, không chỉ train trên
   state đúng.
3. Chuẩn hóa document ontology từ corpus; chỉ trừ giấy tờ khi từng item và điều kiện đã được
   cấu trúc hóa, review và gắn evidence.
4. Đánh giá query rewriting bằng retrieval metrics trước khi thêm vào runtime.
5. Sau khi khóa 4B candidate mới tạo fresh holdout; không tối ưu theo lỗi của holdout cũ.
