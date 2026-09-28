# Tổng hợp quá trình phát triển sau hệ thống cơ bản đến hiện tại

Cập nhật: **14/09/2026**.

Tài liệu này giúp cả nhóm nhìn lại một mạch từ sau G3 đến hết vòng cải thiện intent/context
hiện tại. Các con số TEST được giữ đúng theo biên bản cũ; không đổi kết quả FAIL thành PASS.

> **Lưu ý về tên giai đoạn:** lộ trình dài hạn lập ngày 11/09 từng dự kiến G6 là “sản phẩm
> thử nghiệm nội bộ”. Sau yêu cầu ưu tiên của mentor, công việc thực tế mang tên G6 đã được dùng
> cho vòng làm intent/context bền vững. Vì vậy các hạng mục sản phẩm nội bộ trong lộ trình cũ
> như RBAC, monitoring và backup chưa thể coi là đã hoàn thành chỉ vì G6 hiện tại đã đóng.

## 1. Điểm xuất phát: hệ thống cơ bản sau G3

Sau G3, nhóm đã có một hệ thống RAG chạy end-to-end:

```text
Người dùng → Web → Backend → tìm nguồn → Qwen local
           → verifier/fallback → câu trả lời có citation → lưu lịch sử PostgreSQL
```

Phạm vi phục vụ là `demo10`: **10 thủ tục, 10 nguồn và 49 fragment** đã được duyệt.
Hệ thống biết trả lời theo nguồn và chuyển sang trạng thái an toàn khi không đủ evidence.
Đây là nền tảng kỹ thuật hoàn chỉnh để tiếp tục phát triển, nhưng khả năng hiểu field và câu
hỏi nối tiếp còn đơn giản.

## 2. G4: đúng ý, đúng nguồn và hội thoại ngắn

### Mục tiêu

G4 không xây lại hệ thống. Mục tiêu là làm hệ thống cơ bản hiểu người dùng tốt hơn:

- Tách **thủ tục đang hỏi** và **field cần trả lời** như hồ sơ, phí, thời gian, nơi nộp.
- Tìm đúng fragment theo field thay vì chỉ khớp từ khóa chung.
- Dựng `AnswerPlan` từ evidence và kiểm claim trước khi trả lời.
- Giữ context ngắn trong cùng conversation: thủ tục, field, địa phương và câu làm rõ đang chờ.
- Chấm riêng DEV và TEST khóa để không lấy kết quả demo làm kết quả nghiệm thu.

### Công việc đã làm

| Phần | Nội dung chính |
|---|---|
| Tú – dữ liệu đánh giá | Hoàn thiện 80 DEV, 40 TEST_V2, 36 scenario multi-turn; schema, validator, hash, review/lock và split 8/2 thủ tục |
| Minh – Backend/RAG | Tách field intent khỏi procedure, giữ Top-5, binding evidence đúng field và lưu conversation context trong PostgreSQL |
| Hoan – AI/tích hợp | Xây AnswerPlan, verifier, fallback trích xuất an toàn, benchmark Qwen và tích hợp Docker/Web/API |

Gói dữ liệu Tú gửi đã được sửa các điểm quan trọng: multi-turn thành đúng chuỗi
`user → assistant → user`, gold lấy theo giá trị nguồn thay vì từ khóa chung, placeholder mơ hồ
buộc `INSUFFICIENT_DATA`, đồng thời bổ sung schema và publish validator riêng.

Backend lưu context theo đúng user/conversation và không chia sẻ chéo. Khi đủ nguồn, AnswerPlan
chỉ cho Qwen diễn giải các claim đã được evidence hỗ trợ; khi thiếu hoặc conflict, hệ thống hỏi lại
hoặc từ chối an toàn.

### Kết quả

- DEV 80 scenario đạt 100% field, routing, status, Recall@5 và AnswerPlan.
- So với G3 trên 64 câu một lượt, field accuracy tăng từ **48,44% lên 100%** và Recall@5
  từ **73,47% lên 100%**.
- TEST_V2 đạt phần lớn gate nhưng multi-turn chỉ **85%**, thấp hơn yêu cầu 90%.
- TEST_V3 độc lập chỉ đạt **5% multi-turn** và phát hiện hệ thống chưa tổng quát với cách diễn đạt mới.

Kết luận: **G4 hoàn thành phần tích hợp nhưng không đạt gate phát hành**. Những TEST đã mở chỉ
được giữ làm regression, không còn là holdout độc lập.

