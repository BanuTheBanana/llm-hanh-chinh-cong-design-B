# Lộ trình dài hạn – từ nền tảng cơ bản đến trợ lý hành chính chuyên biệt

> Điều chỉnh 12/09/2026 theo mentor: ưu tiên [mốc 5 ngày làm việc cho model đã fine-tune,
> intent và context](giai-doan-5/08-ke-hoach-intent-context-finetune.md), feedback làm sau.
> Kế hoạch này thay thứ tự và thời lượng gần hạn ở phần G5 dưới đây. Demo10 G5 đã chạy,
> nhưng yêu cầu mới chưa hoàn thành. Các chặng dài hạn và số liệu lịch sử vẫn được giữ.

Ngày lập: 11/09/2026. Bản kế hoạch để Hoan và nhóm review, áp dụng cho công việc sau G4.
Các thời lượng, quy mô và chỉ tiêu dưới đây là mục tiêu đề xuất, không phải kết quả đã đạt.

## 1. Hướng đi được chọn

**Chặng lớn tiếp theo: G5 – Trợ lý hành chính chuyên biệt, nhẹ và có khả năng cập nhật nguồn.**

Đầu ra là một phiên bản sản phẩm tiến bộ rõ rệt: hiểu câu hỏi và hội thoại tự nhiên hơn,
tra cứu phạm vi rộng hơn có kiểm soát, có thử nghiệm fine-tuning Qwen, có bản lượng tử
hóa được đo chất lượng và có kết nối MCP lấy thông tin từ nguồn được phép.

Giai đoạn được đặt theo năng lực sản phẩm. Công việc hằng ngày là task trong giai đoạn;
các mốc G5.1–G5.5 là các phần nhỏ của cùng một chặng, không phải năm dự án mới.

Yêu cầu công ty trong ảnh gồm: model lightweight, lượng tử hóa, fine-tuning, trả lời
đúng trọng tâm và kết hợp MCP cập nhật thông tin. Hành chính công là miền triển khai
đầu tiên; việc mở rộng sang lĩnh vực pháp lý khác nằm ở chặng sau, theo dữ liệu và nhu cầu.

## 2. Điểm xuất phát thực tế

| Đã có | Khoảng cách cần xử lý |
|---|---|
| Web, Backend, PostgreSQL, RAG, Qwen local, Docker và lịch sử hội thoại | Cần nâng chất lượng sử dụng ngoài các mẫu demo quen thuộc |
| Corpus được duyệt cho demo: 10 thủ tục, 49 fragment | Cần bổ sung nguồn, phạm vi, phiên bản và độ phủ từng trường |
| Intent theo field, AnswerPlan, verifier, context trong conversation | Khả năng hiểu câu nối tiếp còn yếu trên tập thử mới |
| So sánh pilot 0.6B/1.7B/4B; 1.7B Q8_0 làm mặc định | Chưa chọn model fine-tune dựa trên đánh giá nội dung; chưa huấn luyện |
| TEST_V2 và TEST_V3 đã có kết quả | Chưa đạt gate G4 đã đặt; chưa thể coi DEV/demo pass là nghiệm thu độc lập |

G3 là mốc nền tảng đã hoàn thành. G4 đã tích hợp các cải tiến nhưng còn nợ chất lượng.
Kế hoạch này cho phép tiếp tục phát triển, đồng thời giữ nguyên kết quả chưa đạt trong
[biên bản G4](giai-doan-4/07-nghiem-thu-giai-doan-4.md). Không đổi kết quả lịch sử thành PASS.

## 3. Các chặng lớn

