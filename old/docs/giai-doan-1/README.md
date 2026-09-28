# Giai đoạn 1 – Technical Vertical Slice

> Trạng thái: `COMPLETED_ON_MAIN`<br>
> Tag đóng băng: `g1-v1.0.0`<br>
> Merge commit: `17139b4`<br>
> Pull request: [#2](https://github.com/DOMEMON/llm-hanh-chinh-cong/pull/2)<br>
> Runtime CI: [run 34197723998](https://github.com/DOMEMON/llm-hanh-chinh-cong/actions/runs/34197723998)

Đây là chỉ mục lưu dấu G1. Source không được sao chép vào folder này vì G2 sẽ
nâng cấp trực tiếp cùng các module `web/`, `backend/` và `ai-service/`. Tag Git
`g1-v1.0.0` là snapshot bất biến để checkout hoặc đối chiếu lại toàn bộ code G1.

## Tài liệu G1

- [Phân công và nghiệm thu](../01-phan-cong-giai-doan-1.md)
- [API Contract G1 v1.2](../contracts-g1.md)
- [Báo cáo test Backend](../../backend/docs/TEST_REPORT.md)
- [Runbook Docker](../../infra/docker/README.md)

## Kết quả đã xác minh

- Web: 9 test, production build và Playwright browser smoke;
- AI Service: 15 test;
- Backend: 58 test trên PostgreSQL 16;
- full Compose, API smoke, history, idempotency, logout và user isolation;
- chỉ dùng Mock AI và dữ liệu giả `D0_SYSTEM_SMOKE`.

G1 không bao gồm RAG, dữ liệu thủ tục, hosted model, Qwen, fine-tune, Case,
memory dài hạn, queue hoặc Socket.IO.
