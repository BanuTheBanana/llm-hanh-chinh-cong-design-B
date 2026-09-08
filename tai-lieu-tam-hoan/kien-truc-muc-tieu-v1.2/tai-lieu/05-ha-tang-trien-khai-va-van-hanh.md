# Module 05 – Hạ tầng, triển khai và vận hành

> File chi tiết cho deployment: Docker topology, cấu hình, networking, secrets, observability, scale, backup và performance test.  
> File trung tâm: [Workflow tổng quát](../00-workflow-tong-quat.md).  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 07/09/2026 |
| Phiên bản | `v1.1` |
| Trạng thái | Thiết kế Docker Compose MVP; production profile chờ hạ tầng/SLA công ty |
| Thay đổi lần này | Đồng bộ queue/locking cho mô hình một conversation nhiều case và khả năng cùng case được nhắc từ nhiều conversation |
| Contract ảnh hưởng | Deployment profile, queue/lock metrics, environment variables, health checks, telemetry và backup policy |

---

# PHẦN I – TỔNG: MỤC TIÊU TRIỂN KHAI

## 1. Mục tiêu

Hạ tầng phải giúp hệ thống:

- chạy được end-to-end bằng một quy trình thống nhất;
- tách service public khỏi data/model private;
- phục vụ nhiều conversation mà vẫn giữ thứ tự từng conversation;
- quan sát được latency/lỗi theo từng stage;
- thay model/index/procedure version có kiểm soát;
- backup, rollback và khôi phục được;
- không lộ secret hoặc PII.

## 2. Ba deployment profile

| Profile | Mục đích | Đặc điểm |
|---|---|---|
| `local-dev` | Lập trình từng máy | Docker Compose, mock OTP, llama.cpp hoặc model server local |
| `demo-gpu` | Báo cáo/pilot trên RTX 5060 Ti 16GB | Full pipeline, một GPU, telemetry và sample data |
| `production-like` | Load/security test | HTTPS, vLLM/WSL2/Linux, multi-worker, secret/backup/monitoring |

Cùng API contract và migration; khác cấu hình scale, secret và runtime model.

## 3. Topology tổng quát

```text
Browser
  ↓ HTTPS
Gateway/Reverse proxy
  ├─ Web static/SPA
  ├─ FastAPI REST
  └─ Socket.IO

Private network
  ├─ Conversation workers
  ├─ Ingestion/Summary workers
  ├─ Model server
  ├─ PostgreSQL
  ├─ Redis
  ├─ Qdrant
  └─ MinIO/S3
```

Production chỉ expose gateway. Database, Redis, Qdrant, object store và model server không public.

---

# PHẦN II – PHÂN: SERVICE VÀ VẬN HÀNH

## 4. Docker Compose topology MVP

| Service | Vai trò | Development port |
|---|---|---:|
| `web` | HTML/CSS/JS hoặc SPA | 3000 |
| `gateway` | Nginx/reverse proxy/TLS termination | 8080 |
| `api` | FastAPI REST/BFF | 8000 nội bộ qua gateway |
| `realtime` | Socket.IO ASGI | 8002 nội bộ |
| `worker` | Conversation jobs | Không public |
| `summary-worker` | Summary/memory jobs | Không public |
| `ingestion-worker` | Scan/parse/chunk/embed/index | Không public |
| `llm-server` | vLLM hoặc llama.cpp OpenAI-compatible | 8001 nội bộ |
| `postgres` | App state, Procedure metadata, audit | 5432 nội bộ |
| `redis` | Streams, cache, locks, Socket adapter | 6379 nội bộ |
| `qdrant` | Dense/sparse index | 6333 nội bộ |
| `minio` | Raw/upload object storage | 9000 nội bộ; console dev 9001 |

MVP có thể gộp `api/realtime` hoặc `worker/summary-worker` trong cùng image nhưng phải giữ process/queue riêng để sau này scale độc lập.

## 5. Network và access

Đề xuất hai network logic:

```text
edge: gateway ↔ web/api/realtime
private: api/workers ↔ postgres/redis/qdrant/minio/model
```

Quy tắc:

- không publish data-service port ở production;
- firewall/allowlist chỉ cho service cần thiết;
- admin endpoints tách role và có audit;
- CORS chỉ cho origin cấu hình;
- upload/download dùng authenticated route hoặc signed URL ngắn hạn;
- health endpoint public không lộ version/secret nhạy cảm.

## 6. Environment variables

File mẫu: [`.env.example`](../.env.example).

Nhóm biến:

