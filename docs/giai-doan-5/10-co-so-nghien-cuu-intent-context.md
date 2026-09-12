# Cơ sở nghiên cứu và quyết định áp dụng

Đối chiếu nguồn gốc ngày 12/09/2026. Đây là giải thích lựa chọn cho dự án, không phải
tuyên bố tái lập hay vượt điểm paper.

| Nguồn gốc | Ý tưởng liên quan | Quyết định cho hệ thống |
|---|---|---|
| [SDP-DST, EMNLP 2021](https://aclanthology.org/2021.emnlp-main.404/) | Dùng mô tả schema để model suy ra các slot của hội thoại | Mô tả field, action, slot bằng tiếng Việt; train output có cấu trúc |
| [IC-DST, Findings EMNLP 2022](https://aclanthology.org/2022.findings-emnlp.193/) | Biểu diễn bài toán state tracking qua schema; dùng ví dụ để hướng model | State + lượt liên quan + patch; ví dụ few-shot chỉ lấy từ TRAIN. Không thực thi SQL do model sinh |
| [CONQRR, EMNLP 2022](https://aclanthology.org/2022.emnlp-main.679/) | Viết lại câu hội thoại thành truy vấn độc lập để dùng retriever | Backend dựng query từ state đã xác minh. Chưa triển khai RL query rewriting trong tuần |
| [QLoRA, 2023](https://arxiv.org/abs/2305.14314) | Fine-tune adapter trên base đóng băng lượng tử 4-bit | Giảm VRAM training trên GPU 16 GB; phải đo lại chất lượng và tốc độ sau export |
| [PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization), [LoRA](https://huggingface.co/docs/peft/developer_guides/lora) | Quy trình k-bit training và chọn target modules | Kiểm layer theo kiến trúc, gradient và số tham số trainable; không sao chép target của Qwen3 sang Qwen3.5 |
| [llama.cpp grammars](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) | Ràng buộc output theo grammar/JSON schema được hỗ trợ | Chặn output sai cấu trúc; Backend vẫn kiểm ID, provenance và tính đúng của patch |

Các lựa chọn state budget, một checkpoint đa nhiệm, ngưỡng điểm và cách chia ngày trong
kế hoạch là quyết định kỹ thuật của nhóm. Chưa có nghiên cứu nào ở đây chứng minh chúng
là cách tối ưu cho toàn bộ dữ liệu hành chính tiếng Việt của công ty.

## Model shortlist

- [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B): baseline có sẵn; G4 có pilot trên
  task trả lời nhưng chưa đủ để quyết định model cho state tracking.
- [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507): checkpoint
  instruction non-thinking; dùng làm đối chứng ở trần 4B của dự án.
- [Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B): model card công bố chế độ
  non-thinking mặc định và hướng dùng fine-tune theo task. Cần thử runtime/export và
  decoder-only text path phù hợp; khả năng vision không nằm trong sprint.

Không chọn bằng điểm leaderboard chung. Ba ứng viên phải được chấm cùng nhiệm vụ tiếng
Việt, rồi so trước/sau fine-tune và bản lượng tử thực tế. Không mở thêm ứng viên khi chưa
hoàn tất phép so nhỏ này. Mục tiêu “nhẹ” áp dụng cho toàn service model + embedding,
không chỉ kích thước file trọng số.

## Ba điều cần sửa trong cách hiểu kết quả cũ

1. G5 cũ có validation 10 scenario gốc, phần còn lại là biến thể evidence. Chưa thể
   suy ra kết luận model tốt nhất cho intent/context từ kết quả đó.
2. `benchmark` G4 chuẩn bị target ở lượt cuối; một số số liệu mang nhãn multi-turn
   chưa chấm đủ mọi lượt. Protocol mới chấm full rollout bằng predicted state.
3. Fine-tune trước học target câu trả lời nguyên văn với evidence. Muốn dạy nhận
   intent và sửa/giữ/xóa context, cần target riêng tương ứng; chỉ tăng số câu QA không
   bảo đảm học được hai chức năng này.
