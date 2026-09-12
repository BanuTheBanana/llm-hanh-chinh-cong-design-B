# Protocol lựa chọn model và nghiệm thu intent/context

Phiên bản: `g5-intent-context-v1`, 12/09/2026. Trạng thái: **IN PROGRESS**.
Áp dụng cùng [kế hoạch](08-ke-hoach-intent-context-finetune.md).
Ngưỡng/split phải khóa trước khi chạy candidate; không sửa để hợp thức hóa kết quả.

## 1. Các nhánh so sánh

| ID | Nhánh | Câu hỏi thực nghiệm |
|---|---|---|
| B0 | G5 hiện tại: rule/context + base Qwen | Baseline sản phẩm có gì và hỏng ở đâu? |
| B1 | Base Qwen + prompt schema + state manager mới | Kiến trúc/prompt giúp được bao nhiêu khi chưa train? |
| B2 | Qwen fine-tuned + cùng schema/state manager | Fine-tune cải thiện trực tiếp intent/context bao nhiêu? |
| B3 | B2 + route rule cho câu chắc chắn | Có giảm latency mà không làm mất khả năng sửa/đổi/phủ định? |
| Q8/Q4 | Cùng winner, khác lượng tử | Bản nhẹ thực tế giảm chất lượng và VRAM bao nhiêu? |

B1/B2 phải dùng cùng input, lịch sử, catalog ứng viên, giới hạn token, grammar và
state manager. Không ghi mọi cải thiện từ B0 sang B2 là hiệu quả riêng của fine-tune.
Thử rollout bằng gold state chỉ để chẩn đoán; kết quả sản phẩm dùng state dự đoán.

## 2. Bộ dữ liệu cần xây

Mỗi conversation có `conversation_id`, `scenario_family_id`, `procedure_group`, split,
corpus version, provenance nguồn và trạng thái review. Mỗi lượt có input user, phản hồi
trợ lý trong lịch sử, gold intent, gold patch, gold state sau lượt, hành động mong đợi
và gold evidence/claim nếu cần trả lời. `state_before` dùng để train phải được tính từ
các lượt trước cùng conversation; không lấy dữ kiện ở lượt tương lai.

Nhóm bắt buộc (mỗi nhóm ít nhất 10 hội thoại TEST; có thể gắn nhiều nhãn trên một chuỗi):

- hỏi trực tiếp, nhiều field và tên thủ tục có chứa từ “phí”/“thời gian”;
- nối tiếp ngắn và dài, phản hồi cho câu hỏi làm rõ;
- phủ định/sửa dữ kiện và đổi thủ tục;
- reset, quay lại chủ đề và câu không liên quan;
- địa phương chưa xác minh, tên gần giống, out-of-scope;
- thiếu field/evidence và điều kiện phí/thời gian không rõ.

Tách 240 TRAIN / 60 DEV / 60 TEST ở cấp conversation/họ kịch bản trước augmentation.
Không sử dụng lại họ kịch bản với ID khác để lấp split. Kiểm tra exact và near-duplicate;
đóng góp paraphrase được báo riêng. Phân tầng theo intent/action và nhóm thủ tục.

Sau audit, giữ một nhóm procedure không có ví dụ trong TRAIN để báo kết quả riêng.
DEV/TEST được chạm nguồn trong RAG nhưng không chạm gold lúc inference. Nếu không đủ
nguồn/nhãn để đáp ứng quy mô, ghi rõ thiếu; không gọi một batch tự sinh chưa review là
corpus đã hoàn thiện. Bộ đã mở trong G3/G4/G5 không tính vào fresh holdout này.

Fine-tuning học schema/state update theo catalog và trả lời dựa nguồn. Data thiếu căn
cứ có thể dùng để học ask/abstain; không dùng làm nhãn ANSWER có claim tự tạo.

## 3. Hợp đồng hiểu hội thoại

Input:

```text
current_user_message
validated_state + pending_question
recent_messages (bounded)
procedure_candidates (ID + tên/mô tả được phép)
field/action schema
```

Output: `dialogue_act`, `topic_action`, và `patch` cho `procedure_id`, `field_intents`,
`jurisdiction`, `as_of`. Mỗi slot có thao tác KEEP/SET/CLEAR. Chỗ thay đổi có trích đoạn
user và ID message làm căn cứ; Backend tự kiểm ID/span và tự ghi provenance chuẩn.
Schema khởi đầu: [intent-context-v2.schema.json](schema/intent-context-v2.schema.json).