## 3. G5: mở rộng hệ thống chuyên biệt rồi tập trung vào intent/context

### 3.1. Audit dữ liệu và giữ phạm vi an toàn

| Bộ dữ liệu | Nguồn | Thủ tục | Fragment | Trạng thái |
|---|---:|---:|---:|---|
| Demo đã duyệt | 10 | 10 | 49 | Được phục vụ |
| Corpus đầy đủ | 42 | 38 | 202 | BLOCKED |

Corpus đầy đủ còn 34 thủ tục chờ review và 4 thủ tục conflict/quarantine. Nhóm quyết định không
đưa dữ liệu chưa đủ chất lượng vào hệ thống chỉ để tăng số lượng. Vì vậy runtime hiện vẫn dùng
demo10.

### 3.2. Nâng RAG và cập nhật nguồn

G5 bổ sung các năng lực sau:

- Giữ Exact/BM25 làm tuyến truy xuất chính; thêm Qwen3 Embedding 0.6B làm fallback khi lexical
  không xác định được kết quả.
- Thêm Source Service theo MCP với vòng đời
  `STAGE → APPROVE → PUBLISH → ROLLBACK/REJECT`.
- Mỗi snapshot có version, SHA-256, người duyệt và thời gian. Bản chưa duyệt, sai hash hoặc chưa
  đến hiệu lực không được đưa vào trả lời.
- Web hiển thị checklist, citation, phiên bản tri thức và thời điểm nguồn được duyệt.
- MCP hiện đọc registry nội bộ đã review; **chưa nối trực tiếp nguồn nhà nước realtime**.

### 3.3. Fine-tune model sinh câu trả lời

Qwen3-1.7B được thử QLoRA rank 16 bằng 208 dòng TRAIN và 40 dòng VALIDATION. Adapter tăng một
ca bao phủ nguyên văn nhưng citation giảm từ 10/10 xuống 9/10 và thời gian trung bình tăng từ
4,90 lên 10,72 giây. Vì citation là chốt an toàn, adapter này **không được triển khai**.

Do đó model sinh câu trả lời hiện tại vẫn là **Qwen3-1.7B Q8_0 gốc**.

### 3.4. Chuyển trọng tâm sang intent/context theo yêu cầu mentor

Nhóm tách nhiệm vụ hiểu hội thoại thành một contract JSON gồm:

- `dialogue_act`: hỏi thông tin, làm rõ, sửa context, reset, chào hoặc ngoài phạm vi.
- `topic_action`: giữ, chuyển, reset hoặc chưa xác định chủ đề.
- Patch `KEEP / SET / CLEAR` cho procedure, field, địa phương và ngày tra cứu.
- Evidence phải là nguyên văn từ message hiện tại; Backend kiểm schema, catalog và state trước
  khi áp dụng.

Luồng thực tế:

```text
Câu hiện tại + state + catalog
        → model intent/context
        → JSON KEEP/SET/CLEAR
        → policy + verifier
        → Backend reducer
        → retrieval → AnswerPlan → model trả lời có nguồn
```

Ba model 1.7B, Qwen3.5-2B và Qwen3-4B được so sánh cùng prompt, schema và thiết bị.
Qwen3-4B hiểu state tốt nhất nên được fine-tune QLoRA. TRAIN intent/context được mở rộng từ
120 lên **252 mẫu D0 hư cấu**, tập trung vào follow-up, correction/switch, reset, scope/date
và boundary. Bộ này không chứa dữ liệu công ty hoặc câu TEST kín.

Adapter hard-v2 rank 16 của Qwen3-4B kết hợp policy đã nâng full-state DEV từ 63,33% ở adapter
vòng đầu lên **95%**. Model intent/context được tích hợp bằng llama.cpp local; Backend vẫn là
thành phần duy nhất sở hữu conversation state.

> Cần phân biệt: **Qwen3-1.7B sinh câu trả lời**, còn **Qwen3-4B + LoRA phân tích
> intent/context**. Đây là hai nhiệm vụ khác nhau trong cùng hệ thống.

### 3.5. Feedback người dùng

Mỗi câu trả lời hoàn tất có hai trục đánh giá:

- Phù hợp / không phù hợp.
- Hài lòng / chưa hài lòng.

Người dùng có thể ghi lý do, sửa hoặc xóa feedback. Backend kiểm quyền sở hữu conversation và
lưu kèm model, provider, corpus, prompt. Feedback chỉ đi vào hàng chờ review, **không tự trở
thành gold pháp lý hoặc tự đi vào fine-tune**.

