# Bàn giao G4-01 sau khi hoàn thiện phần Tú

Tài liệu này chỉ ghi số liệu và thay đổi kỹ thuật; không chứa nội dung dữ liệu
công ty hoặc đáp án TEST_V2.

## Kết quả cuối

- Bundle `G4-01-evaluation-v4`: 80 DEV, 40 TEST_V2 và 36 multi-turn.
- Split theo 8/2 thủ tục; không trùng procedure, procedure-field hoặc group giữa
  DEV và TEST_V2.
- Sáu field nguồn mơ hồ đã được reviewer xử lý theo chính sách bảo thủ.
- Schema, validator, test, hướng dẫn tái tạo và publish gate đều đã bổ sung.
- Publish validation đạt `PASS`; manifest và TEST_V2 đã `LOCKED` bởi Hoan theo
  quyền review được ủy nhiệm.

## Những gì giữ lại từ bản Tú push

- Công cụ coverage và ý tưởng generator deterministic.
- Quy mô 80 DEV/40 TEST_V2, danh sách 8/2 thủ tục và manifest hash.
- Các kiểm tra nền về ID, reference, section, PII và split procedure.
- Dữ liệu G3 nền không đổi.

## Những gì đã sửa hoặc bổ sung

1. Sửa multi-turn từ chuỗi kết thúc bằng assistant thành
   `user → assistant → user`; lượt user cuối là target cần chấm.
2. Thay keyword gold chung bằng `expected_points` lấy đúng giá trị của từng
   field/source; fragment gold phải khớp toàn bộ `field_evidence` tương ứng.
3. Với nguồn chỉ ghi `0.0` hoặc `05`, chuyển expected status sang
   `INSUFFICIENT_DATA`. Giá trị mơ hồ khác chỉ được duyệt theo `raw_text`.
4. Thêm schema riêng cho scenario và manifest G4.
5. Tách validator thành tool riêng với hai chế độ `preflight` và `publish`.
6. Thêm kiểm tra schema, UTF-8/NFC, PII, reference, field, hash, split, hội thoại,
   nhãn và metadata reviewer.
7. Thêm lệnh review/lock có acknowledgement, reviewer, timestamp và rollback nếu
   publish validation thất bại.
8. Thêm năm test không dùng dữ liệu công ty và cập nhật README/CLI.

## File code liên quan

- `tools/data/g3_pipeline/coverage_tu_g4.py`
- `tools/data/g3_pipeline/g4_tu_scenarios.py`
- `tools/data/g3_pipeline/g4_tu_validator.py`
- `tools/data/g3_pipeline/g4_tu_review.py`
- `tools/data/tests/test_g4_tu_evaluation.py`
- `docs/giai-doan-4/schema/g4-evaluation-scenario-v1.schema.json`
- `docs/giai-doan-4/schema/g4-evaluation-manifest-v1.schema.json`

## Quy tắc bàn giao

- Tú và Minh có thể dùng DEV/schema/tool để tiếp tục phát triển.
- TEST_V2/gold do Hoan giữ và không được đưa vào prompt, tuning hoặc serving
  index.
- Nếu thay đổi scenario sau khi khóa, phải tăng `scenario_set`, review và tạo
  hash mới; không sửa trực tiếp bundle v4.
