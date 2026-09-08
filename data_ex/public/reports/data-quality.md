# Data quality report

Status: `SPIKE_NORMALIZED_PENDING_CROSS_REVIEW`

One official source-level-2 snapshot has been captured. It is a legal-document
listing, not a procedure page, so no `ProcedureRecord`, fragment, or gold
question is derived from it.

Source review notes:

- URL: `https://vanban.chinhphu.vn/he-thong-van-ban?classid=1&mode=1`
- `robots.txt`: fetched; `User-agent: *` allows `/`.
- Terms/attribution: page states that republication must credit the Government
	Information and Communications Department or `www.chinhphu.vn`.
- Access: one direct HTML GET, 30-second timeout, no login/CAPTCHA bypass,
	`User-Agent: CaoData-G2-demo/1.0`.
- Snapshot: `data/demo_public/raw/legal_portal/2026-09-08/he-thong-van-ban.html`
- SHA-256: `515e72e4560235d56e39b18eb5f29e95f6eba73895a4c23b4412b7ed6f3326ec`
- Review: `PENDING`; a second reviewer must confirm the source before it is
	used in the corpus.

The downloader was re-run against the same URL into a temporary file. The
second response had SHA-256 `e3796c9c0203b89cc99c20fb5d8d747486c9cc8a4445d37c52f45d6ee74394cf`.
The original snapshot was not overwritten; the difference must be reviewed as
possible dynamic content or source change before treating either snapshot as a
stable legal reference.

## HCMC civil-status spike candidate

The official HCMC portal qualifies as a first-level procedure publisher for the
spike. The index identifies `165/QĐ-UBND` as a civil-status decision and links
to a detail page with the signed attachment `165.rar`. The archive contains:

- `DM_TTHC_HO_TICH_signed.pdf`
- `QD_signed (1).pdf`

The HCMC `robots.txt` endpoint returned `404 Not Found`. Only the index, detail
page, and one linked attachment were fetched, with no pagination or broad crawl.
The portal page states the attribution requirement: cite the "Trang thông tin
điện tử Văn phòng UBND TP.HCM" when republishing. All three HCMC sources remain
`PENDING` until a second reviewer reads the PDFs and confirms the applicable
procedure/version fields.

Spike normalization output:

- 1 `ProcedureRecord`: `birth_registration_hcmc_demo`.
- 7 `ProcedureFragment` records covering scope, processing time, submission
	method/location, receiving authority, legal bases, effective date and fees.
- 10 `GoldQuestion` records across `DEV` and `TEST`.
- `required_documents` and `steps` remain empty because the reviewed catalogue
	snapshot does not provide those sections. No replacement facts were inferred.
- All gold questions use `contains_pii=false`; questions with unsupported scope
	are marked `NEED_CLARIFICATION` or `INSUFFICIENT_DATA`.

## Remaining Tu work

- Obtain and review the official detailed procedure page for birth registration
	(or an approved manual export). The current decision catalogue does not state
	the required documents or complete steps, so those `ProcedureRecord` arrays
	intentionally remain empty.
- Have Minh review source-to-fragment links and have Hoan review all
	`expected_points` and `forbidden_points` before changing any source to
	`APPROVED`.
- Confirm the effective date and local jurisdiction against the official
	detailed procedure source before freezing the spike version.
- Add the remaining procedure-specific questions after the detailed source is
	available; the current 10 questions are only a limited catalogue spike.

## Detailed-source crawl attempts

- `https://dichvucong.gov.vn/p/home/dvc-trang-chu.html`: rejected by the
	official site's WAF with support ID `844787494960454000`; no bypass attempted
	and no snapshot written.
- HCMC internal-process pages for Decisions 74/2026/QĐ-UBND, 3630/2025/QĐ-UBND
	and 3544/2025/QĐ-UBND were fetched once each. Their HTML did not expose a
	civil-status procedure or attachment directly, so no new source was added.

The next source needed is an official detailed procedure URL or manual export
that explicitly contains `Thành phần hồ sơ` and `Trình tự thực hiện` for
`Đăng ký khai sinh`. Until then, leaving `required_documents` and `steps` empty
is intentional and contract-compliant.

Validation run on 2026-09-08:

```text
python tools/data/validate_dataset.py --root .
{"errors": 0, "records": {"fragments": 7, "procedures": 1, "questions": 10, "sources": 4}}
```

Once a procedure source is approved, add its immutable raw snapshot and replace
this report with the full validator output plus the normalized data review.