| Chặng | Năng lực sản phẩm khi hoàn thành | Phạm vi triển khai |
|---|---|---|
| Nền tảng G1–G4 | Hệ thống chạy thật, có nguồn, lưu hội thoại; biết các hạn chế hiện tại | Giữ làm baseline và sửa các lỗi cốt lõi ở đầu G5 |
| **G5 – Chuyên biệt hóa và cập nhật nguồn** | Trợ lý có chất lượng đo được trên miền hành chính đã chọn; có kết quả fine-tune/quantization và MCP hoạt động | Một miền nghiệp vụ hẹp, một model phục vụ, một nguồn kết nối MCP |
| **G6 – Sản phẩm thử nghiệm nội bộ** | Một nhóm người dùng thật có thể dùng ổn định và được hỗ trợ khi gặp lỗi | Tài khoản/quyền, hồ sơ người dùng, quản trị dữ liệu, theo dõi vận hành và phản hồi |
| **G7 – Mở rộng và nâng cao** | Nhiều nhóm thủ tục hoặc lĩnh vực pháp lý; hướng dẫn theo tình huống và nhiều nguồn cập nhật | Mở từng miền có dữ liệu, chuyên môn review và kết quả đánh giá riêng |

Ước lượng ban đầu: G5 khoảng **6–8 tuần**, G6 khoảng **4–6 tuần** sau khi đủ điều kiện.
Đây là khung lập kế hoạch cho nhóm ba người, cần điều chỉnh theo quỹ giờ OJT, dữ liệu
và phần cứng. G7 chưa chốt thời lượng khi chưa có phạm vi sử dụng thực tế.

## 4. Phạm vi cụ thể của G5

### G5.1 – Chuẩn hóa dữ liệu và cách đánh giá (dự kiến tuần 1)

- Chọn 1–2 nhóm nghiệp vụ để làm sâu. Audit phần dữ liệu công ty còn lại; mục tiêu
  khoảng 20–30 thủ tục được duyệt nếu nguồn đủ, không ép đưa bản thiếu/conflict vào phục vụ.
- Khóa danh sách thủ tục/trường được hỗ trợ sau audit. Báo rõ trường nào có nguồn,
  thiếu nguồn, chưa rõ phạm vi hoặc cần kiểm chứng; giữ demo10 làm mốc đối chiếu.
- Chuẩn hóa provenance, field, fragment, thời điểm kiểm tra, hiệu lực khi có nguồn;
  có phiên bản, hash và đường quay lại corpus trước.
- Phân loại lỗi G4 thành dữ liệu, nhận diện ý, giữ ngữ cảnh, truy xuất, sinh đáp án
  và kiểm chứng. Rà lại thước đo để tránh gộp các loại lỗi khác nhau.
- Lập bộ phát triển dùng lâu dài: TRAIN cho fine-tune, DEV để chọn cấu hình,
  regression để giữ các lỗi đã sửa. Tú chuẩn bị nhãn SFT từ mốc này.

**Đầu ra:** danh sách phạm vi G5, corpus phiên bản mới, bộ phát triển và rubric chấm
nội dung. Có thể chuẩn bị model/MCP song song; dữ liệu được phát hành theo phần đã duyệt.

### G5.2 – Nâng khả năng hiểu và tìm đúng thông tin (dự kiến tuần 2–3)

- Xử lý câu nối tiếp, câu nhiều ý, sửa thông tin đã nói, chuyển thủ tục và phạm vi
  địa phương; giữ nguồn của thông tin người dùng đã xác nhận.
- Phát triển cơ chế nhận diện ý có cấu trúc: trường hợp rõ dùng logic hiện có;
  trường hợp khó thử Qwen trích xuất intent/context có schema, Backend kiểm tra trước khi dùng.
- So sánh lexical hiện tại với một phương án kết hợp từ khóa và embedding; chỉ thêm
  reranker nếu đo được bằng chứng đúng đã có trong ứng viên nhưng thường xếp thấp.
- Hướng dẫn hồ sơ và bước tiếp theo từ trường dữ liệu được duyệt. Checklist theo
  điều kiện chỉ mở cho thủ tục có đủ dữ kiện và quy tắc; thiếu thì hỏi làm rõ.
- Chấm riêng câu trả lời của model trước verifier và câu cuối người dùng nhận để
  biết phần nào cải thiện nhờ model, phần nào nhờ trích xuất an toàn.

