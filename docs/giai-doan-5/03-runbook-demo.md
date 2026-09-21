# Runbook Docker và demo G5 full corpus

## 1. Phạm vi runtime

Stack `hanh-chinh-g5` chạy độc lập với G3 và dùng:

- corpus đã kiểm duyệt: 34 thủ tục, 34 nguồn, 139 fragment;
- grounded answer: Qwen3-1.7B Q8_0 + LoRA full-corpus r16;
- intent/context: Qwen3-4B Q8_0 + LoRA hard-v2 r16;
- retrieval: Exact/BM25, embedding 0.6B và MCP source registry;
- Backend, PostgreSQL, Web và feedback hai trục.

TEST kín không được mở khi start hoặc smoke runtime.

## 2. Khởi động

Trên máy dự án hiện tại, các đường dẫn mặc định đã trỏ tới artifact private nên chỉ cần:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-g5.ps1 `
  -Action Start `
  -ReviewToken '<token-local-it-nhat-12-ky-tu>'
```

Khi chạy trên máy khác, truyền thêm `DatasetPath`, `GenerationModelPath`,
`GenerationAdapterPath`, `EmbeddingModelPath`, `IntentModelPath` và
`IntentAdapterPath`. Nên truyền đủ năm SHA-256 theo biên bản tích hợp để phát hiện artifact bị đổi.

- Web: `http://localhost:3005`
- Backend: `http://localhost:8005`
- Grounded model: `http://localhost:8085/health`
- Intent model: `http://localhost:8087/health`
- Source MCP: `http://localhost:8096/mcp`

Script chặn corpus không có manifest `READY_FOR_CONTROLLED_RAG`, sai version, sai số thủ tục,
sai hash hoặc model/adapter không phải GGUF.

## 3. Smoke toàn luồng

Chọn một thủ tục và hai field có dữ liệu trong corpus, sau đó chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke-g5-runtime.ps1 `
  -DirectQuestion '<cau-hoi-co-ten-thu-tuc>' `
  -FollowUpQuestion '<cau-hoi-tiep-noi-khong-lap-ten-thu-tuc>'
```

Smoke kiểm tra: đăng nhập, conversation, intent/context, retrieval, generation, verifier,
citation, reset context và vòng đời lưu/đọc/xóa feedback. Báo cáo không in nội dung nguồn hoặc
đáp án TEST.

## 4. Demo thủ công

1. Đăng nhập và hỏi một field của thủ tục đã duyệt.
2. Hỏi tiếp field khác mà không nhắc lại tên thủ tục để chứng minh context.
3. Gửi “Bắt đầu lại” để chứng minh reset.
4. Chỉ ra nguồn, checklist, phiên bản tri thức và tên model dưới câu trả lời.
5. Lưu, sửa và xóa đánh giá phù hợp/hài lòng.

## 5. Kiểm tra và dừng

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-g5.ps1 `
  -Action Status -ReviewToken '<cung-token-khi-start>'

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-g5.ps1 `
  -Action Stop -ReviewToken '<cung-token-khi-start>'
```

`Stop` không xóa volume PostgreSQL hoặc source registry.
