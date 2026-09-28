# Báo cáo chất lượng dataset D0

Dataset `synthetic-demo-v1` được tạo bằng script, không crawl Internet và không
chứa PII. Gate kỹ thuật yêu cầu:

- đúng 3 nguồn, 3 thủ tục, 24 fragment và 33 câu hỏi;
- raw/fragment SHA-256 khớp;
- mọi procedure/source/fragment/gold reference hợp lệ;
- đủ tám business field và provenance;
- có cả DEV và TEST;
- contract fixture không rò URL/score/metadata sang AI request;
- mọi source thuộc `fixture.invalid` và `D0_SYSTEM_SMOKE`.

Kết quả ngày 09/09/2026:

| Gate | Kết quả |
|---|---|
| Validator `publish`, D0 | Pass, không warning |
| DEV | 23 câu; Recall@5 = 1.0; MRR = 0.7595; 0 câu fail |
| TEST | 10 câu; Recall@5 = 1.0; MRR = 0.75; 0 câu fail |

Raw result nằm ở `retrieval-dev.json` và `retrieval-test.json`. Các điểm này chỉ
phản ánh khả năng kiểm thử dữ liệu giả, không phản ánh chất lượng trên thủ tục
hành chính thật.
