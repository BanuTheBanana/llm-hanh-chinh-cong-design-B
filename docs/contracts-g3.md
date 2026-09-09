# Contract G3 – D2 private RAG và Qwen local

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Phiên bản | `g3-d2-v1` |
| Cập nhật | 10/09/2026 |
| Trạng thái | `IMPLEMENTED_AND_E2E_TESTED` |
| Kế thừa | Grounded API v2 trong `contracts-g2.md` |

## Tổng

G3 không đưa workbook hay normalized record qua HTTP. Backend đọc corpus private
đã duyệt từ volume read-only, truy hồi fragment rồi gửi projection tối thiểu tới
AI Service chạy local.

```text
Private corpus → Backend retrieval → GroundingContext D2 → local AI only
                                         ↓
Web ← Grounding + public-safe citation ← verifier
```

## Phân

### Data classification

Grounded request/response bổ sung giá trị:

```json
"data_classification": "D2_COMPANY_REAL"
```

`template` không nhận D2. `local` chỉ nhận khi cấu hình
`LOCAL_LLM_ALLOW_D2_COMPANY_DATA=true`; capability được công bố ở
`GET /internal/v2/health`:

```json
{
  "provider": "local",
  "external_calls_enabled": false,
  "allowed_data_classifications": ["D0_SYSTEM_SMOKE", "D2_COMPANY_REAL"]
}
```

Backend fail-closed nếu D2 được bật mà một trong hai điều kiện sau sai:

- `external_calls_enabled` khác `false`;
- `allowed_data_classifications` không có `D2_COMPANY_REAL`.

### Citation projection

`Citation.url` là `string | null`. Khi source chỉ có internal URI, Backend trả
`url=null`; Web hiển thị title dạng text và không tạo link. Các trường sau không
được xuất hiện trong AI/Web payload:

- `source_uri`;
- `raw_locator` / `source_locator`;
- workbook/cell hash;
- email hoặc metadata nhân sự;
- cookie, user ID hoặc toàn bộ conversation history.

### Corpus activation

Khi `G3_D2_ENABLED=true`, Backend yêu cầu đồng thời:

- `RAG_ENABLED=true`;
- private dataset path;
- dataset version;
- expected row count;
- corpus SHA-256.

Sai version/schema/reference/review/hash làm readiness và request fail-closed.
Release demo bị cấm trong `production` trừ khi có cấu hình production riêng được
phê duyệt.

Gold/TEST và conflict report chỉ được loader đánh giá đọc. Sau khi validate release,
loader phục vụ chat chỉ giữ source, procedure và fragment; TEST không nằm trong
retrieval index hoặc runtime memory của Backend.

### Output verification

AI chỉ trả answer/status/cited fragment IDs/missing information. AI Service kiểm
JSON schema, status invariant, citation allowlist và thinking leakage. Nếu output
sai contract, local provider retry đúng một lần; lần hai vẫn sai thì trả lỗi, không
lưu assistant answer giả. Backend bind lại request/bundle/version/classification
và hydrate citation từ evidence do chính Backend giữ.

## Hợp

Contract này đủ cho foundation G3 demo nội bộ. Nó không mở hosted provider, không
biến chat thành train data và không chứng nhận nội dung nguồn là đúng pháp lý.
