# Contract G2 – Grounded generation

> Contract version: `g2-grounded-v0.2`
> Prompt version: `g2-grounded-v2`
> Trạng thái: **đã tích hợp D0 trên `g2/integration`; chờ team sign-off và D1**.
> G1 `/internal/v1/generate` được giữ nguyên.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Owner ghi contract | Hoan |
| Consumer hiện tại | Core Backend/RAG, đã chạy end-to-end với fixture D0 |
| Provider hiện được bật | `template`, offline, không gọi mạng |
| Hosted provider | Chưa chọn/chưa bật; chờ phê duyệt |
| Dữ liệu API nhận | `D0_SYSTEM_SMOKE` hoặc `D1_PUBLIC_DEMO`; từ chối D2 |
| Template hiện tại | Chỉ cho phép D0; D1 chờ provider được duyệt |

---

# PHẦN I – TỔNG

## 1. Vì sao cần API v2?

API G1 chỉ nhận lịch sử message và trả một chuỗi `text`. G2 cần evidence, trạng
thái abstain và citation ID; đây là thay đổi không tương thích. Vì vậy:

```text
POST /internal/v1/generate  # giữ nguyên cho G1
POST /internal/v2/generate  # grounded generation của G2
```

Khi `RAG_ENABLED=false`, Backend tiếp tục gọi v1 để giữ regression G1. Khi bật
RAG, Backend tạo evidence rồi gọi v2; hai luồng đã được kiểm thử song song. Team
vẫn phải sign-off contract trước khi đóng băng thành `v1.0` và trước khi dùng D1.

## 2. Hai kiểu bundle không được nhầm

```text
Canonical EvidenceBundle trong Backend
  có retrieval score + URL + metadata phục vụ audit/UI
                    │ project/allowlist
                    ▼
GroundingContext gửi AI Service
  chỉ có query + ID + text + metadata phạm vi/hiệu lực cần thiết
```

AI Service không cần URL, retrieval score, arbitrary metadata, cookie, user ID hoặc
100 message history. Sau khi AI trả `cited_fragment_ids`, Backend dùng bundle gốc
để hydrate title/URL; không tin model tạo nguồn.

---

# PHẦN II – PHÂN

## 3. Health G2

```http
GET /internal/v2/health
```

Response offline hiện tại:

```json
{
  "status": "ok",
  "service": "ai-service",
  "endpoint": "grounded-v2",
  "provider": "template",
  "prompt_version": "g2-grounded-v2",
  "external_calls_enabled": false
}
```

`GET /health` cũ chỉ phản ánh provider v1 để không phá G1. Readiness của v2 phải
dùng endpoint v2 ở trên.

## 4. Generate G2

```http
POST /internal/v2/generate
Content-Type: application/json
```

### 4.1. Request mẫu

```json
{
  "request_id": "00000000-0000-4000-8000-000000000001",
  "evidence_bundle_id": "10000000-0000-4000-8000-000000000001",
  "corpus_version": "synthetic-demo-v1",
  "data_classification": "D0_SYSTEM_SMOKE",
  "query": "Lệ phí của Đăng ký khai sinh Sao Mai là bao nhiêu?",
  "evidence": [
    {
      "fragment_id": "frag_birth_star_fees",
      "source_id": "src_synthetic_birth_star",
      "procedure_id": "synthetic_birth_star",
      "section_type": "FEES",
      "title": "[D0 GIẢ LẬP] Đăng ký khai sinh Sao Mai",
      "text": "D0 giả lập – Lệ phí khai sinh Sao Mai là 5 đơn vị thử nghiệm; đây không phải mức phí thật.",
      "jurisdiction": "DEMO_CITY",
      "effective_from": null,
      "effective_to": null,
      "validity_status": "UNKNOWN"
    }
  ],
  "as_of": "2026-09-08",
  "max_output_tokens": 500
}
```

### 4.2. Giới hạn request

| Field | Quy tắc |
|---|---|
| `request_id` | UUID trace toàn request |
| `evidence_bundle_id` | UUID bind đúng retrieval result với answer |
| `corpus_version` | ID 1–128 ký tự theo pattern an toàn |
| `data_classification` | Chỉ `D0_SYSTEM_SMOKE` hoặc `D1_PUBLIC_DEMO` |
| `query` | Không rỗng, tối đa 4.000 ký tự |
| `evidence` | Tối đa 8 fragment, `fragment_id` duy nhất |
| Tổng `evidence.text` | Tối đa 32.000 ký tự |
| Một `text` | Tối đa 8.000 ký tự |
| `max_output_tokens` | 32–2.048, integer strict |

`D2_COMPANY_REAL` bị schema từ chối. Nhãn dữ liệu là defense-in-depth chứ không
thay thế kiểm tra PII/DLP. Vì query Web vẫn có thể chứa dữ liệu cá nhân, hosted
interactive tiếp tục bị tắt cho tới khi có policy và gate riêng.

`validity_status` nhận `CURRENT`, `EXPIRED`, `FUTURE`, `UNKNOWN`. Không tự biến
`UNKNOWN` thành `CURRENT`. `effective_to` không được trước `effective_from`.

### 4.3. Response mẫu

