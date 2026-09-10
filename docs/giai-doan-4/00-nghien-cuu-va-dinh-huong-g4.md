# Định hướng sau G3: trả lời đúng ý, đúng nguồn và nối tiếp hội thoại

Ngày tổng hợp: 10/09/2026. Trạng thái: đề xuất phạm vi G4 sau khi đọc kế hoạch cũ, đối chiếu code và nghiên cứu nguồn công khai. Chưa triển khai G4 hoặc chạy benchmark model mới.

## 1. Quyết định đề xuất

Tiếp tục đánh số **G4 – Nâng chất lượng trả lời và hội thoại ngắn** trên nền G1–G3. Mục tiêu là người dùng hỏi tự nhiên, hỏi tiếp và nhận đúng thông tin trong phạm vi dữ liệu đã duyệt.

Thứ tự: **chuẩn đánh giá → intent/evidence → kiểm chứng nội dung → hội thoại ngắn → mở rộng dữ liệu → thử model/retrieval khi còn lỗi**. Giữ Qwen3-1.7B Q8_0 làm baseline; chưa đưa fine-tune thành yêu cầu bắt buộc.

G3 vẫn là mốc hoàn thành hệ thống cơ bản để demo nội bộ. G4 phải chứng minh chất lượng sử dụng tiến bộ bằng những ca kiểm thử cụ thể.

## 2. Đọc lại kế hoạch ban đầu

Ba tài liệu được dùng để đối chiếu:

- [Khung dự án ban đầu](../archive/2026-09-07/khung-du-an-LLM.md).
- [Kiến trúc mục tiêu v1.2 trước khi thu nhỏ phạm vi](../parked/kien-truc-muc-tieu-v1.2/00-workflow-tong-quat.md).
- [Chiến lược xây từ nhỏ đến lớn](../00-chien-luoc-trien-khai-tu-nho-den-lon.md).

Đích cũ là trợ lý hành chính công: hiểu tình huống, nhớ đúng hồ sơ, tìm thủ tục đúng phạm vi/phiên bản, hướng dẫn có điều kiện và kiểm chứng nguồn. Đích đó vẫn phù hợp. Các số giai đoạn trong tài liệu lưu trữ thuộc lộ trình cũ; không đồng nhất với G1–G3 đã demo.

| Nội dung trong kế hoạch cũ | Cách đưa trở lại lộ trình |
|---|---|
| Query Envelope, Evidence Gate, kiểm claim | G4: làm bản nhỏ cho câu hỏi theo trường thông tin |
| Case Card và memory | G4: ngữ cảnh trong một conversation; G5 mới quản lý nhiều hồ sơ xuyên conversation |
| Hybrid retrieval và reranker | Thử nghiệm có đối chứng sau khi sửa intent; triển khai nếu cải thiện |
| Procedure Engine | G4 giữ nguyên điều kiện của nguồn; checklist theo hoàn cảnh chỉ mở khi có dữ liệu điều kiện đủ rõ |
| Fine-tune, lượng tử hóa, so sánh 1.7B/4B | So sánh trước, huấn luyện khi xác định lỗi thuộc model |
| MCP và cập nhật dữ liệu | G5: công cụ đọc nguồn có kiểm soát và quy trình duyệt/publish phiên bản |
| Queue, streaming, upload, auth thật | G5/G6 theo nhu cầu sử dụng và tải thực tế |

Header của roadmap cũ còn ghi G3 đang chờ review. Để xác định mốc đã hoàn thành, dùng [biên bản G3 cập nhật 10/09](../giai-doan-3/05-bao-cao-tich-hop-va-dieu-kien-nghiem-thu-g3.md) và [tổng kết G1–G3](../bao-cao-tong-ket-giai-doan-1-den-3.md), không lấy trạng thái cũ làm trạng thái hiện tại.

## 3. Khoảng cách đã xác nhận

Đối chiếu trên nhánh `g3/integration`, commit `62ef10f`. Số benchmark dưới đây lấy từ hồ sơ G3, không phải lượt đo mới.

