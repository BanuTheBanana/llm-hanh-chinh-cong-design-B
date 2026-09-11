# Review ba file TEST_V3 của Tú

Ngày review: **11/09/2026**. Báo cáo chỉ ghi cấu trúc, hash và số tổng hợp; không
đưa câu hỏi, đáp án hoặc evidence riêng tư vào Git.

## Phần Tú làm được

- Tạo 40 scenario TEST_V3, toàn bộ là hội thoại ba lượt `user → assistant → user`.
- Phủ đủ 10 thủ tục và bốn field trọng yếu: nơi tiếp nhận, hồ sơ, phí và thời gian;
  mỗi field có 10 scenario.
- Scenario ID và group ID không trùng; không có PII theo pattern kiểm tra.
- Hội thoại TEST_V3 không trùng exact/near-duplicate với DEV hoặc TEST_V2 đã khóa.
- Hash file gốc khớp manifest Tú gửi:
  `02acbe925e0756cd62850c4dc5c21cc123f445e33bf7fa3a66d655b96f19b3c8`.

## Sai sót trong ba file gửi ban đầu

1. 40/40 scenario thiếu `scenario_version`, `contains_pii`, `expected_points` và
   metadata `review`; đồng thời có field ngoài schema hiện hành.
2. 40/40 trường `question` trỏ tới câu đầu, trong khi lượt cần chấm là user cuối.
   Nếu chạy trực tiếp, evaluator sẽ chấm sai mục tiêu.
3. So với corpus đã duyệt: 20 `gold_answer`, 5 `must_include` và 3 trạng thái chưa
   khớp nguồn.
4. File TEST_V2 gửi kèm không phải bản đã khóa: hash khác và dùng cấu trúc bốn lượt
   kết thúc bằng assistant. File này đã bị loại, không thay TEST_V2 chuẩn.
5. `test_g4_test_v3.py` dùng root/path/schema cũ và import module generator chưa được
   gửi hoặc push, nên không chạy trong repository hiện tại.
6. `test_g4_tu_scenarios.py` gọi API generator cũ, mong kết quả tuple và chấp nhận
   hội thoại kết thúc bằng assistant; trái contract G4 hiện tại.

## Phần Hoan đã sửa và tích hợp

- Giữ nguyên nội dung hội thoại TEST_V3; tạo bản reviewed riêng, không ghi đè bản Tú gửi.
- Gán đúng target user cuối, dựng lại gold/status/fragment/expected point từ corpus
  đã duyệt và kế thừa cờ nguồn mơ hồ từ review DEV/TEST_V2.
- Bổ sung schema manifest hidden test, validator source binding/leakage/PII/hash và
  test hư cấu trong repository.
- Mở rộng release evaluator để đọc TEST_V3 đã khóa và chỉ xuất metric tổng hợp.
- Bản reviewed đạt validator: 40 scenario, 40 multi-turn, 10 thủ tục, 4 field × 10,
  không có lỗi; hash mới:
  `bab36260dc4a920d6f315b73a0414834d90fedd9ea6c2bf7986a3bc12566d1a1`.

## Kết quả và yêu cầu cho lần sau

TEST_V3 đã được chấm đúng một lần trên commit `824fd50` và **không đạt release gate**.
Không tái sử dụng hay chỉnh TEST_V3. Tú cần tạo TEST_V4 hoàn toàn mới, chỉ gửi cho
Hoan sau khi candidate mới đã khóa; giữ đúng schema mới và không gửi kèm TEST cũ.
