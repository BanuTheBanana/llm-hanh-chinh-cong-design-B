# So sánh Qwen local và quyết định cấu hình G4

> Cập nhật sau tích hợp: lỗi retrieval nêu trong báo cáo pilot đã được G4-02 sửa trên
> DEV mới. Qwen3-1.7B Q8_0 vẫn là cấu hình mặc định; không dùng TEST_V2 để đổi model.
> Kết quả phát hành cuối được ghi riêng trong `07-nghiem-thu-giai-doan-4.md`.

Ngày chốt pilot: **11/09/2026**. Dữ liệu và output chi tiết chỉ lưu local.

## 1. Kết luận ngắn

**Giữ Qwen3-1.7B Q8_0 làm mặc định hiện tại.** 4B Instruct là ứng viên tiếp theo,
chưa thay mặc định: làm theo contract tốt hơn một chút khi evidence đúng,
nhưng chậm hơn và chưa giải quyết được lỗi retrieval.

Không chọn 0.6B cho luồng tư vấn hiện tại vì sai contract và cần fallback quá nhiều.
Chưa fine-tune. Chưa có bằng chứng từ đánh giá nghiệp vụ độc lập để kết luận
1.7B hay 4B là model trả lời đúng nội dung nhất, càng không phải “Qwen tốt nhất”.

## 2. Cách so sánh

- Cùng **31 câu DEV G3** trên corpus demo10: 10 thủ tục, 49 fragment.
- Mỗi model chạy hai seed 42/43; mỗi câu được chạy lại, không phải thêm câu độc lập.
- Nhánh A: evidence từ retrieval G3, cố định Exact/BM25 và Top-5.
- Nhánh B: evidence do gold DEV chỉ định, bỏ qua retrieval để chẩn đoán generator.
  Nhánh B không đại diện khả năng truy hồi thực tế hay kiểm định pháp lý.
- Cùng prompt `g2-grounded-v2`, context 4096, output tối đa 500 token,
  temperature 0.2, top_p 0.8, top_k 20, min_p 0, presence_penalty 1.5.
- Cùng Q8_0, cùng bản llama.cpp được pin digest, GPU RTX 5060 Ti 16 GB;
  chạy tuần tự, không chạy nhiều model cùng lúc. Có một câu giả lập warm-up trước mỗi lượt.
- 0.6B/1.7B dùng template non-thinking của G3; 4B Instruct dùng template của artifact,
  tắt reasoning. Đây là so sánh **cấu hình model dùng được**, không phải thí nghiệm
  chỉ thay số tham số: 4B cũng khác đợt instruction training/template.

Chỉ câu hỏi, evidence và thời điểm được gửi vào model. Gold label, expected answer,
AnswerPlan và TEST không đưa vào prompt/index. Không mở TEST_V2 để chọn cấu hình.
DEV G3 đã được nhóm sử dụng trước đây: số dưới đây phục vụ lựa chọn nội bộ,
không đo khả năng tổng quát hóa trên câu hỏi/thủ tục chưa thấy.

Tổng lượt đánh giá chính: 3 model × 2 seed × 2 nhánh × 31 = **372 lượt**.
Nhánh B có một câu không có evidence, guard không gọi model: tổng **366 lượt gọi
provider**, chưa tính các lần retry và warm-up. Lượt thử sơ bộ 10/09 không gộp vào bảng.

## 3. Nhánh A — Giữ nguyên retrieval hiện tại

Mỗi hàng gồm 62 lượt trên 31 câu. “Trạng thái” chỉ là ANSWER/NEED_CLARIFICATION/
INSUFFICIENT_DATA; không phải đánh giá câu trả lời đúng nghiệp vụ.

| Model Q8_0 | Contract đúng ngay lần đầu | Trạng thái đúng sau retry/fallback | Cần retry | Fallback của provider | Gold citation recall lần đầu |
|---|---:|---:|---:|---:|---:|
| Qwen3-0.6B | 20/62 (32,3%) | 56/62 | 42/62 | 28/62 | 20,0% |
| Qwen3-1.7B | 60/62 (96,8%) | 60/62 | 2/62 | 0/62 | 76,7% |
| Qwen3-4B-Instruct-2507 | 61/62 (98,4%) | 55/62 | 1/62 | 0/62 | 80,0% |