Contract output mang `schema_version=g5-intent-context-v2`; đây là phiên bản contract,
khác số phiên bản protocol ở đầu tài liệu. `dialogue_act` gồm ASK_INFORMATION,
PROVIDE_CLARIFICATION, CORRECT_CONTEXT, RESET_CONTEXT, GREET và OUT_OF_SCOPE.
Đổi thủ tục biểu diễn bằng `topic_action=SWITCH`, không tạo intent nghiệp vụ mới.
KEEP dùng `value=null`, evidence rỗng; SET/CLEAR phải có evidence. Ngày dùng ISO date.
Backend phải bật kiểm `format` của JSON Schema và kiểm thêm các quy tắc ngữ nghĩa bên dưới.

[Ví dụ hư cấu](schema/intent-context-v2.example.json) là output cho “Còn lệ phí?”
ở message `fixture-user-2`, giả sử state đã có thủ tục. Không chứa dữ liệu công ty.
Chạy test cấu trúc từ thư mục gốc repository:

```powershell
uv run --project tools/data pytest tools/data/tests/test_g5_intent_context_contract.py -q
```

Các test này chỉ kiểm contract; không được tính vào điểm intent/context của model.

Quy tắc state manager:

1. Schema JSON chỉ bảo đảm cấu trúc. ID procedure phải thuộc catalog; field thuộc enum;
   ngày phải parse được; trích đoạn phải có trong message được phép đọc.
2. KEEP giữ nguyên; SET thay giá trị; CLEAR xóa rõ ràng. Không gộp `null` với “không đổi”.
3. Sửa trực tiếp ở lượt hiện tại ưu tiên hơn state cũ. Đổi thủ tục xóa slot phụ thuộc
   thủ tục; địa phương dùng tiếp chỉ khi phạm vi lời người dùng hỗ trợ, nếu chưa rõ hỏi lại.
4. “Đúng rồi” chỉ xác nhận đề xuất đang chờ làm rõ; không xác nhận mọi phát biểu trợ lý.
5. RESET xóa thủ tục/field/scope/date đang hoạt động và câu hỏi còn chờ.
6. JSON sai, ID lạ hoặc lời mơ hồ: không cập nhật state từ output đó; hỏi rõ hoặc dùng
   tuyến đã kiểm chứng. Không lấy số confidence tự khai của model làm xác suất đã hiệu chuẩn.
7. State lưu theo conversation và được cập nhật một lần mỗi message; kiểm concurrency
   bằng state revision và transaction, tách khỏi gold state dùng đánh giá.

Phiên bản schema ban đầu đã có parser/verifier/reducer Backend và test độc lập; route chat
G5 hiện tại chưa gọi model intent/context mới.
Không nhận hỗ trợ multi-procedure đồng thời khi state chỉ giữ một thủ tục: hỏi người dùng
chọn thủ tục hoặc lần lượt xử lý, đưa các ca này vào đánh giá.

## 4. Chấm riêng lỗi hiểu, nhớ, tìm nguồn và trả lời

- **Field macro-F1:** tính precision/recall/F1 từng field rồi trung bình; báo support.
  Thêm exact-set match để câu hỏi hai field thiếu một field không được coi là đúng hoàn toàn.
- **Dialogue act:** macro-F1 và confusion matrix cho sửa/bổ sung/đổi/reset/ngoài phạm vi.
- **Joint state accuracy:** tỷ lệ lượt khớp toàn bộ procedure, field, scope và date cần
  chấm sau cập nhật. Hỏi rõ đúng nhưng bịa một slot vẫn là sai state.
- **Conversation success:** chỉ pass khi tất cả lượt được đánh dấu cần chấm trong
  conversation đều đúng; một lần mất context khiến chuỗi fail. Replay dùng predicted state.
- **Policy accuracy:** đúng hành động ANSWER/CLARIFY/INSUFFICIENT_DATA; tách từ chối sai
  trên câu có đáp án với tự tin sai trên câu thiếu dữ kiện.
- **Retrieval:** candidate recall của procedure, Recall@5 fragment và tỷ lệ thiếu nguồn
  do corpus; không đổ lỗi model nếu gold procedure chưa có trong candidates.
- **Generator:** output nguyên bản trước retry/verifier, contract, citation precision/recall,
  đủ claim/điều kiện. So nguyên văn chỉ là một phép chẩn đoán, không thay review ngữ nghĩa.
- **Final answer:** đo lại sau verifier và công bố tỷ lệ fallback. Chấm blind một tập
  phân tầng có phiên bản rubric; trường hợp bất đồng được Hoan phân xử trước khi tổng hợp.

