# Nghiệm thu Giai đoạn 6

## Kết luận

G6 đã hoàn tất phần triển khai kỹ thuật nhưng **không đạt gate nghiệm thu intent/context**.
Candidate được khóa và chạy đúng một FINAL độc lập; kết quả được giữ nguyên, không tạo thêm
TEST để đuổi điểm.

## Kết quả FINAL duy nhất

| Chỉ số | Kết quả | Gate | Trạng thái |
|---|---:|---:|:---:|
| Schema hợp lệ | 100% | 100% | Đạt |
| Semantic hợp lệ | 100% | 100% | Đạt |
| Full-state | 83,33% | ≥95% | Không đạt |
| Field macro-F1 | 90,74% | ≥95% | Không đạt |
| Hội thoại đúng trọn chuỗi | 60% | ≥90% | Không đạt |
| P95 toàn tuyến | 2.562 ms | ≤3.000 ms | Đạt |

Theo nhóm, direct và clarification đạt 100%; follow-up đạt 90,91% và scope/date đạt 83,33%.
Ba nhóm yếu là boundary 71,43%, correction/switch 55,56% và reset 33,33%. Kết quả cho thấy
DEV trước FINAL chưa đủ đại diện cho các cách diễn đạt mới.

## Những phần đã hoàn thành

- Policy hybrid v4, verifier và fast path 0-token đã được tích hợp.
- 107 test AI Service và Ruff đều pass.
- Qwen3.5-2B đã được fine-tune lại và so sánh công bằng với 1.7B, 2B pilot và 4B.
- Qwen3-4B là candidate duy nhất qua gate DEV; Docker đủ 8 service healthy, Web/Backend/AI
  và tuyến 0-token đều được smoke thành công trước FINAL.
- FINAL gồm 60 lượt/20 hội thoại, không trùng hoặc gần trùng TRAIN, DEV và ba holdout G5.
  Gold/raw được giữ ngoài Git; repository chỉ lưu số tổng hợp.

## Trạng thái bàn giao

Không phát hành cấu hình này như một bản intent/context đã nghiệm thu. Vòng phát triển kế tiếp
cần tập trung vào correction/switch, reset và boundary bằng dữ liệu TRAIN mới và kiểm thử DEV
theo họ cách diễn đạt. Chỉ sau khi model hoặc policy thay đổi được khóa mới được tạo một holdout
độc lập mới; không chạy lại FINAL G6.

Aggregate công khai:
[`g6-intent-context-final-result-20260914.json`](../../evaluation/baselines/g6-intent-context-final-result-20260914.json).
Kết quả này chỉ đánh giá intent/context, không chứng minh câu trả lời đúng pháp luật.
