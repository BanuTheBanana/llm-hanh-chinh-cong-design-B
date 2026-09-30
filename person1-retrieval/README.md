# Person 1 — Corpus & Retrieval

Bản hoàn thiện kỹ thuật ngày 30/09/2026. Đọc `REPORT_PERSON1.md` ở gốc trước.
Giữ nguyên shape của `contracts/retrieval_input.schema.json` và `evidence_bundle.schema.json`.
BM25 là mặc định của backend; dense/hybrid chạy riêng qua CLI hoặc Python API.

## Cài và chạy (Windows PowerShell, Python 3.12)

Từ thư mục gốc `person1-completed`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\person1-retrieval[test]"
python -m person1_retrieval.cli validate --corpus person2-backend/fixtures/demo
python -m person1_retrieval.cli query --corpus person2-backend/fixtures/demo --allow-draft --query "demo alpha lệ phí và hồ sơ"
python -m person1_retrieval.cli build --corpus person2-backend/fixtures/demo --allow-draft --output local-index
python -m pytest person1-retrieval/tests -q
```

Linux: `python3.12 -m venv .venv`, `source .venv/bin/activate`, sau đó dùng cùng các lệnh `python`.
`--allow-draft` chỉ dùng để thử corpus demo. Nếu bỏ cờ, nguồn draft/không rõ ngày hiệu lực không được phục vụ.
Không dùng dữ liệu demo để tư vấn thật.

Chạy hồi quy cả Person 2 từ gốc:

```powershell
python -m pip install -r person2-backend/requirements-test.txt
$env:PYTHONPATH = "$PWD\person1-retrieval\src;$PWD\person2-backend"
python -m pytest person1-retrieval/tests person2-backend/tests -q
```

Linux dùng `PYTHONPATH=person1-retrieval/src:person2-backend python -m pytest ...`.
PostgreSQL test chỉ chạy khi có database thử nghiệm đúng hướng dẫn của Person 2.

## File cần hiểu

| File trong `src/person1_retrieval/` | Nhiệm vụ |
|---|---|
| `segmenter.py` | NFC, underthesea/pyvi, protected terms, cùng config cho query/index |
| `contracts.py` | Validate schema từ duy nhất `contracts/` ở gốc repo |
| `corpus.py` | Validate ba exports, SHA-256 text, IDs/liên kết/nguồn/supersession, snapshot fingerprint |
| `retriever.py` | Exact shortcut, BM25, filter, chọn ứng viên, top-2 theo procedure, EvidenceBundle |
| `dense.py` | Encoder local, cosine fragment + procedure, RRF 3 nhánh, xuất NPZ không pickle |
| `evaluation.py` | Đo procedure/status, field precision/recall, coverage, ambiguity recall, latency; grid DEV |
| `cli.py` | validate / build / query / evaluate / tune |

`build` ghi corpus canonical, tài liệu token, IDF và metadata segmenter. Với dense/hybrid còn ghi vector + hash/model metadata.
Runtime CLI hiện rebuild index từ ba exports đã kiểm tra; chưa có load cache index hay ANN, không tuyên bố sẵn sàng scale lớn.
Corpus snapshot chứa text: giữ local/ngoài git. Source content_hash được giữ nguyên; thiếu file nguồn gốc thì không thể kiểm chứng hash file nguồn, chỉ kiểm tra được hash text fragment và cấu trúc.

## Lựa chọn sau ambiguity

`state.unresolved_references` là danh sách ID theo đúng thứ tự Person 2 đã hiển thị.
`cái đầu tiên`, `chọn cái thứ hai`, `số 2`, `không, cái thứ hai` chọn theo thứ tự 1-based.
Chỉ nhận câu lựa chọn hoàn chỉnh; không suy đoán ordinal trong câu dài.
Kế thừa `last_requested_section_types` khi lượt chọn không nêu trường mới.
Danh sách trùng, ID đã biến mất, thứ tự vượt phạm vi: `low_confidence`.
Tên/alias mới ưu tiên hơn state. Mẫu `không phải X mà Y` dùng Y để exact-match.
Các phủ định phức tạp khác chưa có intent model và có thể cần hỏi lại.
Sau khi Person 2 đã clear unresolved list, muốn đổi thì nêu tên thủ tục; không tự dựng lại lựa chọn cũ.

`carries_context(raw,state)` giúp Person 2 giữ filters khi chọn ứng viên/follow-up,
và reset filters khi nêu thủ tục mới, kể cả câu mở đầu bằng “còn”. Explicit filters vẫn ưu tiên.
Đã nối helper này vào backend hiện có và kiểm thử state + grounding. Đây là quy ước v1 để Person 2 review, không phải chữ ký chấp thuận của người đó.

## Dense / hybrid local

```powershell
python -m pip install -e ".\person1-retrieval[dense]"
```

Cần thư mục sentence-transformers model đã tải và được nhóm lựa chọn. Không tự tải model; không gửi dữ liệu đi API.
Tùy model, cấu hình query/document prefix theo hướng dẫn riêng của model. Encoder nhận text gốc; BM25 nhận text đã tách từ.

```powershell
# Các ngưỡng bên dưới CHỈ minh họa cú pháp, chưa tune trên corpus thật.
python -m person1_retrieval.cli query --corpus path/to/approved-corpus --mode hybrid --model-path path/to/local-model --score-floor 0.02 --margin-floor 0.002 --dense-min-similarity 0.4 --query "câu hỏi cần tìm"
```

`--mode dense`: điểm procedure là max(cosine fragment, cosine mô tả procedure).
`--mode hybrid`: RRF cộng thứ hạng BM25 fragment, dense fragment, dense procedure; mặc định k=60.
Điểm bằng nhau giữ cùng rank để ID không tạo margin giả. Top-2 luôn là hai procedure khác nhau, tính trước top_k.
Bộ lọc áp dụng trước ranking. Exact/state selection chỉ bỏ qua ngưỡng confidence, không bỏ qua filters.
Mỗi procedure chỉ được chứa fragments của cùng source; source version/effective_date lấy từ manifest.
Các điểm BM25/cosine/RRF khác thang và không phải xác suất. Hybrid bắt buộc nhập ngưỡng riêng.
Model thật, chất lượng dense, CPU/GPU memory và tốc độ model chưa được kiểm chứng trong lần bàn giao này.

## Benchmark và tune

```powershell
python -m person1_retrieval.cli evaluate --corpus person2-backend/fixtures/demo --allow-draft --benchmark person1-retrieval/benchmarks/synthetic_smoke.json --split dev --output dev-report.json
python -m person1_retrieval.cli evaluate --corpus person2-backend/fixtures/demo --allow-draft --benchmark person1-retrieval/benchmarks/synthetic_smoke.json --split test --output test-report.json
python -m person1_retrieval.cli tune --corpus person2-backend/fixtures/demo --allow-draft --benchmark person1-retrieval/benchmarks/synthetic_smoke.json --scores 0,0.5,1 --margins 0,0.15,0.3 --output grid-demo.json
```

24 case tự tạo (16 DEV/8 TEST) chỉ là smoke/regression, không phải benchmark pháp lý hay TEST_V2 của nhóm.
Grid này kiểm tra công cụ chạy; không dùng kết quả để chốt ngưỡng production.
`benchmarks/README.md` mô tả nhãn và protocol dùng corpus thật. Không đưa TEST_V2/nhãn bí mật vào tool của Person 1.
Latency đo riêng retrieve (có validation và xác minh segmentation), không gồm build, lần segment query đầu hay generation/DB.
Xem `verification/current/` cho kết quả thực chạy; báo cáo ở `verification/` cấp trên là lịch sử được giữ nguyên.