```json
{
  "request_id": "00000000-0000-4000-8000-000000000001",
  "evidence_bundle_id": "10000000-0000-4000-8000-000000000001",
  "corpus_version": "synthetic-demo-v1",
  "data_classification": "D0_SYSTEM_SMOKE",
  "prompt_version": "g2-grounded-v2",
  "answer": "...",
  "status": "ANSWER",
  "cited_fragment_ids": ["frag_birth_star_fees"],
  "missing_information": [],
  "provider": "template",
  "model": "template-grounded-v2",
  "usage": {"input_tokens": 0, "output_tokens": 0},
  "latency_ms": 0
}
```

Model/provider tương lai chỉ được sinh bốn field nghiệp vụ:

```text
answer
status
cited_fragment_ids
missing_information
```

Các ID binding, version, provider, model, usage, latency và prompt version do AI
Service gắn; không lấy từ output model.

## 5. Invariant bắt buộc

- `ANSWER` phải có ít nhất một citation và `missing_information=[]`.
- `NEED_CLARIFICATION` chỉ dùng khi evidence cho thấy câu trả lời phụ thuộc vào dữ
  kiện cụ thể người dùng có thể bổ sung; phải có `missing_information`.
- `INSUFFICIENT_DATA` dùng khi evidence rỗng, không liên quan, hết/chưa hiệu lực,
  mâu thuẫn hoặc hỏi thêm người dùng vẫn không tạo đủ căn cứ; không có citation.
- Mọi list phải duy nhất, không chứa chuỗi rỗng/whitespace.
- `cited_fragment_ids` phải là tập con chính xác của evidence trong request.
- Evidence rỗng luôn short-circuit thành `INSUFFICIENT_DATA`; không gọi provider.
- Output fenced Markdown, extra field, malformed JSON hoặc citation giả bị từ chối.
- Citation ID hợp lệ chưa chứng minh claim được source hỗ trợ; bước đó vẫn cần gold
  evaluation và human review.

## 6. Error

Giữ error envelope của G1:

```json
{
  "error": {
    "code": "AI_PROVIDER_INVALID_RESPONSE",
    "message": "AI provider returned an invalid response.",
    "request_id": "uuid"
  }
}
```

| HTTP | Trường hợp |
|---:|---|
| 422 | Request/schema/data classification không hợp lệ |
| 502 | Provider output sai schema/invariant/citation allowlist |
| 503 | Provider chưa hỗ trợ hoặc tạm lỗi |
| 504 | Provider timeout |

`AI_PROVIDER_DATA_NOT_ALLOWED` trả 503 khi provider hiện tại không được allowlist
cho classification của request. Template mặc định chỉ allow D0.

Log không ghi query, evidence text, token/key hoặc raw provider error. Chỉ ghi
request/bundle/corpus/classification, số fragment, provider/model và latency.

## 7. Hosted-provider gate

Hiện chỉ `GROUNDED_PROVIDER=template`. Trước khi thêm provider bên ngoài phải có:

1. mentor/công ty chấp thuận provider và loại dữ liệu;
2. model allowlist không có built-in web/tool tự bật;
3. base URL pinned/allowlisted, không nhận URL tùy ý cùng secret;
4. API key chỉ nằm trong `.env` local/secret store;
5. timeout/retry nhỏ hơn deadline Backend; retry chỉ trường hợp đã thống nhất;
6. test bằng fake transport; live test manual/opt-in, không chạy PR CI;
7. D1 đã kiểm tra PII; không gửi raw corpus hoặc history dài.
8. Mỗi adapter khai báo explicit classification allowlist và cờ external-call;
   service kiểm tra trước khi gọi, không dựa vào nhãn do adapter tự suy luận.
9. `provider`/`model` trong response là metadata do service sở hữu và kiểm tra ký
   tự an toàn; không lấy từ raw response để tránh giả log/metadata.

Không dùng API key đã từng dán vào chat, issue tracker, commit hoặc log.

---

# PHẦN III – HỢP

## 8. Trách nhiệm Backend khi tích hợp

```text
retrieve approved/versioned evidence
→ giữ canonical bundle có URL/score ở Backend
→ project sang GroundingContext tối thiểu
→ gọi /internal/v2/generate
→ so request_id + evidence_bundle_id + corpus_version
→ validate citation IDs lần nữa
→ hydrate URL/title từ DB
→ lưu answer + grounding metadata
```

Browser không được tự gửi evidence hoặc source URL tới AI Service.

## 9. Trạng thái triển khai

| Hạng mục | Trạng thái |
|---|---|
| API v1 G1 | Giữ nguyên, regression test pass |
| Schema/route v2 | Đã implement và ghép trên `g2/integration` |
| No-evidence/citation guard | Đã implement |
| Template offline | Đã implement |
| Evaluation fixture/harness | Đã implement |
| Backend/RAG integration | Đã chạy D0 qua Compose/API/Web |
| Team sign-off contract | Chưa ghi nhận; cần Tú và Minh xác nhận |
| D1 public corpus | Spike kỹ thuật có 1 thủ tục; review/publish gate chưa đạt |
| Hosted adapter/live API | Chưa thực hiện; chờ approval và D1 |

Contract này trở thành `v1.0 FROZEN` chỉ sau khi Tú và Minh formal sign-off trên
projection/consumer đã tích hợp, đồng thời fixture contract test vẫn pass. Trước
đó, mọi thay đổi phải cập nhật version và test fixture cùng lúc.
