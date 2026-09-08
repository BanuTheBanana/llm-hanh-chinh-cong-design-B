# Chỉ mục tài liệu

## Tài liệu trung tâm

1. [Chiến lược triển khai từ nhỏ đến lớn](00-chien-luoc-trien-khai-tu-nho-den-lon.md)
2. [Kế hoạch và phân công Giai đoạn 2](giai-doan-2/02-phan-cong-giai-doan-2.md)
3. [Chỉ mục Giai đoạn 2](giai-doan-2/README.md)
4. [Grounded API Contract G2](contracts-g2.md)
5. [API Contract G1](contracts-g1.md)
6. [Hồ sơ phân công và nghiệm thu Giai đoạn 1](01-phan-cong-giai-doan-1.md)
7. [Chỉ mục Giai đoạn 1](giai-doan-1/README.md)

Chiến lược là roadmap đang có hiệu lực. Phân công G2 là danh sách task hiện tại.
Contract G1 vẫn là source of truth của code/runtime đang chạy; file phân công G1
là hồ sơ nghiệm thu đã hoàn tất, không phải backlog hiện tại.

## Nhóm tài liệu

| Thư mục | Vai trò | Có dùng để triển khai G1 không? |
|---|---|---|
| `architecture/` | Sơ đồ hệ thống và file nguồn draw.io | Chỉ tham khảo |
| `giai-doan-2/` | Kế hoạch, contract và báo cáo thực thi G2 | Có, là trọng tâm hiện tại |
| `archive/` | Tài liệu cũ, giữ lại lịch sử quyết định | Không |
| `parked/` | Kiến trúc mục tiêu và module nâng cao tạm hoãn | Chỉ mở khi có trigger |

Không thêm tài liệu mới ở repository root. Tài liệu đang dùng đặt trực tiếp trong `docs/`; tài liệu module tương lai đặt trong thư mục con có tên rõ ràng.
