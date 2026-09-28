# Biên bản tích hợp runtime full corpus

Ngày: **14/09/2026**
Trạng thái: **PASS smoke end-to-end, chưa mở TEST kín**.

## Thay đổi chính

- Xuất adapter `qwen3-1.7b-full-corpus-r16-seed42` sang GGUF F16.
- Gắn adapter vào generation server; alias runtime là `Qwen3-1.7B-FullCorpus-r16`.
- Chuyển runtime G5 từ demo10 sang release đã kiểm duyệt gồm 34 thủ tục, 34 nguồn và
  139 fragment.
- Khóa corpus bằng version, 34 row nguồn và fingerprint
  `b4a7b8fc7260930f9e80ddcf05733705c936d88f5fd4d91c1e0e4908cf242c34`.
- Giữ intent/context trên adapter riêng vì adapter full-corpus sinh grounded answer không có cùng
  output contract với intent/context.
- Đồng bộ verifier với đúng format câu trả lời đã dùng khi SFT. Nội dung claim vẫn phải nguyên văn,
  citation vẫn phải khớp fragment và sai contract vẫn retry/fallback an toàn.
- Thêm smoke tái lập cho đăng nhập, hội thoại trực tiếp, follow-up, reset và feedback.

## Bằng chứng chạy thật

- Tám service Docker đều healthy.
- `/health/rag` xác nhận đúng corpus full, 34 nguồn, 34 thủ tục, 139 fragment, local-only và
  intent/context đang bật.
- Container generation mount read-only đúng base GGUF và adapter GGUF.
- Một lượt trực tiếp đạt `candidate_passed=true`, `fallback_used=false`, 1 nguồn và 1.127 ms.
- Smoke toàn luồng cuối đạt PASS: lượt trực tiếp 1.102 ms, follow-up 779 ms, reset 32 ms;
  feedback lưu được một bản ghi và sau khi xóa còn 0.

## Giới hạn còn lại

- Runtime hiện dùng ba model service để đo tích hợp; đây chưa phải cấu hình tài nguyên cuối.
- Intent/context vẫn dùng 4B. Muốn giảm tải phải huấn luyện và đánh giá một adapter intent/context
  nhỏ hơn trên đúng dataset của tác vụ này, không tái sử dụng nhầm adapter grounded answer.
- Chưa chạy TEST kín và không dùng TEST để sửa model.
