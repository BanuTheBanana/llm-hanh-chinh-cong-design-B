# G5 Source Service

Registry MCP nội bộ cho các bản cập nhật nguồn đã review. Service có đúng hai tool:
`get_procedure_update` và `manage_source_update`. Mọi thao tác ghi, kể cả `STAGE`, đều
cần `G5_REVIEW_TOKEN`; Backend chỉ đọc snapshot ở trạng thái `PUBLISHED` và tự quay về
corpus gốc nếu transport, schema, hash, hiệu lực hoặc binding không hợp lệ.

Vòng đời hợp lệ:

```text
STAGE → PENDING_REVIEW → APPROVE → PUBLISH
                   └──→ REJECT
PUBLISHED/SUPERSEDED → ROLLBACK
```

Registry chỉ là thành phần limited release localhost, chưa thay thế RBAC, audit database,
backup và nguồn hành chính chính thức. Cách chạy đầy đủ nằm tại
[`docs/giai-doan-5/03-runbook-demo.md`](../docs/giai-doan-5/03-runbook-demo.md).