### 3.6. Runtime G5 đã đạt gì?

- Docker gồm 8 service: Web, Backend, PostgreSQL, AI Service, generation model, embedding model,
  intent model và Source Service.
- Chat nhiều lượt, switch/reset, RAG có nguồn, MCP version/rollback và feedback đã chạy E2E.
- Web phục vụ tại `http://localhost:3005`.

Tuy nhiên ba FINAL intent/context độc lập đều không qua gate:

| FINAL G5 | Full-state | Hội thoại đúng trọn chuỗi | Kết luận |
|---|---:|---:|---|
| V1 | 90% | 75% | FAIL |
| V2 | 73,33% | 60% | FAIL |
| V3 | 81,67% | 65% | FAIL |

Kết luận G5: **chức năng và runtime hoàn tất, chất lượng intent/context chưa được nghiệm thu**.

## 4. G6 hiện tại: làm intent/context bền vững và giảm gọi model

G6 là một chu kỳ chất lượng mới sau G5, không chạy lại TEST cũ để lấy điểm đẹp.

### 4.1. Policy hybrid v4

Lỗi G5 được chuyển thành các bất biến tổng quát:

- Chỉ nhận `PROVIDE_CLARIFICATION` khi state thật sự có slot đang chờ.
- Tín hiệu procedure/field rõ không bị nhãn chào hoặc ngoài phạm vi lấn át.
- Không suy legal basis chỉ vì xuất hiện từ “quy định”, hoặc suy hồ sơ từ mọi câu có chữ “hồ sơ”.
- Chỉ cho `CLEAR` khi người dùng yêu cầu xóa đúng slot.
- Nhận diện câu sửa địa bàn, đổi thủ tục và giữ scope qua follow-up.

Kiến trúc hybrid:

```text
Câu + state + catalog
        ├─ rõ, chắc chắn → fast path 0-token
        └─ mơ hồ/pending/scope/date → Qwen3-4B + LoRA
                    ↓
             policy v4 + verifier
                    ↓
             Backend state reducer
```

Fast path chỉ xử lý trường hợp chắc chắn; nó không tự tạo nội dung pháp lý. Mọi can thiệp đều
ghi `policy_actions`. Hiện có **107 test AI Service** và Ruff đều pass.

### 4.2. Fine-tune và chọn lại model nhẹ

Qwen3.5-2B được fine-tune lại trên 252 mẫu TRAIN để kiểm tra liệu có thể thay 4B hay không:

| Cấu hình trên DEV mới | Full-state | Hội thoại | P95 | VRAM tăng | Qua gate |
|---|---:|---:|---:|---:|:---:|
| Qwen3-1.7B base | 58,33% | 40% | 2,42 s | 2.262 MiB | Không |
| Qwen3.5-2B + LoRA pilot | 85% | 70% | 1,79 s | 2.222 MiB | Không |
| Qwen3.5-2B + LoRA mới | 95% | 85% | 1,47 s | 2.311 MiB | Không |
| Qwen3-4B + LoRA hard-v2 | 100% | 100% | 2,86 s | 4.913 MiB | Có |

2B nhẹ và nhanh hơn nhiều, nhưng chưa đạt gate hội thoại và correction/switch. Vì ưu tiên chất
lượng, Qwen3-4B tiếp tục được chọn làm candidate intent/context.

### 4.3. FINAL G6

Candidate, model hash, adapter, prompt, policy và ngưỡng được khóa trước khi chạy. FINAL riêng
gồm 20 hội thoại × 3 lượt, không trùng/gần trùng TRAIN, DEV và các holdout G5.

| Chỉ số | Kết quả | Gate | Trạng thái |
|---|---:|---:|:---:|
| Schema/semantic | 100% | 100% | Đạt |
| Full-state | 83,33% | ≥95% | Không đạt |
| Field macro-F1 | 90,74% | ≥95% | Không đạt |
| Hội thoại đúng trọn chuỗi | 60% | ≥90% | Không đạt |
| P95 | 2,56 s | ≤3 s | Đạt |

Nhóm yếu nhất là reset 33,33%, correction/switch 55,56% và boundary 71,43%. FINAL này đã chạy
đúng một lần và không được dùng để chỉnh rồi chạy lại trong G6.

Kết luận G6: **hoàn tất kỹ thuật nhưng FAIL nghiệm thu intent/context**.

## 5. Hệ thống hiện có gì và chưa có gì?