```text
Application/gateway
Session/authentication/PII
PostgreSQL
Redis queue/cache/lock
Socket.IO
Qdrant/index version
Object storage/upload policy
LLM runtime/model limits
Retriever/reranker
Context/memory
Ingestion/safety
Observability
```

Quy tắc:

1. Commit `.env.example`, không commit `.env` thật.
2. Example không chứa secret dùng được.
3. Validate config khi startup và fail fast.
4. Development có thể dùng `.env`; production dùng secret manager/Docker secrets.
5. Ghi rõ precedence và một command chuẩn để mọi máy nhận cùng config.
6. Không log toàn bộ environment.

## 7. Secret và PII

- Session signing, phone lookup HMAC và PII encryption dùng key riêng.
- Rotate key có version; giữ kế hoạch decrypt/re-encrypt.
- Log redaction ở gateway, API, worker và model gateway.
- Không gửi PII không cần thiết vào retrieval/model.
- Backup được mã hóa, có retention và quyền restore giới hạn.
- Development seed không dùng dữ liệu công dân thật.

## 8. Health, readiness và startup order

Mỗi service có:

```text
/health/live  → process còn sống
/health/ready → dependency và migration/model/index sẵn sàng
```

Readiness ví dụ:

- API: DB/Redis reachable, schema version phù hợp.
- Worker: Redis group và DB reachable.
- RAG: active index/procedure version tồn tại.
- Model: model load xong và structured-output smoke test pass.
- Gateway: upstream ready.

Không chỉ dùng `depends_on`; service phải retry dependency có backoff và giới hạn.

## 9. Model serving

### vLLM profile

- chạy Linux/WSL2 khi cần concurrency;
- continuous batching, prefix caching, structured output;
- giới hạn max model length, GPU memory utilization và concurrent requests;
- một ModelGateway che giấu runtime chi tiết khỏi backend.

### llama.cpp profile

- native Windows/CUDA cho GGUF local;
- benchmark Q5/Q4 và demo đơn giản;
- cùng endpoint contract với vLLM.

Không load nhiều generator cùng GPU 16GB trong production mặc định. Reranker/embedding có thể tách lịch xử lý hoặc device sau benchmark VRAM.

## 10. Queue và worker capacity

Queue tuần tự theo conversation, không tuần tự toàn hệ thống:

```text
N conversation workers
→ mỗi worker lock đúng conversation
→ case mutation dùng optimistic `case_version` hoặc lock ngắn theo case
→ gọi chung một model server
→ model server batch request từ các conversation
```

Theo dõi:

```text
queue depth
oldest job age
queue wait P50/P95
jobs processing/retry/DLQ
lock wait/contention
case-version conflicts
per-user queued messages
model concurrency/VRAM
```

Áp dụng backpressure/rate limit trước khi queue tăng vô hạn.

## 11. Cache

| Cache | Invalidation |
|---|---|
| Procedure record | procedure version publish |
| Retrieval result | index version đổi |
| Public embedding | embedding model/version đổi |
| Checklist | procedure version hoặc relevant facts đổi |
| Prefix/KV | model/prompt/schema/trust boundary đổi |
| Public FAQ answer | procedure version đổi/TTL |

Không semantic-cache final answer cá nhân giữa users. Cache key chứa version và namespace phù hợp.

## 12. Observability

### 12.1. Correlation

Mọi log/span/event có:

```text
trace_id
message_id
conversation_id (pseudonymized nếu cần)
job_id
model_version
prompt/schema_version
procedure_version_id
index_version
```

### 12.2. Metrics

Backend:

```text
HTTP rate/error/latency
DB pool/slow query/transaction failures
queue lag/retry/DLQ/lock wait
Socket connections/reconnect/replay
```

AI/RAG:

```text
route distribution
model_calls_per_turn
input/output tokens
retrieval/rerank latency
TTFT/TPOT/total model latency
VRAM/RAM/OOM
verifier pass/rewrite/fail
answer status distribution
```

Data:

```text
active index/procedure version
source health
ingestion failures
staging/active document counts
cache hit/stale invalidation
```

### 12.3. Logging

Structured JSON logs; không log raw message/evidence mặc định. Dùng error codes, duration và IDs; sampling cho debug phải theo consent/policy.

## 13. Alerting ban đầu

- API/model error hoặc timeout tăng.
- Queue oldest-age vượt ngưỡng.
- DLQ có job mới.
- DB disk/pool/saturation.
- GPU OOM hoặc VRAM gần ngưỡng lâu.
- Không có active index/procedure version.
- Ingestion regression fail sau publish.
- Verifier fail/abstain/critical error bất thường.
- Source health/URL chính thức hỏng hàng loạt.

