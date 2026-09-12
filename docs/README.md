# Chỉ mục tài liệu

## Tài liệu trung tâm

Ưu tiên thực hiện: [fine-tune và hoàn thiện intent/context theo yêu cầu mentor](giai-doan-5/08-ke-hoach-intent-context-finetune.md).

Lộ trình sau nền tảng cơ bản: [Chiến lược dài hạn và chặng G5](lo-trinh-phat-trien-he-thong.md).
Tài liệu này định hướng các chặng lớn; biên bản từng giai đoạn vẫn lưu kết quả thực tế.

1. [Chỉ mục và kết quả Giai đoạn 5](giai-doan-5/README.md)
2. [Biên bản nghiệm thu Giai đoạn 5](giai-doan-5/07-nghiem-thu-giai-doan-5.md)
3. [Chiến lược triển khai từ nhỏ đến lớn](00-chien-luoc-trien-khai-tu-nho-den-lon.md)
4. [Định hướng Giai đoạn 4](giai-doan-4/00-nghien-cuu-va-dinh-huong-g4.md)
5. [Phân công Giai đoạn 4](giai-doan-4/01-phan-cong-giai-doan-4.md)
6. [Chiến lược và phân công Giai đoạn 3](giai-doan-3/03-chien-luoc-va-phan-cong-giai-doan-3.md)
7. [Audit dataset công ty](giai-doan-3/01-audit-dataset-cong-ty.md)
8. [Data contract G3 giữa Tú và Minh](giai-doan-3/02-contract-data-g3.md)
9. [Runbook Qwen3-1.7B local](giai-doan-3/04-runbook-qwen-local.md)
10. [Chỉ mục Giai đoạn 3](giai-doan-3/README.md)
11. [Kế hoạch và phân công Giai đoạn 2](giai-doan-2/02-phan-cong-giai-doan-2.md)
12. [Chỉ mục Giai đoạn 2](giai-doan-2/README.md)
13. [Grounded API Contract G2](contracts-g2.md)
14. [API Contract G1](contracts-g1.md)
15. [Hồ sơ phân công và nghiệm thu Giai đoạn 1](01-phan-cong-giai-doan-1.md)
16. [Chỉ mục Giai đoạn 1](giai-doan-1/README.md)

Lộ trình dài hạn định hướng công việc sau G4; chiến lược từ nhỏ đến lớn lưu kế hoạch
nền tảng G1–G3. Phân công G4 và biên bản nghiệm thu lưu tiến độ cùng các hạn chế còn lại.
G1/G2/G3 đã nghiệm thu và tiếp tục được giữ làm regression baseline.

## Nhóm tài liệu

| Thư mục | Vai trò | Trạng thái |
|---|---|---|
| `architecture/` | Sơ đồ hệ thống và file nguồn draw.io | Tham khảo |
| `giai-doan-5/` | Phạm vi, thực nghiệm, runbook và nghiệm thu G5 | Limited release trên demo10 |
| `giai-doan-4/` | Nghiên cứu, triển khai, đánh giá và bàn giao G4 | Đã tích hợp; gate chất lượng chưa đạt |
| `giai-doan-3/` | Audit data, Qwen local, tích hợp và nghiệm thu G3 | Đã hoàn tất nền tảng cơ bản |
| `giai-doan-2/` | Kế hoạch và biên bản nghiệm thu G2 | Đã hoàn tất |
| `archive/` | Tài liệu cũ, giữ lại lịch sử quyết định | Lưu trữ |
| `parked/` | Kiến trúc mục tiêu và module nâng cao tạm hoãn | Chỉ mở khi có trigger |

Không thêm tài liệu mới ở repository root. Tài liệu đang dùng đặt trực tiếp trong `docs/`; tài liệu module tương lai đặt trong thư mục con có tên rõ ràng.
