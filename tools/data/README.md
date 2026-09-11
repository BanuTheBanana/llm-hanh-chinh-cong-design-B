# Công cụ dữ liệu G2

- `validate_dataset.py --mode preflight`: kiểm tra kỹ thuật draft; cảnh báo các
  gate review/phạm vi còn thiếu nhưng vẫn trả exit code 0 nếu cấu trúc nhất quán.
- `validate_dataset.py --mode publish`: cùng các kiểm tra trên nhưng biến review,
  độ đầy đủ và phạm vi 2–3 thủ tục/30–50 câu thành lỗi chặn publish.
- `build_synthetic_dataset.py`: tạo lại deterministic corpus D0 gồm 3 thủ tục,
  24 fragment và 33 câu hỏi; không truy cập Internet.
- `crawl_or_download.py`: chỉ tải một URL HTTPS thuộc allowlist, tôn trọng
  `robots.txt`, giới hạn dung lượng và không ghi đè snapshot cũ.
- `g3_pipeline`: parser, validator và gold-draft builder cho workbook công ty G3.
  Công cụ chỉ chạy local, output luôn nằm ở vùng `data/company_private/` bị ignore.
  Xem [hướng dẫn phần Tú](../../docs/giai-doan-3/04-huong-dan-pipeline-data-tu.md).

Generator và validator không tự chuyển `review_status` sang `APPROVED`. Chỉ lệnh
khóa có xác nhận rõ của leader/reviewer mới ghi duyệt và khóa hash TEST_V2.

## Bộ đánh giá G4 của Tú

Các lệnh dưới đây chỉ chạy local trên corpus `demo10`; DEV/TEST_V2 và gold không
được commit. Generator giữ 8 thủ tục cho DEV và 2 thủ tục khác cho TEST_V2.

```powershell
$dataset = "data/company_private/company-tthc-9c38dde8-v1-demo10-v1"
$scenarioSchema = "docs/giai-doan-4/schema/g4-evaluation-scenario-v1.schema.json"
$manifestSchema = "docs/giai-doan-4/schema/g4-evaluation-manifest-v1.schema.json"

uv run --project tools/data hcc-g4-coverage `
  --procedures "$dataset/normalized/procedures.jsonl"

uv run --project tools/data hcc-build-g4-evaluation `
  --procedures "$dataset/normalized/procedures.jsonl" `
  --output-dir "$dataset/g4_eval"

uv run --project tools/data hcc-validate-g4-evaluation `
  --dataset $dataset `
  --scenario-schema $scenarioSchema `
  --manifest-schema $manifestSchema `
  --mode preflight
```

Multi-turn luôn có dạng `user → assistant → user`; `question` là lượt user cuối
cần hệ thống trả lời. `expected_points` được lấy theo từng giá trị nguồn, không
dùng một từ khóa chung cho cả field. Các field phí/thời gian parse chưa chắc được
gắn cờ và khi duyệt chỉ được chấm theo `raw_text`.

Chỉ leader/reviewer cuối chạy lệnh khóa sau khi xem nhãn. Lệnh yêu cầu xác nhận
rõ, ghi reviewer/thời điểm, cập nhật hash rồi chạy lại publish validator:

```powershell
uv run --project tools/data hcc-lock-g4-evaluation `
  --dataset $dataset `
  --scenario-schema $scenarioSchema `
  --manifest-schema $manifestSchema `
  --reviewer-role PROJECT_LEADER_DELEGATED_REVIEW `
  --reviewed-at "2026-09-11T12:00:00+07:00" `
  --acknowledge-test-lock
```

Sau khi `LOCKED`, không dùng kết quả TEST_V2 để chỉnh prompt, retrieval hoặc
model. Minh chỉ nhận DEV, schema và tool; TEST_V2/gold do Hoan giữ.

Khi kiểm tra dữ liệu D0, phải truyền rõ:

```text
--dataset data/demo_synthetic --classification D0_SYSTEM_SMOKE
```

## Hidden TEST_V3

TEST_V3 không được sinh hoặc lưu trong Git. Leader/reviewer dùng
`g3_pipeline.g4_release_test` để chuẩn hóa nhãn theo corpus đã duyệt, kiểm tra schema,
PII, source binding, trùng DEV/TEST_V2 và khóa SHA-256. Công cụ chỉ in thống kê và mã
lỗi; không in câu hỏi, đáp án hoặc evidence riêng tư.

Hai lệnh `prepare-lock` và `validate` bắt buộc nhận đường dẫn private tới corpus,
TEST_V3, DEV, TEST_V2 cùng hai schema trong `docs/giai-doan-4/schema/`. Sau khi khóa,
không dùng TEST_V3 để sửa retrieval, prompt hoặc model.