**Đầu ra:** bản tra cứu/hội thoại tốt hơn baseline trên bộ phát triển đa dạng và có
bảng lỗi còn lại. Giữ thay đổi có lợi; kết quả thử không có lợi cũng được lưu và kết thúc.

### G5.3 – Chọn model, fine-tune và lượng tử hóa (dự kiến tuần 4–5)

- Dùng Qwen3-1.7B hiện tại và Qwen3-4B-Instruct-2507 làm hai ứng viên đầu tiên,
  kế thừa [pilot đã có](giai-doan-4/04-ket-qua-so-sanh-qwen.md). Chưa gọi ứng viên nào
  là tốt nhất. Không mở cuộc thi nhiều model khi hai ứng viên đã đủ để ra quyết định.
- So cùng evidence đúng trên DEV để chấm nội dung, điều kiện, mức độ đúng trọng tâm
  và khả năng hỏi lại; đồng thời đo toàn luồng để tính chi phí nhận diện/truy xuất.
- Chọn một checkpoint để thử SFT bằng LoRA/QLoRA. Mục tiêu học hành vi: trả lời
  ngắn đúng ý theo evidence, giữ điều kiện, hỏi lại khi thiếu dữ kiện và dùng schema đúng.
- Khởi đầu khoảng 300–800 mẫu đã review nếu đủ nhóm tình huống khác nhau. Số paraphrase
  không thay thế độ đa dạng; split cả nhóm và cả hội thoại trước khi tạo biến thể.
- Thử tối đa hai cấu hình adapter trong vòng đầu; so model gốc và fine-tune trên cùng
  DEV. Nếu chưa cải thiện, ghi nguyên nhân và quyết định sửa dữ liệu hoặc giữ model gốc.
- Huấn luyện từ checkpoint tương thích với thư viện training; bản GGUF Q8_0 hiện tại
  dùng làm baseline inference. Sau huấn luyện mới xuất artifact phục vụ và so Q8 với Q4;
  thử Q5 nếu Q4 làm giảm chất lượng đáng kể.
- Đo chất lượng, kích thước model, VRAM, thời gian phản hồi và timeout trên máy đích.
  Bắt đầu bằng bài thử vừa bộ nhớ trước khi chạy huấn luyện đầy đủ.

**Đầu ra bắt buộc:** bộ SFT phiên bản hóa, adapter thử nghiệm, báo cáo trước/sau và
quyết định model phục vụ. Chỉ triển khai adapter khi có lợi; hoàn thành thí nghiệm
fine-tune và chọn adapter để vận hành là hai quyết định khác nhau.