Contract gồm JSON/schema, status invariant và citation ID nằm trong evidence.
Citation recall tính trên câu có gold fragment, output lần đầu không hợp lệ tính 0;
không dùng câu do fallback tạo để nâng điểm model lần đầu.

| Model | Trung bình/lượt | P50 | P95 | GPU memory quan sát lớn nhất |
|---|---:|---:|---:|---:|
| 0.6B | 641 ms | 639 ms | 913 ms | 5.0 GiB |
| 1.7B | 764 ms | 692 ms | 1.191 ms | 6.2 GiB |
| 4B Instruct | 1.407 ms | 1.197 ms | 3.176 ms | 8.4 GiB |

Latency gồm retry/fallback trong provider, **không** gồm Web, PostgreSQL, retrieval
hay toàn luồng E2E. P50/P95 tính từ các lượt gộp, không lấy trung bình percentile.
Bộ nhớ là mẫu `nvidia-smi` của **toàn GPU** sau từng request, gồm ứng dụng desktop;
không phải VRAM riêng model hoặc peak thực sự. Đây là đo warm, một request mỗi lần,
không phải SLA hay kiểm thử tải. Cả ba không có lỗi HTTP/transport ở các lượt đã đo.

## 4. Nhánh B — Dùng fragment do gold DEV chỉ định

Mỗi model có 60 lượt sinh trên 30 câu có evidence. Hai lượt còn lại được guard
xử lý vì không có evidence; cột trạng thái có tính hai lượt này.

| Model Q8_0 | Contract đúng lần đầu | Trạng thái đúng sau retry/fallback | Fallback của provider | Gold citation recall lần đầu | Độ trễ TB lượt có gọi model |
|---|---:|---:|---:|---:|---:|
| 0.6B | 14/60 | 56/62 | 34/60 | 16,7% | 637 ms |
| 1.7B | 58/60 | 62/62 | 0/60 | 96,7% | 698 ms |
| 4B Instruct | 60/60 | 62/62 | 0/60 | 100% | 1.380 ms |

4B có lợi về contract/citation ở nhánh này. Tuy nhiên, không được viết “4B đúng
100% câu hỏi”: bảng chưa chấm ý nghĩa, đủ ý, điều kiện, phạm vi áp dụng bằng reviewer.
Gold evidence cũng là nhãn nội bộ G3, chưa thay thế bước reviewer G4 của Tú.

## 5. Kiểm tra phần Hoan, không gộp với chất lượng model

AnswerPlan mới luôn dựng dữ kiện từ nguồn. Bộ kiểm tra nguyên văn bảo thủ nên
một câu paraphrase đúng vẫn có thể phải thay bằng bản trích xuất.

| Kiểm tra | Kết quả / ý nghĩa |
|---|---|
| Có đủ plan với retrieval G3 | 24/31 câu. Sáu câu thiếu evidence đúng trường nơi tiếp nhận; một câu chưa xác định intent. |
| Trạng thái sau guard với retrieval G3 | 24/31, chưa đạt gate G4. Không bật thay G3 mặc định. |
| Có đủ plan khi cấp gold evidence | 30/30 câu có evidence; cho thấy có thể tiếp tục tích hợp với retrieval của Minh. |
| Câu 1.7B qua kiểm tra nguyên văn trên nhánh A | 4/48 lượt có plan trả lời; 44/48 phải dựng lại từ nguồn. Không được gọi 44 lượt này là lỗi nghiệp vụ của model. |
| Chặn sai dữ kiện trong test giả lập | Có regression cho bỏ điều kiện phí, đổi số tiền, thêm nơi nộp, thiếu fragment, sai citation/binding, timeout và cắt text. |

Cột kiểm tra nguyên văn là chấm offline trên output G3 đã cố định. Đây **không**
phải tỷ lệ fallback đo từ endpoint G4: endpoint G4 lọc evidence theo plan trước
khi gọi Qwen. Smoke Docker/Chromium kiểm tra endpoint thật nhưng mẫu nhỏ, chưa dùng
để công bố một tỷ lệ chất lượng hay độ trễ toàn hệ thống.