### Đã có và chạy được

- Web chat, đăng nhập demo, history và context lưu PostgreSQL.
- RAG trên 10 thủ tục đã duyệt; Exact/BM25 và embedding fallback.
- AnswerPlan, citation binding, verifier và fallback an toàn.
- Qwen local cho sinh câu trả lời và model riêng cho intent/context.
- Hiểu direct/follow-up tốt; có switch, correction, reset, scope/date và pending clarification.
- MCP nội bộ có review, version, publish và rollback.
- Feedback phù hợp/hài lòng có ownership và provenance.
- Docker 8/8 service healthy, demo tại `http://localhost:3005`.

### Còn vướng

1. **Intent/context chưa tổng quát ổn định:** DEV có thể rất cao nhưng FINAL mới giảm mạnh,
   nhất là reset, correction/switch và boundary.
2. **Model lightweight chưa chốt được phương án nhỏ:** 2B tiết kiệm khoảng một nửa VRAM nhưng
   chưa đạt chất lượng; 4B tốt hơn trên DEV nhưng vẫn không qua FINAL.
3. **Corpus đầy đủ chưa được phát hành:** mới phục vụ 10/38 thủ tục; phần còn lại phải review
   coverage, conflict và nguồn trước.
4. **Chưa đánh giá pháp lý độc lập:** điểm intent/context không đồng nghĩa câu trả lời đúng pháp luật.
5. **MCP chưa realtime từ nguồn nhà nước:** mới chứng minh quy trình cập nhật registry nội bộ.
6. **Chưa production:** còn thiếu RBAC quản trị thật, monitoring/alert, backup/restore, kiểm thử
   tải lớn và SLA.

## 6. Việc nhóm cần thống nhất tiếp theo

Không nên tiếp tục tạo TEST mới mỗi ngày. Cần mở một chu kỳ cải thiện đủ lớn, sau đó mới nghiệm
thu lại:

1. Phân loại raw lỗi đã mở thành họ lỗi, nhưng không sao chép câu FINAL thành TRAIN.
2. Bổ sung TRAIN/DEV đa dạng cho reset, correction/switch và boundary; split theo hội thoại và
   họ cách diễn đạt trước khi tạo biến thể.
3. Tách mạnh hơn phần state machine xác định khỏi phần model suy luận; model chỉ xử lý phần thật
   sự mơ hồ, mọi quyết định vẫn có log và verifier.
4. Chỉ cân nhắc chuyển xuống 2B sau khi nó đạt cùng gate chất lượng với 4B; không chọn chỉ vì nhanh.
5. Song song, Tú tiếp tục review corpus đầy đủ; Minh hoàn thiện state/retrieval/monitoring; Hoan
   phụ trách model, evaluator, integration và quyết định release.
6. Khi DEV mới đạt ổn định, khóa đúng một candidate rồi mới tạo **một holdout độc lập mới**.

## 7. Trạng thái ngắn để nói lại với nhóm

> Sau G3, nhóm đã nâng hệ thống từ RAG cơ bản thành hệ thống có field intent, AnswerPlan,
> context nhiều lượt, dense fallback, MCP cập nhật nguồn, feedback và model intent/context đã
> fine-tune. Toàn bộ stack chạy thật bằng Docker trên 10 thủ tục đã duyệt. Tuy nhiên khả năng
> hiểu context chưa bền với cách diễn đạt mới: G5 và G6 đều hoàn tất kỹ thuật nhưng chưa qua
> FINAL. Việc tiếp theo là một vòng cải thiện tập trung reset, correction/switch và boundary,
> đồng thời review thêm dữ liệu; chưa thể gọi model hiện tại là bản production hoặc accepted.

## 8. Tài liệu chi tiết liên quan

- [Nghiệm thu G4](giai-doan-4/07-nghiem-thu-giai-doan-4.md)
- [Phạm vi G5](giai-doan-5/01-pham-vi-va-thuc-hien.md)
- [Kết quả chọn model intent/context](giai-doan-5/11-ket-qua-chon-model-intent-context.md)
- [Tích hợp intent/context runtime](giai-doan-5/12-tich-hop-intent-context-runtime.md)
- [Nghiệm thu G5](giai-doan-5/07-nghiem-thu-giai-doan-5.md)
- [Kết quả chọn model G6](giai-doan-6/04-ket-qua-chon-model.md)
- [Nghiệm thu G6](giai-doan-6/05-nghiem-thu-giai-doan-6.md)
