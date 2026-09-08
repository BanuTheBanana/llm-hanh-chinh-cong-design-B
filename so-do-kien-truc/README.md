# Sơ đồ kiến trúc để báo cáo mentor

Hai bản vẽ mô tả kiến trúc đề xuất cho trợ lý hành chính công, dựa trên workflow đã được nhóm trao đổi và chỉnh sửa. Đây là tài liệu thiết kế, chưa phải thông báo các service đã triển khai.

## File nên mở

**[kien-truc-hanh-chinh-cong.drawio](kien-truc-hanh-chinh-cong.drawio)** chứa cả hai bản dưới dạng hai trang:

1. **01 - Tổng quan:** 10 khối chính; dùng để giới thiệu sản phẩm, vị trí LLM, backend, bộ nhớ, RAG và huấn luyện offline.
2. **02 - Chi tiết:** luồng 01–14, nhánh hỏi lại, kiểm tra Case Card/câu trả lời, kho dữ liệu dùng chung, ingestion và train/eval.

Nếu cần hai file độc lập:

| Bản | File draw.io chỉnh sửa được | Ảnh chèn slide | Vector để phóng to |
|---|---|---|---|
| Tổng quan | [01-tong-quan.drawio](01-tong-quan.drawio) | [01-tong-quan.png](01-tong-quan.png) | [01-tong-quan.svg](01-tong-quan.svg) |
| Chi tiết | [02-chi-tiet.drawio](02-chi-tiet.drawio) | [02-chi-tiet.png](02-chi-tiet.png) | [02-chi-tiet.svg](02-chi-tiet.svg) |

## Mở và sửa trong draw.io

1. Mở ứng dụng draw.io hoặc diagrams.net.
2. Chọn **File → Open From → Device**, rồi chọn file .drawio. Cũng có thể kéo file vào trình chỉnh sửa.
3. Với file chứa cả hai bản, chuyển trang bằng tab bên dưới.
4. Các khối, chữ và đường nối đều là đối tượng draw.io; không phải một ảnh được nhúng vào canvas.
5. Mỗi khối đã được group để kéo di chuyển cùng nhau. Có thể chọn thành phần bên trong group hoặc dùng **Arrange → Ungroup** để sửa riêng từng dòng chữ.
6. Sau khi sửa, lưu .drawio và xuất lại PNG/SVG/PDF bằng menu **File → Export as** nếu cần cập nhật ảnh báo cáo.

Các SVG/PNG kèm theo là bản xem trước tại thời điểm tạo, không tự thay đổi khi bạn sửa file draw.io.

## Cách trình bày bản tổng quan

Đi theo đường chính: **Web → Backend/API → Queue/Worker → Luồng xử lý nghiệp vụ → Socket.IO → Web**.

Sau đó giải thích ba khối hỗ trợ:

- **PostgreSQL:** lưu người dùng, hội thoại, từng case, facts, summary và audit để hôm sau có thể tiếp tục đúng hồ sơ.
- **Qwen:** một runtime nhỏ dùng cho trích xuất và diễn giải; backend chuẩn bị ngữ cảnh cho từng lần gọi.
- **Procedure Store/RAG:** cung cấp thủ tục, điều kiện và nguồn có phiên bản. Nội dung mới được đưa vào đây qua luồng quản trị dữ liệu.

Cuối cùng chỉ vào nhánh offline: công ty cấp tài nguyên để fine-tune, lượng tử hóa và đánh giá; chỉ model đạt quality gate mới được triển khai.

## Cách đọc bản chi tiết

Luồng chính chạy theo số:

~~~text
Hàng 1: 01 → 02 → 03 → 04 → 05 → 06
Hàng 2: 11 ← 10 ← 09 ← đủ dữ kiện ← 08 ← 07 (từ 06)
Hàng 3: 12 (từ 11) → đạt kiểm tra? → 13 → 14 → Web
~~~

Các vùng bên dưới là tài nguyên và pipeline hỗ trợ, không phải các bước mà mỗi tin nhắn phải chạy qua:

- **B:** D1 PostgreSQL trạng thái; D2 Procedure Store; D3 chỉ mục tìm kiếm; D4 file/snapshot; M1 Qwen runtime.
- **C:** admin nhập dữ liệu → chuẩn hóa/review → tạo chỉ mục staging/kiểm thử → publish. Upload cá nhân và summary thuộc nhánh riêng theo user/case.
- **D:** dữ liệu train được phép → fine-tune/lượng tử hóa → đánh giá → phát hành model.

Các mã D1–D4/M1 trên khối runtime chỉ tài nguyên mà khối đó sử dụng. Cách tham chiếu này giúp tránh nhiều đường nối đè lên luồng chính.

## Các điểm thiết kế đã đưa vào bản vẽ