QLoRA kết hợp trọng số lượng tử hóa với adapter LoRA để giảm nhu cầu bộ nhớ training;
đó là cơ sở chọn thử nghiệm nhỏ này, không phải bằng chứng sẽ tăng chất lượng dự án.
[Tài liệu PEFT](https://huggingface.co/docs/peft/developer_guides/quantization).

### G5.4 – Cập nhật tri thức qua MCP (dự kiến tuần 6)

- Kết nối **một MCP server** với 1–2 công cụ đọc: tra cứu thủ tục đã duyệt và kiểm tra
  phiên bản/nguồn mới từ một nguồn được phép. Backend điều phối tool có tham số được kiểm tra.
- Có luồng: phát hiện thay đổi → lưu snapshot → đối chiếu phiên bản → review → phát hành
  vào kho phục vụ. Hiển thị thời điểm kiểm tra nguồn và phiên bản đang dùng.
- Nguồn/tool lỗi thì dùng bản đã duyệt kèm trạng thái độ mới, hoặc thông báo chưa xác minh;
  nội dung công cụ trả về không được coi là chỉ thị điều khiển hệ thống.
- Đo riêng thời gian phát hiện thay đổi và thời gian đến khi bản mới được duyệt/phục vụ.
  MCP không tự bảo đảm dữ liệu đúng, đủ hoặc cập nhật tức thì; độ trễ phụ thuộc nguồn và quy trình.
- Nếu chưa có API/feed bên ngoài được phép truy cập, tích hợp MCP với kho nội bộ trước;
  ghi rõ phần cập nhật nguồn ngoài còn thiếu, chưa tuyên bố đáp ứng realtime đầy đủ.

**Đầu ra:** demo cập nhật một nguồn có phiên bản, truy cập qua MCP và quay lại bản cũ.
Khi demo bằng nguồn giả lập phải ghi rõ đó là kiểm thử cơ chế cập nhật.

MCP chuẩn hóa kết nối ứng dụng AI với tools/resources. Cách dùng một connector đọc
trong G5 là lựa chọn phạm vi của dự án. [Kiến trúc MCP](https://modelcontextprotocol.io/docs/learn/architecture).

### G5.5 – Tích hợp và đánh giá cuối chặng (dự kiến tuần 7–8)

- Ghép dữ liệu, hội thoại, model được chọn và MCP vào Web/Docker.
- UI có checklist đơn giản khi đủ nguồn, nguồn/phiên bản rõ, trạng thái chờ và gửi lại
  khi lỗi. Chưa stream nội dung nhạy cảm chưa qua kiểm chứng ra màn hình.
- Chạy kịch bản sử dụng từ đầu đến cuối, đo tải nhỏ trên máy đích và làm hướng dẫn demo.
- Đóng băng một candidate; đánh giá một đợt nghiệm thu của cả chặng, ghi quyết định
  đạt, đạt một phạm vi giới hạn được xác định trước, hoặc chưa đạt cần sửa nhóm lỗi cụ thể.

**Demo cuối chặng:** người dùng nêu nhu cầu → hệ thống hỏi thêm dữ kiện cần thiết →
trả hồ sơ/phí/thời gian có nguồn → hỏi tiếp hoặc đổi thủ tục → quản trị viên cập nhật
nguồn qua quy trình MCP → câu trả lời dùng bản mới đã duyệt mà không cần train lại.

## 5. Đánh giá để phát triển, không lặp tạo TEST vô hạn

1. **Trong chặng:** dùng TRAIN/DEV/regression lặp lại để tìm và sửa lỗi. Các bộ TEST
   cũ có thể được chuyển thành bộ chẩn đoán sau khi ghi rõ đã mở; mọi kết quả sau đó
   là regression, không còn là đo khả năng tổng quát hóa độc lập. Cất bản gốc/kết quả cũ.
2. **Cuối chặng:** chuẩn bị holdout mới theo nhóm hội thoại/tình huống đã thiết kế,
   chỉ chấm sau khi chọn candidate bằng DEV. Không tạo TEST mới sau mỗi lỗi nhỏ,
   cũng không chọn candidate bằng cách thử nhiều TEST rồi lấy lần đạt.
3. **Nếu chưa đạt:** phân tích nhóm nguyên nhân, phạm vi và kế hoạch sửa; chưa gọi
   phiên bản đó đạt. Chỉ tổ chức đợt nghiệm thu mới khi có cải tiến đáng kể đã được chứng minh trên DEV.
4. **Vai trò:** Hoan có quyền giữ/review bộ đánh giá. Khi Hoan hoặc trợ lý đã dùng
   câu/nhãn để sửa hệ thống, ghi bộ đó là đã thấy; chức danh leader không làm mất ảnh hưởng này.
5. **Đo đúng:** sai status/citation ở field phí không tự đồng nghĩa đã bịa số tiền.
   Phân biệt từ chối quá mức, thiếu ý và claim sai. Chỉ gọi “đúng toàn hội thoại” khi
   chấm đủ các lượt cần trả lời; nếu chỉ chấm lượt cuối phải ghi rõ.
6. **Tách dữ liệu:** tri thức nguồn có thể nằm trong RAG của bài toán tra cứu mở sách;
   câu/nhãn holdout không vào TRAIN, ví dụ prompt hoặc index. Tách nhóm trước sinh paraphrase.

Mục tiêu nghiệm thu G5 đề xuất, khóa định nghĩa và tập tình huống trước khi đo:

| Nội dung | Mục tiêu |
|---|---|
| Trả lời và hội thoại | ≥90% câu đủ dữ liệu đúng/đủ ý theo reviewer; ≥90% kịch bản đúng các lượt cần chấm |
| Lấy nguồn | Field accuracy và Recall@5 ≥90%; công bố số đúng/tổng và phạm vi được đo |
| Dữ kiện quan trọng | Không có claim sai về phí, thời gian, nơi nộp hoặc bỏ điều kiện trong bộ trọng yếu |
| Model lightweight | Có quyết định dựa trên chất lượng và tài nguyên; artifact chạy được trên máy đích |
| MCP/cập nhật | Tra cứu qua tool thành công, phiên bản mới chỉ phục vụ sau review; rollback và lỗi nguồn được kiểm thử |
| Sử dụng | Web/Docker, history, gửi lại và cách ly user qua; đo P50/P95 ở tải nhỏ, chốt ngân sách độ trễ ở G5.1 |

Các ngưỡng là mục tiêu kỹ thuật nội bộ. Báo riêng nhóm thiếu nguồn, câu hỏi lại và
phạm vi chưa hỗ trợ; không giảm mẫu khó sau khi thấy kết quả để nâng tỷ lệ đạt.

## 6. Chia việc và kiểm soát phạm vi

| Thành viên | Trách nhiệm xuyên suốt G5 |
|---|---|
| Tú | Nguồn/coverage, dữ liệu chuẩn hóa, nhãn SFT/evaluation, review thay đổi và checklist theo nguồn |
| Minh | Hiểu intent/context, truy xuất, phiên bản kho dữ liệu, công cụ MCP và tích hợp Backend |
| Hoan | Chọn model, fine-tune/quantization, AnswerPlan/verifier, thí nghiệm, Web/Docker và điều phối tích hợp |

Mỗi người giữ một task chính đang làm. Tích hợp và demo mỗi tuần; tổng kết theo
mốc G5.1–G5.5. Dữ liệu phục vụ và dữ liệu training cần chốt trước khi chạy thí nghiệm
phụ thuộc chúng; thiết kế MCP có thể chuẩn bị sớm. Chỉ thay một yếu tố chính trong
mỗi so sánh. Feature mới ngoài phạm vi phải thay thế một việc đã lên kế hoạch hoặc chờ G6/G7.

G5 chưa triển khai: nhiều lĩnh vực luật cùng lúc, nhiều agent, train từ đầu, full
pretraining, nhiều kho vector/model song song, tự nộp hồ sơ/thanh toán, memory nhiều
hồ sơ xuyên conversation, OCR tài liệu cá nhân và hạ tầng phân tán quy mô lớn.

## 7. Sau G5 phát triển gì?

**G6 – Sản phẩm thử nghiệm nội bộ:** đăng nhập và quyền thật; một hồ sơ có checklist,
tiến độ và thông tin người dùng xác nhận; trang quản trị nguồn/review; thu phản hồi;
giám sát lỗi, backup/restore, kiểm thử tải và tài liệu vận hành. Chỉ thêm queue/streaming
hoặc dịch vụ hạ tầng mới khi số đo tải và trải nghiệm cho thấy cần.

**G7 – Mở rộng và nâng cao:** nhiều hồ sơ, nhiều nguồn và địa phương; hướng dẫn có
điều kiện sâu hơn; upload/OCR khi có nhu cầu; thêm miền pháp lý sau khi đủ dữ liệu và
người review. Mỗi miền có coverage và đánh giá riêng. Fine-tune, distillation hoặc
reranker được tiếp tục nếu phân tích lỗi cho thấy lợi ích.

Việc bắt đầu ngay sau khi thống nhất lộ trình là **G5.1: chốt miền nghiệp vụ, dữ liệu
và thước đo cho toàn chặng**, đồng thời chuẩn bị SFT/model và contract MCP. Không yêu
cầu Tú tạo TEST_V4 ngay để làm điều kiện bắt đầu kế hoạch này.
