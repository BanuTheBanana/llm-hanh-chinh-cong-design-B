# Trợ lý hành chính công – LLM lightweight

Repository của nhóm Tú, Minh và Hoan cho hệ thống hỏi đáp hành chính công.

## Trạng thái hiện tại

Nhóm đang triển khai **Giai đoạn 1 – Technical Vertical Slice**:

```text
React Web → FastAPI Core Backend → FastAPI Mock AI Service
                   ↓
              PostgreSQL
```

Giai đoạn này kiểm tra luồng kỹ thuật, đăng nhập demo, conversation, message, history, user isolation và xử lý lỗi. Chưa triển khai RAG, Qwen, fine-tune, Case, queue hoặc Socket.IO.

## Tài liệu bắt buộc đọc

1. [Chiến lược từ nhỏ đến lớn](00-chien-luoc-trien-khai-tu-nho-den-lon.md)
2. [Phân công Giai đoạn 1](01-phan-cong-giai-doan-1.md)
3. [API contract G1](docs/contracts-g1.md)

## Cấu trúc repository

```text
.
├── web/                 # Tú – React + TypeScript + Vite
├── backend/             # Minh – FastAPI + PostgreSQL
├── ai-service/          # Hoan – FastAPI + MockProvider
├── infra/docker/        # Hạ tầng/container bổ trợ
├── scripts/             # Smoke test và script phát triển
├── docs/                # Contract và tài liệu kỹ thuật đang dùng
├── so-do-kien-truc/     # Sơ đồ tham khảo
├── tai-lieu-tam-hoan/   # Target architecture chưa triển khai
├── compose.yaml         # Sẽ được Hoan bổ sung trong G1
└── .env.example         # Danh sách biến môi trường, không có secret thật
```

## Branch G1

| Thành viên | Branch | Phạm vi chính |
|---|---|---|
| Tú | `g1/frontend-tu` | `web/**` |
| Minh | `g1/backend-minh` | `backend/**` |
| Hoan | `g1/ai-integration-hoan` | `ai-service/**`, Compose, contract và integration |

Không push trực tiếp feature lên `main`. Pull request phải nhỏ, chạy test và không tự thay contract chung.