| Nội dung | Bằng chứng | Hệ quả cho G4 |
|---|---|---|
| Nền tảng đã chạy | 10 procedure, 49 fragment; Qwen local, RAG, Web, history, Docker | Kế thừa bản demo hiện tại |
| Retrieval còn bỏ sót | Recall@5 DEV 80%, TEST 75%; TEST chỉ 9 câu | Cần bộ đánh giá lớn và đa dạng hơn |
| Intent chưa vững | Chạy trực tiếp logic hiện tại: “Đăng ký khai sinh nộp hồ sơ ở đâu?” → `required_documents`; “Đăng ký khai sinh nộp ở đâu?” → `receiving_authority` | Sửa nhận diện ý hỏi, tránh từ “hồ sơ” lấn át ý hỏi nơi nộp |
| Chưa có ngữ cảnh cho RAG | `chat.py` tải history nhưng nhánh RAG chỉ truyền câu hiện tại và filters | “Còn lệ phí thì sao?” chưa được gắn thủ tục từ lượt trước |
| Verifier chủ yếu kiểm binding | Kiểm ID nguồn, request, version, schema và status; chưa đối chiếu đầy đủ nội dung phát biểu | Citation hợp lệ không chứng minh phí, thời hạn hoặc nơi nộp đúng |
| Dữ liệu còn giới hạn | Demo10 đã được phép demo nội bộ; audit toàn workbook ghi 42 source, 38 procedure ứng viên và 4 conflict | Mở rộng theo dữ liệu đã review, không tự coi 38 ứng viên là 38 thủ tục chính thức |

Code đối chiếu: [retrieval G3](../../backend/app/rag/g3/retrieval.py), [chat](../../backend/app/chat.py), [grounding Backend](../../backend/app/rag/grounding.py), [grounding AI](../../ai-service/app/grounding.py). Kiểm tra intent là chẩn đoán riêng lẻ, không phải chạy lại E2E hoặc TEST kín.

## 4. Nghiên cứu và điều áp dụng cho dự án

Các quyết định ở cột cuối là đề xuất cho dự án, không phải kết quả thực nghiệm đã đạt.