Trong rollout, nếu pipeline hỏi khác kịch bản, chỉ gửi tiếp utterance hợp lệ với ngữ
cảnh hoặc kết thúc là fail. Không dùng assistant gold để sửa hộ phản hồi sai của hệ thống.
Báo số đúng/tổng, per-group và khoảng tin cậy 95% ở cấp conversation; không đếm các lượt
cùng hội thoại hoặc nhiều seed là những mẫu độc lập mới.

## 5. Thí nghiệm model trong ngân sách

- Ba ứng viên chính: Qwen3-1.7B, Qwen3-4B-Instruct-2507, Qwen3.5-2B. Model mới có tối đa
  nửa ngày cho kiểm tương thích; chưa export được thì tiếp tục với hai ứng viên đã chạy.
- Khóa commit Hugging Face và SHA GGUF riêng từng model, không dùng revision `main`
  trôi theo thời gian; ghi tokenizer/template, phiên bản training và llama.cpp.
- Baseline dùng cùng tập DEV. Prompt có mô tả schema, non-thinking, giới hạn chung và
  kiểm JSON; dùng cấu hình decode xác định cho lượt chính. Cấu hình riêng từng model
  chỉ chỉnh trên DEV và phải ghi rõ, không gọi so sánh đó là chỉ thay kích thước model.
- Pilot fine-tune hai ứng viên trên cùng TRAIN, sampling ratio 70/30 và token budget.
  Một cấu hình rank 16; một vòng sửa dữ liệu/cấu hình nếu có lỗi cụ thể; sau đó xác nhận
  winner với seed khác. Không lựa chọn seed theo điểm TEST.
- Dùng JSON decoding cho cả baseline và FT như nhau. So thêm schema-valid không grammar
  khi cần chẩn đoán mức model đã học. Grammar không bảo đảm chọn đúng intent.
- Lưu prompt/hash, seed, số token không bị truncation, số lượt gọi model, peak VRAM,
  retry/fallback và lỗi transport. Không tự bỏ ví dụ quá dài mà không thống kê.

Chọn candidate vượt các gate dữ kiện/schema trước, sau đó ưu tiên conversation success,
JGA và macro-F1. Khi chênh chất lượng ≤2 điểm phần trăm trên DEV, chọn model nhỏ/nhanh hơn
theo số đo; mốc 2 điểm là quy tắc quyết định đã đặt trước, không phải kiểm định tương đương.
Candidate cuối phải đạt các ngưỡng ở kế hoạch; “tốt nhất trong nhóm” chưa đồng nghĩa đã đạt.

## 6. Đo hệ thống nhẹ và fine-tune có hiệu quả

Chạy tuần tự các model trên RTX 5060 Ti 16 GB. Tách warm-up/cold start; đo lại khi không
có job GPU cạnh tranh và ghi VRAM nền. Nếu G3 đang dùng để demo, đo sau hoặc ghi rõ có
tranh tài nguyên; không so model A lúc máy rảnh với B lúc đang train.

So checkpoint gốc/FT ở cùng precision trước; so Q8/Q4 sau, context 4096, output NLU 384,
answer 512, request concurrency 1 và 2. Đo ≥60 conversation/DEV và ít nhất 30 request
cho phép đo latency; báo P50/P95 riêng NLU, generation và E2E. Bộ 12 request G5 cũ chỉ
giữ làm smoke lịch sử. Đặt trần service VRAM 12 GiB và model sinh tối đa 4B.

Fine-tune đạt khi tăng chất lượng hiểu/giữ context trên DEV, không vi phạm dữ kiện, và
candidate được chọn qua TEST cuối. Nếu tăng nhỏ hoặc CI chồng nhau, báo chưa đủ bằng chứng
cho mức cải thiện, thay vì suy từ loss. Test final chỉ chạy sau khi đóng băng candidate.

## 7. Artifact bàn giao

| Trong Git | Chỉ lưu private |
|---|---|
| Code, schema, fixture hư cấu, cấu hình và số tổng hợp | Corpus, hội thoại/nhãn, các split |
| Protocol, rubric, manifest dạng tổng hợp | Adapter/merged checkpoint/GGUF, training logs |
| Docker và hướng dẫn tái lập | Raw output, trace/context, feedback có nội dung người dùng |

Kết quả cũ không được ghi đè. Mỗi run có candidate commit/hash, data manifest hash và
vai trò TRAIN/DEV/OPENED_REGRESSION/FINAL_TEST. Feedback người dùng chỉ được đưa vào
đợt train mới sau review, loại trùng và chia lại dữ liệu có kiểm soát.
