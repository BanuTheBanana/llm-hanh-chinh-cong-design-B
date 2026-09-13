# Phân tích lỗi intent/context từ G5

FINAL V3 có 11/60 lượt sai full-state. Báo cáo này chỉ giữ thống kê, không chứa câu hỏi, gold label
hoặc raw output private.

| Thành phần sai | Số lượt |
|---|---:|
| Field intent | 6 |
| Dialogue act | 4 |
| Topic action | 2 |
| Procedure | 1 |
| Địa phương | 1 |

Theo nhóm, clarification đạt 33,33%, scope/date 50% và follow-up 58,33%. Nguyên nhân kỹ thuật
chính là từ khóa phụ tạo field giả, nhãn `PROVIDE_CLARIFICATION` xuất hiện khi không có pending,
model xóa scope dù người dùng không yêu cầu và tín hiệu procedure rõ bị nhãn boundary lấn át.

Policy v4 chuyển các lỗi trên thành bất biến tổng quát:

- Chỉ coi là clarification khi state có pending tương ứng.
- Procedure/field chắc chắn thắng nhãn chào hoặc ngoài phạm vi bị dự đoán nhầm.
- Không suy ra legal basis chỉ vì câu có từ “quy định”, hoặc hồ sơ chỉ được nhắc trong câu hỏi quy trình.
- Chỉ chấp nhận `CLEAR` khi câu hiện tại có yêu cầu xóa đúng slot.
- Nhận diện rõ câu sửa địa bàn và giữ scope qua follow-up.

Kết quả V1–V3 sau sửa chỉ dùng làm regression, được lưu tại
[`g6-opened-regression-policy-v4-20260913.json`](../../evaluation/baselines/g6-opened-regression-policy-v4-20260913.json).