| Nguồn đã đọc | Kết quả/khả năng liên quan | Áp dụng |
|---|---|---|
| [LegalBench-RAG](https://arxiv.org/abs/2408.10343) | Đánh giá retrieval theo đoạn văn liên quan chính xác, thay vì chỉ lấy đúng tên tài liệu | Đo đúng fragment và đúng trường thông tin; không dừng ở procedure accuracy |
| [ALCE, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.398/) | Tách chất lượng câu trả lời và chất lượng citation | Bổ sung kiểm nội dung được nguồn hỗ trợ và các ý còn thiếu |
| [DRiLL, VLSP 2025](https://aclanthology.org/2025.vlsp-1.20.pdf) | Retrieval luật tiếng Việt dùng BM25 + BGE-M3, tiêu đề phân cấp và reranker | Thử thêm tên thủ tục + tên mục vào văn bản truy xuất; sau đó mới thử hybrid. Bài toán truy xuất điều luật khác dataset thủ tục của nhóm |
| [BGE-M3 model card](https://huggingface.co/BAAI/bge-m3) | Hỗ trợ retrieval đa ngôn ngữ, dense/sparse/multi-vector | Là ứng viên dense tham chiếu từ kế hoạch cũ; không cần bật cả ba chế độ |
| [Qwen3 Embedding/Reranker](https://qwenlm.github.io/blog/qwen3-embedding/) | Có embedding và reranker riêng cỡ 0.6B, hỗ trợ đa ngôn ngữ | Thử một embedding trước; reranker là bước sau nếu ranking còn yếu |
| [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) | Model 4B instruct chỉ non-thinking | Ứng viên so sánh với 1.7B trên cùng evidence; chưa có căn cứ chọn làm model chính |
| [QLoRA](https://arxiv.org/abs/2305.14314) | Huấn luyện adapter trên model lượng tử hóa để giảm nhu cầu bộ nhớ | Dùng cho pilot SFT hành vi nếu evidence đúng mà model vẫn sai lặp lại |
| [MCP: Architecture overview](https://modelcontextprotocol.io/docs/learn/architecture) | Chuẩn kết nối tools/resources với ứng dụng AI | Sau này bọc công cụ đọc Procedure Store/nguồn; độ mới và độ tin cậy vẫn cần pipeline cập nhật, kiểm tra và duyệt |

Không lấy điểm benchmark công khai làm độ chính xác trên dữ liệu công ty. Lượt nghiên cứu này chỉ tra cứu kỹ thuật công khai, không tải nội dung workbook lên dịch vụ ngoài.

## 5. Phạm vi G4 và thứ tự thực hiện

### G4-A — Bộ đánh giá và lỗi gốc

- Khóa snapshot code/model/corpus G3 để so sánh và quay lại demo.
- Giữ câu đã dùng trong demo hoặc đã phân tích lỗi thành regression đã biết.
- Tạo DEV mới và TEST_V2 độc lập, có câu tự nhiên, không dấu, nhiều ý, thiếu dữ kiện, sai phạm vi và hội thoại nối tiếp.
- Ghi đáp án theo ý bắt buộc, ý cấm, field, fragment và trạng thái; review chéo.
- Phân loại lỗi: dữ liệu, nhận diện thủ tục, intent, retrieval, diễn giải, kiểm chứng, ngữ cảnh.

### G4-B — Đúng ý hỏi và đúng evidence

- Tách “đang hỏi thủ tục nào” khỏi “đang hỏi thông tin gì”. Phân biệt hồ sơ, phí, thời gian, nơi nộp và hình thức nộp.
- Ưu tiên cấu trúc câu hỏi; hỗ trợ biến thể “nộp hồ sơ ở đâu”, “đến đâu làm”, “cần tới cơ quan nào”.
- Một câu hỏi nhiều ý phải có evidence cho từng ý. Nếu thiếu, trả phần có nguồn và nêu rõ phần thiếu khi contract mới hỗ trợ; nếu chưa hỗ trợ thì dùng trạng thái an toàn hiện có.
- Tận dụng `field_evidence` và `missing_fields`; không tăng Top-K để che việc chọn sai field.
- Giữ Top-5 làm mốc so sánh, trần hiện tại 8 fragment. Candidate pool lớn hơn để thử rerank phải tách khỏi bundle gửi model.
- Bổ sung ngữ cảnh tiêu đề/mục cho truy xuất, giữ nội dung nguồn nguyên gốc riêng để citation truy ngược được.

### G4-C — Kiểm đúng nội dung và hỏi nối tiếp

- Tạo AnswerPlan tối thiểu: ý cần trả lời, giá trị, điều kiện và ID evidence hỗ trợ.
- Render trường quan trọng từ dữ liệu đã duyệt: mức phí, đơn vị, thời gian, nơi nộp. Với mô tả chưa parse chắc, giữ nguyên câu nguồn và điều kiện; không ép thành một con số.
- Qwen diễn giải trong phạm vi AnswerPlan; trường không có nguồn không được bổ sung từ kiến thức model.
- Kiểm claim trước khi gửi; fallback trích xuất cũng phải dùng đúng field và giữ điều kiện. Kiểm rule không thay thế được toàn bộ đánh giá ngữ nghĩa của người review.
- Lưu ngữ cảnh nhỏ trong conversation: thủ tục đang nói, địa phương user đã nêu, field đang hỏi và câu làm rõ đang chờ; mỗi fact có message nguồn.
- Nhận câu nối tiếp như “còn lệ phí?”, “bao lâu?”, ưu tiên thông tin mới người dùng nêu và hỏi lại khi không rõ đang nói thủ tục nào.
- Ngữ cảnh phải qua kiểm tra ownership và còn đúng sau refresh. Chưa mở memory nhiều hồ sơ xuyên conversation.

Luồng mục tiêu:

```text
Câu hiện tại + ngữ cảnh đã xác nhận
→ xác định thủ tục và ý hỏi
→ lấy đúng field/evidence, kiểm phạm vi và phần thiếu
→ lập nội dung cần trả lời
→ render dữ kiện + Qwen diễn giải khi cần
→ kiểm claim/citation
→ lưu ngữ cảnh, hiển thị câu trả lời và nguồn
```

### G4-D — Mở rộng và chọn cấu hình bằng thực nghiệm

- Ổn định các ca trên demo10 trước; mở rộng từng đợt nhỏ trong phần dữ liệu còn lại sau review nguồn, conflict và field thiếu.
- Thống kê coverage theo từng field; không chỉ báo số thủ tục. Chưa biết mã chính thức, URL hoặc hiệu lực thì giữ trạng thái chưa xác minh.
- Mỗi đợt có version/hash, validate và đường quay lại corpus trước. Cập nhật kho dữ liệu không kéo theo fine-tune.
- Chỉ thử dense/reranker hoặc đổi generator sau khi có bảng lỗi và bộ đánh giá đã khóa thiết kế.

## 6. Thiết kế thử nghiệm và chống leakage

Phân biệt **tri thức để tra cứu** với **đáp án để chấm điểm**: tài liệu nguồn của câu TEST có thể nằm trong RAG trong bài toán tra cứu mở sách. Câu TEST, đáp án, expected points và nhãn đánh giá không được đưa vào prompt mẫu, training hoặc index phục vụ.

Mục tiêu khởi đầu đề xuất: khoảng 120 scenario, khoảng 80 DEV và 40 TEST_V2. Một scenario có thể là một câu hoặc cả cuộc hội thoại; nên có ít nhất 20 scenario nhiều lượt. Đây là quy mô dự kiến, chưa phải dữ liệu đã tạo.

- Chia theo nhóm tình huống trước khi viết paraphrase; cả hội thoại và các biến thể cùng nhóm ở cùng split.
- Câu và thủ tục đã dùng để chỉnh hệ thống phải được ghi nhận là đã thấy. TEST_V2 trên cùng 10 thủ tục chỉ đánh giá tình huống mới trong phạm vi đã biết.
- Muốn đo khả năng xử lý thủ tục mới, dành riêng một số procedure family chưa dùng để tuning trong phần corpus mở rộng; báo cáo nhóm này riêng.
- TEST G3 đã công bố giữ làm mốc lịch sử/regression. Khóa TEST_V2 với reviewer giữ nhãn; không mở từng lỗi TEST để chỉnh rồi vẫn gọi đó là test kín.
- Dùng DEV chọn prompt, threshold và cấu hình. Sau khi chốt, đánh giá một lần trên TEST_V2; thay đổi sau đó thuộc release tiếp theo.
- D2 và mọi dữ liệu dẫn xuất tiếp tục nằm trong vùng private/local. Báo cáo chung chỉ ghi số tổng hợp.

| Thí nghiệm | So sánh | Giữ cố định |
|---|---|---|
| E0 | G3 và từng cải tiến intent/field, kiểm claim, context | Model 1.7B, corpus và tập scenario; bật từng thay đổi |
| E1 | Exact/BM25 đã sửa và thêm một dense model: Qwen3-Embedding-0.6B hoặc BGE-M3 | Intent, corpus, generator và output budget |
| E2 — có điều kiện | Candidate pool của cấu hình E1 thắng: không rerank và Qwen3-Reranker-0.6B | Cùng candidate pool; chỉ chạy nếu bằng chứng đúng đã có nhưng bị xếp thấp |
| E3 — có điều kiện | 1.7B Q8_0 và Qwen3-4B-Instruct-2507 với artifact ghi rõ | Cùng câu, gold evidence và retrieved evidence; cùng budget; ghi khác biệt quantization |

Không gộp thay model, đổi quantization và đổi retrieval thành một kết quả để quy công cho model. Có thể thêm BGE-reranker từ kế hoạch cũ làm đối chứng sau nếu E2 có lợi và còn ngân sách.

Đo riêng: procedure accuracy, field accuracy, Recall@5, câu trả lời đủ/đúng theo nguồn, claim không được hỗ trợ, hỏi lại/từ chối đúng, lỗi theo lượt hội thoại, tỷ lệ fallback và độ trễ toàn luồng. Báo số đúng/tổng bên cạnh phần trăm; 40 TEST vẫn là pilot nhỏ.

Đối với latency, ghi warm/cold, phần cứng, số user, token đầu vào/đầu ra, P50/P95 toàn request gồm retry/fallback, tỷ lệ timeout và bộ nhớ. Không so trực tiếp generation latency cũ với E2E latency mới.

## 7. Ngưỡng nghiệm thu G4 đề xuất

Đây là mục tiêu nội bộ để nhóm thống nhất trước khi chạy TEST_V2, chưa phải số đã đạt hoặc SLA công ty.

| Hạng mục | Điều kiện mục tiêu |
|---|---|
| Lỗi demo đã biết | Toàn bộ ca regression được chốt trước đều qua |
| Intent và retrieval | Field accuracy và Recall@5 đạt ít nhất 90% trên các ca có gold tương ứng |
| Độ đúng câu trả lời | Ít nhất 90% ca có đủ dữ liệu được trả lời đủ ý và đúng nguồn qua review; từ chối ca đủ dữ liệu tính là chưa đạt |
| Claim trọng yếu | Không có lỗi phí/thời hạn/nơi nộp hoặc bỏ điều kiện gây đổi nghĩa trong bộ kiểm tra trọng yếu |
| Thiếu nguồn/xung đột | Không tự kết luận trong toàn bộ bộ kiểm tra guard; đo riêng việc hỏi lại quá mức |
| Hội thoại ngắn | Ít nhất 90% scenario đúng toàn chuỗi; không lẫn user/conversation |
| Hạ tầng | Regression G1–G3, history và Docker demo vẫn qua; lỗi provider có thể xử lý/retry đúng |
| Chi phí và tốc độ | Đo cùng điều kiện; mục tiêu P95 E2E không tăng quá 1,5 lần baseline E2E đo lại. Nếu vượt, ghi rõ trade-off trước khi chọn |

Nếu dữ liệu chưa đủ căn cứ để người review quyết định, gắn nhãn chưa xác minh và báo coverage thiếu; không tự cho pass. “Không thấy lỗi” trong pilot không phải bảo đảm không có lỗi ngoài bộ thử.

## 8. Phân công đề xuất

| Thành viên | Ownership G4 | Việc đầu tiên và đầu ra |
|---|---|---|
| Tú | Dữ liệu, nhãn đánh giá và coverage | Review 10 procedure theo từng field; lập nhóm scenario DEV/TEST_V2; thống kê phần thiếu/conflict cần xử lý trước khi mở rộng |
| Minh | Intent, retrieval và context Backend | Sửa chọn field; tạo regression cho các cách hỏi nơi nộp; chốt lưu/truyền ngữ cảnh conversation và binding nguồn |
| Hoan | AnswerPlan, Qwen/verifier, evaluation và tích hợp | Chấm claim với evidence, so sánh baseline/candidate, đo latency/fallback; tích hợp Web/Docker và demo |

Cả nhóm thống nhất contract trước: tận dụng schema G3, thêm ngữ cảnh/AnswerPlan nhỏ; thay đổi không tương thích phải có version và regression. Người tạo gold không tự duyệt cuối toàn bộ phần mình viết; claim nghiệp vụ chưa chắc cần reviewer phù hợp.

Đợt đầu chỉ nhận ba đầu việc ở bảng trên. Kết thúc đợt phải có demo: hỏi hồ sơ → hỏi tiếp nơi nộp → hỏi phí → chuyển thủ tục khác → hỏi phần thiếu nguồn; hệ thống giữ đúng ngữ cảnh và lấy đúng field ở từng lượt.

## 9. Hướng sau G4

- **G5 – Hỗ trợ hồ sơ và cập nhật tri thức:** nhiều case, checklist có điều kiện, memory phù hợp, công cụ MCP đọc nguồn, import/review/publish/rollback và kiểm tra độ mới. Queue/streaming mở theo độ trễ và tải đo được.
- **G6 – Pilot và vận hành:** xác thực thật, quyền truy cập, giám sát, backup/restore, kiểm thử tải và người dùng; hoàn thiện artifact lightweight theo máy triển khai.
- **Nhánh model:** nếu E3 cho thấy model vẫn sai với gold evidence, mới lập tập SFT hành vi độc lập với TEST và chạy QLoRA pilot. Giữ phiên bản train/model/quantization để đo lại và rollback.

Việc bắt đầu tiếp theo là **G4-A và G4-B trên demo10**. Sau khi có số liệu, quyết định mở rộng corpus và kỹ thuật bổ sung; không đặt việc “phải fine-tune” làm tiêu chí hoàn thành giai đoạn.
