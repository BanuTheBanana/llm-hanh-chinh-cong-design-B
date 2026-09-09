# Chỉ mục Giai đoạn 3

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.2` |
| Trạng thái | `G3_A01_PASS_D0_E2E; G3_A02_WAITING_FOR_D03_R02` |

## Tổng

G3 đưa dữ liệu công ty vào pipeline private, đo RAG thật và thay grounded template
bằng Qwen3-1.7B chạy local. Không fine-tune trước khi data/retrieval/zero-shot
baseline chứng minh model là bottleneck.

## Phân

1. [Audit dataset công ty](01-audit-dataset-cong-ty.md).
2. [Data contract G3 giữa Tú và Minh](02-contract-data-g3.md).
3. [Machine-readable JSON Schema](schema/data-contract-v1.schema.json).
4. [Chiến lược và phân công G3](03-chien-luoc-va-phan-cong-giai-doan-3.md).
5. [Runbook Qwen3-1.7B local](04-runbook-qwen-local.md).
6. [Contract grounded hiện tại](../contracts-g2.md).
7. [Chiến lược trung tâm](../00-chien-luoc-trien-khai-tu-nho-den-lon.md).

## Hợp

Thứ tự làm: governance → preprocess → review → RAG → gold set → Qwen local
zero-shot → error analysis → QLoRA có điều kiện. Raw và derived company data không
được commit lên GitHub.
