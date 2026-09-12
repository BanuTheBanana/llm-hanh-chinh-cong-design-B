# Kế hoạch G5 tiếp theo: model nhẹ đã fine-tune, hiểu intent và context

Cập nhật 12/09/2026 theo yêu cầu mới của mentor. Đây là kế hoạch thực hiện trong
**5 ngày làm việc**. Ngày 1 đã hoàn tất pilot chọn checkpoint; các gate nghiệm thu
toàn sprint chưa đạt. Ngày 1 là ngày bắt đầu sprint;
chưa có ngày báo cáo cụ thể của mentor nên không tự quy đổi thành lịch thứ Hai–thứ Sáu.

## 1. Chốt đầu ra và thứ tự ưu tiên

Mốc này phải có **model đã fine-tune chạy trong hệ thống, nhận đúng ý định và theo dõi
hội thoại nhiều lượt**, kèm bảng trước/sau trên dữ liệu tiếng Việt của dự án.
Feedback thực hiện sau khi luồng này ổn. Tiếp tục trong G5, không đặt thêm một giai đoạn
mới cho mỗi ngày hoặc mỗi lần sửa lỗi.

Thứ tự phụ thuộc: **chốt bài toán/nhãn → so model → fine-tune → ghép intent/context →
đánh giá → feedback**. Minh có thể làm state manager bằng fixture trong lúc Hoan train;
không phải chờ model mới bắt đầu viết Backend.

“Tốt nhất” được hiểu là tốt nhất trong các ứng viên đã thử, với ngân sách máy và bài
toán này. Mục tiêu là chất lượng đo được; không thể cam kết một model đứng đầu mọi tác vụ.

## 2. Khoảng cách thực tế cần sửa

| Hiện có | Cần hoàn thành ở mốc này |
|---|---|
| Intent dùng regex/từ khóa trong `backend/app/rag/g4/intent.py` | Model học nhiều intent, phủ định, nói tắt, lỗi gõ và câu nhiều ý |
| Context giữ thủ tục, field, địa phương theo conversation | Học giữ/đổi/xóa dữ kiện, sửa lời trước, hiểu phản hồi cho câu hỏi làm rõ |
| QLoRA trước học câu trả lời từ evidence; 62 scenario gốc, validation 10 scenario | Dataset có nhãn intent và thay đổi trạng thái cho từng lượt; chấm đúng nhiệm vụ đã train |
| Kết quả cũ có nhiều phép chấm lượt cuối | Replay toàn hội thoại bằng trạng thái dự đoán, đo từng lượt và cả chuỗi |
| Một adapter chưa được triển khai vì citation giảm | Artifact fine-tune có lợi, xuất được bản nhẹ và thực sự dùng trong web demo |

Vì vậy biên bản G5 demo10 là mốc kỹ thuật trước yêu cầu mới; chưa chứng minh đã hoàn
thành năng lực intent/context bằng model. Giữ các số liệu đó làm baseline lịch sử.

## 3. Kiến trúc được chọn

```text
Câu người dùng + trạng thái đã kiểm tra + vài lượt hội thoại gần nhất
                         ↓
         Qwen đã fine-tune → intent + thay đổi context dạng JSON
                         ↓
      Backend kiểm schema/provenance → cập nhật state trong PostgreSQL
                         ↓
   thiếu dữ kiện: hỏi rõ | đủ dữ kiện: tạo truy vấn độc lập → RAG
                         ↓
    evidence → Qwen cùng checkpoint → verifier → câu trả lời có nguồn
```