Đã sửa thêm lỗi của adapter: từ “chi phí” hoặc “thời gian” nằm trong **tên thủ tục**
không được tự coi là field đang hỏi. Sửa trên DEV/test giả lập; không đọc TEST.
Khi so sánh verifier trước/sau, giữ lại nguyên model output và bắt buộc câu hỏi,
evidence, thứ tự, nhãn không đổi; lưu hash riêng cho plan trước/sau.

Chế độ hiện tại ưu tiên an toàn bằng trích xuất, nên Qwen chưa được phép tự viết
lại dữ kiện cuối theo ý mình. Chi phí gọi model còn là điểm cần tối ưu sau khi
Minh tích hợp QueryContext và có review đủ ý từ Tú; không nới guard chỉ để giảm fallback.

## 6. Quyết định tiếp theo

1. Giữ **1.7B** mặc định vì cân bằng tốc độ, bộ nhớ và contract; giữ **4B** sẵn để
   thử tiếp trên DEV_V2. Script Docker G4 cho phép chọn cả hai.
2. Ưu tiên sửa **field intent và lấy đủ evidence** cùng Minh. Recall@5 của retrieval
   hiện tại chỉ 80%; tăng model không khắc phục việc thiếu nguồn đúng trường.
3. Chưa thêm dense/reranker vào thí nghiệm này. Chưa có thử nghiệm trực tiếp để
   kết luận chúng kém hơn; cần sửa lexical routing trước rồi đo riêng từng thay đổi.
4. Chờ Tú/reviewer cung cấp evaluation V2, review nội dung và giữ TEST_V2 kín.
   Sau khi ghép context của Minh, Hoan chạy gate một lần trên bản đã khóa.
5. Chưa fine-tune: thiếu đánh giá nội dung độc lập và chưa có bộ SFT riêng chống leakage.

## 7. Artifact và tái lập

Code:

- `scripts/evaluate-g4-dev.py`: khóa DEV / gold-evidence DEV và tổng hợp.
- `ai-service/scripts/benchmark_local.py`: replay qua provider thật, ghi first attempt,
  retry/fallback/latency; kiểm model mount read-only, alias, artifact hash và runtime image.
- `scripts/demo-g4.ps1`: mở/tắt G4 riêng, mặc định 1.7B, Web `http://localhost:3004`.
- `scripts/smoke-g4-private.py` và `scripts/smoke-g4-browser.mjs`: API/E2E trình duyệt thật.

Artifact private nằm ở `evaluation/reports/g4-model-selection/` (đã ignored), gồm
`dev-frozen.json`, `dev-gold-evidence.json`, `dev-plan-v2.json`, `dev-gold-plan-v2.json`,
`qwen*-r2-seed*.json`, `qwen*-gold-seed*.json`, `summary-final-*.json`.
Không gửi các JSON này lên Git: chúng chứa câu hỏi/evidence/output công ty.

Hash fixture nhánh A: `ef92df2744836b5edc0205416dbc694d882384d836b083ccc93ebe3a9055bf6a`.
Hash fixture nhánh B: `f277ae5094d1d6e2ed0d24b5d2e3877ab09910b23580dd284ef53b576415e80f`.
Corpus phục vụ (không gồm gold/evaluation): `3cf57b03c3c10d580e1dfe298b08728dd910198379c80bc30c338ed6d0e99181`.

Model và xuất xứ:

| Artifact | SHA-256 |
|---|---|
| Qwen3-0.6B-Q8_0.gguf | `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031` |
| Qwen3-1.7B-Q8_0.gguf | `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| qwen3-4b-instruct-2507-q8_0.gguf | `ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1` |

0.6B lấy từ [kho GGUF chính thức Qwen](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF).
4B dùng [artifact của ggml-org](https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF/tree/e6f794d44f9395d0184a966c27b5ae99ea356fcb).
1.7B là artifact G3 đang có, được hash lại, không tải lại trong đợt này.
4B Instruct-2507 chỉ hỗ trợ non-thinking theo [model card Qwen](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
Các số thực nghiệm trong báo cáo do chạy local, không lấy từ benchmark trên model card.