Ngưỡng số chốt sau khi có baseline và SLA.

## 14. Backup và disaster recovery

### PostgreSQL

- backup định kỳ + point-in-time nếu production yêu cầu;
- kiểm restore bằng drill, không chỉ kiểm file tồn tại;
- migration có forward/rollback plan.

### MinIO/S3

- versioning/retention cho raw snapshot;
- checksum và lifecycle policy;
- không xóa source đang được audit tham chiếu.

### Qdrant

- index có thể rebuild từ canonical store/object snapshot;
- snapshot để phục hồi nhanh nhưng không là nguồn duy nhất.

### Redis

- không là source of truth dài hạn;
- outbox/DB cho phép republish job/event cần thiết.

## 15. Release và rollback

Artifact/version cần khóa cùng nhau:

```text
application commit/image tag
database schema version
model artifact + quantization
prompt/schema version
procedure version set
index version
environment/deployment profile
```

Rollout:

```text
deploy inactive/new version
→ health + smoke tests
→ activate pointer/config
→ monitor
→ rollback pointer/image nếu gate fail
```

Không ghi đè model/index/procedure artifact đang dùng.

## 16. CI/CD tối thiểu

```text
lint/type/unit
→ schema/contract tests
→ migrations on disposable DB
→ integration: DB + Redis + mock model
→ RAG/model smoke tests
→ image scan + secret scan
→ build immutable images
→ deploy staging/demo
→ private regression gate
→ manual approval production/pilot
```

Large model benchmark có thể chạy theo lịch/manual thay vì mọi commit, nhưng schema/smoke test phải chạy thường xuyên.

## 17. Performance benchmark

Ma trận:

```text
context: 2K / 4K / 8K
concurrency: 1 / 2 / 4 / 8
precision/runtime: BF16/AWQ hoặc GGUF Q5/Q4
route: fast / standard / complex
cache: cold / warm
```

Đo:

```text
end-to-end P50/P95/P99
TTFT/TPOT
throughput requests/s
queue wait
retrieval/rerank/model stage latency
peak VRAM/RAM
timeout/error/OOM
quality metrics cùng lúc
```

Không chốt SLA bằng cảm giác trước benchmark phần cứng thật.

---

# PHẦN III – HỢP: KẾ HOẠCH TRIỂN KHAI

## 18. Thứ tự triển khai

### I0 – Local skeleton

- Compose cho PostgreSQL, Redis, API, worker và web.
- `.env.example`, health/readiness và migration.
- Mock model/RAG.

### I1 – Data và realtime

- Qdrant/MinIO/ingestion worker.
- Socket.IO, outbox publisher và reconnect sync.

### I2 – GPU integration

- ModelGateway + llama.cpp local.
- vLLM/WSL2 profile và GPU telemetry.

### I3 – Reliability

- DLQ/backpressure/rate limit.
- Backup/restore, rollback model/index và failure drills.

### I4 – Production-like

- HTTPS, secret manager, least privilege.
- Observability/alerts, load/security tests.

## 19. Deployment checklist

### Trước deploy

- image/model/index checksums đúng;
- migration và backup hoàn tất;
- secret/config validation pass;
- active procedure/index tồn tại;
- private regression đạt gate;
- rollback target đã xác định.

### Sau deploy

- health/readiness pass;
- gửi synthetic message end-to-end;
- kiểm citation/evidence UI;
- theo dõi P95, queue lag, OOM, verifier status;
- xác nhận không lộ port/data/secret.

## 20. Quality gate hạ tầng

- Compose dựng được từ máy sạch bằng hướng dẫn duy nhất.
- Không có secret thật trong Git/image/log.
- Chỉ gateway public ở production profile.
- Service restart không mất message đã commit.
- Redis/Qdrant có thể mất và rebuild/replay theo thiết kế.
- Model/index/procedure rollback được.
- Có benchmark cold/warm và concurrency.
- Observability truy được một message xuyên mọi stage.
- Backup restore drill thành công theo RPO/RTO công ty chốt.

## 21. Definition of Done module

- Có Compose profiles và `.env.example` được validate.
- Health/readiness/dependency retry hoạt động.
- Metrics/log/trace dashboard tối thiểu.
- Queue backpressure, retry và DLQ có cảnh báo.
- GPU runtime benchmark trên RTX 5060 Ti 16GB.
- Backup, restore và rollback có runbook đã thử.
- Security/network/secret checks vượt gate.