Model học **hiểu ngôn ngữ**; Backend chịu trách nhiệm **lưu và áp dụng trạng thái**.
Trạng thái của mỗi người không được ghi vào trọng số model. Cách này sử dụng ý tưởng
dialogue state tracking theo schema và cập nhật từng lượt, tham khảo
[SDP-DST](https://aclanthology.org/2021.emnlp-main.404/) và
[IC-DST](https://aclanthology.org/2022.findings-emnlp.193/).

- Intent gồm hai phần: **hành động hội thoại** (hỏi, bổ sung, sửa, đổi chủ đề, bắt đầu lại,
  chào hỏi, ngoài phạm vi) và **trường nghiệp vụ** (hồ sơ, phí, thời gian, nơi nộp,
  cách nộp, trình tự, đối tượng, căn cứ). Một câu có thể hỏi nhiều trường.
- Model nhận danh sách thủ tục ứng viên, chọn ID trong danh sách hoặc báo chưa rõ.
  Thêm thủ tục vào corpus không bắt buộc thêm lớp phân loại cố định vào model.
- Context lưu thủ tục, các trường đang hỏi, địa phương người dùng nêu, ngày tra cứu,
  câu hỏi đang chờ trả lời và ID lượt đã cung cấp từng dữ kiện.
- Model trả thao tác `KEEP/SET/CLEAR`. “Không, tôi hỏi đăng ký kết hôn” phải thay thủ tục;
  “bắt đầu lại” phải xóa state; “còn lệ phí?” phải giữ thủ tục và đổi field.
- Backend gán user/conversation ID, phiên bản corpus và số phiên bản state. Model không
  được tự đặt các ID sở hữu. Gửi lại cùng message không được áp dụng state hai lần.
- Có thể đọc câu hỏi làm rõ của trợ lý để hiểu “đúng rồi” hoặc câu trả lời ngắn, nhưng
  câu trợ lý không tự tạo dữ kiện đã được người dùng xác nhận.
- Trước tiên chỉ dùng state + tối đa 6 message gần nhất. Cắt theo ngân sách token,
  không cắt mất câu hiện tại hoặc câu đang chờ làm rõ. Không cần một model tóm tắt riêng.
- Truy vấn RAG được dựng từ state đã kiểm tra. Ví dụ “còn bao lâu?” được bổ sung đúng
  thủ tục đang hỏi; ý tưởng viết lại truy vấn tham khảo
  [CONQRR](https://aclanthology.org/2022.emnlp-main.679/).

Đích vận hành là một checkpoint Qwen, tối đa hai lần gọi model mỗi lượt có trả lời
(hiểu câu hỏi và sinh đáp án); lượt cần làm rõ chỉ cần bước hiểu. Giữ bộ trích xuất
an toàn hiện có. So thêm tuyến rule → model khi không chắc để xem có giảm thời gian
mà vẫn giữ chất lượng; chưa mặc định rule đúng chỉ vì khớp một từ khóa.

## 4. Chọn model và fine-tune có mục tiêu

Máy kiểm tra ngày 12/09: **RTX 5060 Ti 16 GB VRAM, khoảng 32 GB RAM**.

| Ứng viên chính | Vai trò |
|---|---|
| Qwen3-1.7B | Baseline có sẵn, inference/QLoRA đã chạy |
| Qwen3-4B-Instruct-2507 | Đối chứng lớn hơn nhưng vẫn trong mức 4B; GGUF đã có |
| Qwen3.5-2B | Ứng viên 2B mới để kiểm tra; cần xác minh train/export/runtime trước |

Model card chính thức xác nhận [Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B)
có chế độ non-thinking và trọng số phù hợp thử fine-tune theo tác vụ.
Không suy ra nó thắng tiếng Việt từ benchmark chung. Qwen3.5 có kiến trúc khác;
không dùng nguyên danh sách LoRA target/module loader của script Qwen3 hiện tại.

1. Khóa revision, prompt, tokenizer, runtime và ngân sách token. Với ứng viên mới chạy
   thử load → vài bước LoRA → merge → GGUF → JSON trước khi dành thời gian train đầy đủ.
2. So ba model trên cùng DEV intent/context và evidence, giữ chế độ non-thinking.
   Chọn hai ứng viên có chất lượng tốt và vừa ngân sách để pilot fine-tune cùng lượng data.
3. Fine-tune theo hai task có prompt riêng: `INTENT_CONTEXT` và `ANSWER_WITH_EVIDENCE`.
   Khởi đầu 70% mẫu intent/context, 30% trả lời/hỏi rõ/thiếu nguồn; khóa tỷ lệ trước vòng đo.
4. Dùng QLoRA NF4, BF16, rank 16, batch nhỏ và gradient accumulation. Chọn epoch bằng
   DEV, tối đa 3 epoch. Kiểm tra target modules thực sự train được cho từng kiến trúc.
   Cơ sở bộ nhớ: [QLoRA](https://arxiv.org/abs/2305.14314),
   [hướng dẫn PEFT](https://huggingface.co/docs/peft/developer_guides/quantization).
5. Chọn winner **sau pilot fine-tune**, không chỉ dựa model gốc. Chạy một lần xác nhận
   bằng seed khác cho cấu hình được chọn; không thử hàng chục model/adapter trong tuần.
6. Xuất artifact, so Q8 và Q4 trên cùng DEV, dùng Q5 nếu Q4 giảm chất lượng quá mức.
   Đo lại bản GGUF thật; chất lượng adapter trong Python chưa bảo đảm chất lượng bản Docker.

Model fine-tune phải được sử dụng ít nhất ở bước `INTENT_CONTEXT` trong bản nghiệm thu.
Nếu adapter đa nhiệm làm generation giảm, vòng sửa ưu tiên chuyên biệt hóa intent/context
và để câu trả lời dựng từ evidence. Đây vẫn là ứng dụng fine-tune vào chức năng cần học;
phải báo rõ phần nào được model thực hiện. Nếu model fine-tune chưa đạt, giữ trạng thái
chưa đạt của yêu cầu mới và sửa nhóm lỗi, không dùng fallback để nâng điểm model.

Ngân sách phục vụ ban đầu: model sinh ≤4B; model chính + embedding ≤12 GiB VRAM khi
đo tải đã quy định; context tối đa 4096 token; input hiểu câu ≤2048, output JSON ≤384,
output đáp án ≤512. Mục tiêu P95 toàn lượt ≤5 giây khi chạy tuần tự và ≤8 giây ở
concurrency 2. Đây là mục tiêu cần đo, chưa phải thông số đã đạt.

## 5. Dùng toàn bộ dữ liệu công ty đúng việc

Audit hiện có: **42 dòng nguồn → 38 thủ tục → 202 fragment**; 34 thủ tục chờ review,
4 có conflict. Các trường đối tượng, trình tự và căn cứ còn thiếu trong toàn bộ 38.
Phạm vi đã duyệt trước đây vẫn là demo10: 10 thủ tục/49 fragment.

- Dùng toàn bộ corpus để rà soát, lập catalog và chuẩn bị tình huống. Quyền Hoan đã cấp
  cho phép tiếp tục review; không chờ xin lại quyền dùng dữ liệu.
- Đối chiếu từng thủ tục với nguồn, xử lý trùng/conflict và duyệt theo từng field.
  Field không có dữ kiện không được tự điền. Phát hành từng phần đã xác minh được.
- Thiếu nguồn vẫn có ích cho nhãn `INSUFFICIENT_DATA`; không tạo một đáp án có nội dung
  tự đoán để đạt đủ số lượng SFT. Intent về “trình tự” vẫn nhận diện được dù corpus chưa có đáp án.
- Mục tiêu đầu vòng: 360 **hội thoại gốc**, TRAIN 240 / DEV 60 / TEST 60; 3–6 lượt user
  mỗi hội thoại. Đây là kế hoạch tạo nhãn, chưa có sẵn 360 hội thoại đã duyệt.
- Chia cả hội thoại và họ kịch bản trước khi sinh paraphrase; audit nội dung gần giống.
  Giữ một nhóm thủ tục chưa tham gia SFT để chấm khả năng chuyển sang thủ tục mới.
  Quy mô nhóm này chốt sau audit, không ghi giả đủ 38 thủ tục đều dùng được.
- RAG được chứa nguồn đã duyệt của thủ tục test trong phép tra cứu mở sách. Câu hỏi,
  đáp án và state gold TEST không vào train, prompt ví dụ, cache hay index.
- TEST cũ đã mở là regression. Chỉ có một đợt TEST mới cuối sprint sau khi chọn candidate;
  không tạo lại TEST sau mỗi lỗi. Hoan giữ/review nhãn; chỉ giữ tính độc lập nếu nhãn không
  được dùng để chọn/sửa candidate. Vai trò leader không tự tạo hay xóa leakage.

## 6. Lịch làm việc cho nhóm

| Mốc | Hoan | Minh | Tú | Đầu ra kiểm tra được |
|---|---|---|---|---|
| Ngày 1 | Chốt protocol; thử tương thích 3 model | Contract intent/context; state reducer, migration và fixture | Rà đủ 38 thủ tục; nhóm lỗi và nhãn pilot | Schema, catalog, split plan, baseline đầu tiên |
| Ngày 2 | Benchmark baseline; pilot QLoRA hai ứng viên | Nối model JSON; provenance, sửa/đổi/reset và làm rõ | Hoàn tất TRAIN/DEV theo nhóm; chuẩn bị TEST riêng | Hai pilot có số intent/context, bộ data phiên bản hóa |
| Ngày 3 | Chọn/checkpoint fine-tune; xác nhận seed | Ghép RAG với state; replay toàn hội thoại | Rà lỗi nhãn và từng field mới được duyệt | Model đã train + luồng nhiều lượt chạy end-to-end |
| Ngày 4 | Export/quantize; so base/FT/Q4/Q8 | Cách ly user, idempotency, reload; sửa lỗi DEV | Review câu trả lời, khóa TEST cuối | Candidate Docker có fingerprint và bảng ablation |
| Ngày 5 | Chấm candidate khóa, tổng hợp, quay demo | Hỗ trợ demo; feedback nếu core đạt | Chấm rubric, báo coverage; kiểm feedback | Bảng nghiệm thu + video + hướng dẫn chạy |

Nếu Hoan/trợ lý tiếp tục làm thay, vẫn ghi công việc theo trách nhiệm của Tú/Minh/Hoan.
Các việc code có thể dùng fixture trong lúc chờ data; training đầy đủ phải dùng nhãn đã
kiểm tra. Rủi ro tiến độ chính là review data và tương thích export của model mới.

Nếu chậm: ưu tiên fine-tuned intent/context + sửa/đổi/reset + demo; giảm số thủ tục
phát hành theo phần đã duyệt và dời feedback. Không giảm bài khó hoặc đổi ngưỡng sau khi chấm.

## 7. Khi nào được nói đã xong?

| Nội dung | Mục tiêu nghiệm thu đề xuất, khóa trước khi chạy |
|---|---|
| Model | Adapter thật, fingerprint, bản lượng tử chạy được và được gọi trong demo |
| Intent | Field macro-F1 ≥0,95; exact-match nhiều field ≥0,90 |
| Context | Joint state accuracy ≥0,90 trên state dự đoán; ≥90% hội thoại đúng tất cả lượt cần chấm |
| Tình huống khó | Có riêng sửa dữ kiện, đổi/reset chủ đề, câu ngắn, mơ hồ, phủ định, thiếu nguồn và chuyển thủ tục |
| Dữ kiện trọng yếu | 0 claim sai số tiền/thời gian/nơi nộp hoặc bỏ điều kiện trong bộ trọng yếu được review |
| Tài nguyên | Đạt ngân sách model/VRAM/latency ở mục 4; báo cả tỷ lệ fallback |
| Trải nghiệm | Câu nối tiếp chạy thật, reload giữ đúng state, tách user, hiện citation; không chỉ ảnh chụp một câu |

Điểm model trước sửa phải tách điểm câu cuối sau verifier. Bộ 60 hội thoại TEST là một
mốc nội bộ nhỏ; báo số đúng/tổng và khoảng tin cậy, không gọi là bằng chứng đúng mọi câu.
Protocol chi tiết: [09-protocol-model-intent-context.md](09-protocol-model-intent-context.md).

## 8. Feedback, làm sau core

Hai câu hỏi riêng dưới mỗi câu trả lời: **phù hợp / không phù hợp** và **hài lòng /
không hài lòng**, kèm lý do tùy chọn. Cho sửa/xóa đánh giá của chính người dùng.
Lưu theo assistant message, user, model/corpus/prompt version và timestamp; kiểm quyền
sở hữu ở Backend. Phân biệt “chưa đánh giá” với đánh giá âm.

Feedback đi vào hàng đợi review lỗi. Không tự biến nút hài lòng thành nhãn đúng pháp lý
hoặc đưa thẳng mọi phản hồi vào lần training sau.

## 9. Trạng thái hiện tại

- Đã rà code intent/context, pilot G4, SFT/QLoRA G5, audit full corpus và máy đích.
- Đã chọn hướng nghiên cứu, ghi kế hoạch và protocol thực nghiệm.
- Đã tạo JSON Schema, fixture hư cấu 120 TRAIN/60 DEV, script QLoRA và benchmark GGUF.
- Đã thêm parser/verifier/reducer Backend độc lập: kiểm catalog/evidence, tự xóa context
  phụ thuộc khi switch/reset và chống áp dụng hai lần. Chưa nối model mới vào route chat,
  nên không ảnh hưởng demo G3 đang dùng.
- Đã chạy baseline ba model, pilot QLoRA hai model và xác nhận winner bằng seed thứ hai.
  Chọn **Qwen3-4B-Instruct-2507** cho nhánh phát triển; Qwen3.5-2B là fallback nhẹ.
- Kết quả tốt nhất hiện tại trên DEV hư cấu: schema/ngữ nghĩa 100%, dialogue act 91,67%,
  topic 93,33%, joint state 75,00%, full state 63,33%, P95 2,52 giây và tăng 4.843 MiB VRAM.
- Đây là **model-selection pilot**, không phải TEST cuối: joint state chưa đạt 90%, chưa
  replay hội thoại và chưa dùng nhãn công ty đã review. Xem
  [kết quả chi tiết](11-ket-qua-chon-model-intent-context.md).