1. Backend kiểm tra session và quyền conversation/case. Case có thể chưa tồn tại ở câu hỏi đầu; Qwen chỉ đề xuất ý định, backend quyết định chọn/tạo case.
2. Message và outbox được ghi cùng transaction, sau commit mới publish queue job. Xử lý tuần tự theo conversation; nếu hai conversation cùng sửa một case thì kiểm tra version hoặc khóa case.
3. Context chỉ lấy dữ liệu thuộc đúng user/case và phạm vi lượt đang xử lý. Facts do người dùng cung cấp có nguồn; summary không tự trở thành bằng chứng xác minh.
4. Tra sơ bộ procedure schema trước khi hỏi dữ kiện bắt buộc. Chỉ hỏi thông tin ảnh hưởng đến câu hỏi hiện tại; không bắt người dùng điền toàn bộ hồ sơ để hỏi thông tin chung.
5. Case Card là đề xuất có kiểm tra. Lỗi định dạng do model cần sửa nội bộ hoặc xử lý lỗi; không biến mọi lỗi model thành yêu cầu người dùng bổ sung dữ liệu.
6. Procedure Engine xét điều kiện, nhánh giấy tờ thay thế và trạng thái. Lời người dùng nói đã có giấy tờ không chứng minh giấy tờ đã được cơ quan có thẩm quyền xác minh.
7. Hai khối Qwen ở bước 06 và 11 dùng **cùng M1**. BGE-M3 phục vụ dense retrieval; BM25 phục vụ tìm từ khóa; reranker chấm độ liên quan. Đây là các vai trò khác nhau.
8. Verifier kiểm cả nội dung trả ra, không chỉ kiểm claims JSON hoặc sự tồn tại của citation. MVP nên render thông tin trọng yếu từ cấu trúc đã duyệt; kiểm ngữ nghĩa là phần bổ sung và vẫn có sai số.
9. Thiếu evidence phù hợp/phiên bản áp dụng thì không tiếp tục tạo hướng dẫn như đã đủ nguồn; trả mẫu chưa đủ căn cứ hoặc chuyển hỗ trợ.
10. Các câu hỏi làm rõ được tạo từ mẫu backend/required_facts đã duyệt. Nếu dùng Qwen viết lại các câu hỏi này, chúng cũng phải qua kiểm tra trước khi gửi.
11. Trạng thái xử lý được gửi sớm. Bản nháp Qwen giữ nội bộ; câu trả lời chỉ gửi hoặc chia nhỏ để hiển thị sau khi đã kiểm tra và lưu. Đây có thể là hiển thị dần bản đã duyệt, không phải stream token thô ngay khi model sinh.
12. Nếu viết lại, giới hạn một lần trong MVP rồi kiểm lại. Không đạt tiếp thì dùng mẫu chưa đủ căn cứ/hỏi lại/chuyển hỗ trợ. Memory Delta được validate và chỉ ghi lại theo version; retry không áp dụng delta hai lần.
13. Dữ liệu chính thức và upload cá nhân tách quyền. Không tự đưa file người dân tải lên thành nguồn thủ tục chung.
14. MCP là giao diện gọi công cụ đọc dữ liệu/cập nhật nguồn; chất lượng và độ mới vẫn cần pipeline kiểm tra, version và publish.

## Mức độ chốt công nghệ

Các tên công nghệ là phương án hiện tại: backend API/worker, PostgreSQL, Redis, Qdrant, MinIO, Socket.IO, Qwen nhỏ, BGE-M3 và BGE reranker.

BM25 được vẽ là một **lexical index riêng về chức năng**; chưa khẳng định Qdrant tự thực hiện toàn bộ BM25 hoặc chốt thêm một hệ quản trị tìm kiếm. Cần chọn implementation sau khi nhận dữ liệu và đo baseline.

Các khối là module logic, không tương ứng một-một với container hay microservice. D1/D2 có thể dùng chung PostgreSQL. API, phần kiểm tra và bộ điều phối có thể nằm trong cùng codebase; worker và model server tách tiến trình khi cần.

Qwen 1.7B–4B và Q4/Q5 là cấu hình ứng viên. Quyết định cuối dựa trên chất lượng, latency, VRAM/RAM và mức đồng thời trên máy triển khai.

## Nguồn và cách tạo lại

- [Tài liệu kiến trúc gốc](../kien-truc-he-thong-tro-ly-hanh-chinh-cong.md).
- [Khung dự án](../khung-du-an-LLM.md).
- Những điều chỉnh trong trao đổi gần nhất: tra schema trước khi hỏi, checklist theo điều kiện, tách nguồn user/thủ tục, kiểm cả answer và duyệt trước khi stream.

[tao_so_do.py](tao_so_do.py) sinh file XML draw.io và SVG từ cùng mô tả hình học; không cần thư viện ngoài Python tiêu chuẩn:

~~~powershell
python so-do-kien-truc/tao_so_do.py
~~~

Lệnh này tái tạo và ghi đè các file .drawio/.svg được script quản lý, **không giữ các chỉnh sửa tay đã thực hiện trong draw.io**. Nếu đã chỉnh tay, hãy lưu thành tên khác trước khi chạy lại. PNG được chụp từ SVG bằng trình duyệt; không được tái tạo bởi lệnh trên.

Đã kiểm tra: XML đọc được, các ID/đường nối tham chiếu hợp lệ, đủ hai trang, không chồng khối hoặc vượt canvas; các bản SVG/PNG đã được kiểm tra trực quan.
