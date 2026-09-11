"""Lexical field intent, independent of procedure identification."""

import re

from app.rag.retrieval import normalize

PATTERNS = {
    "receiving_authority": (
        r"\b(?:nop|gui|tiep nhan)(?: ho so)? (?:o |tai )?dau\b",
        r"\b(?:den|toi) (?:dau|co quan nao)\b",
        r"\b(?:o dau|tai dau|co quan nao)\b",
        r"\b(?:noi nop|noi tiep nhan|dia diem|co quan tiep nhan|don vi tiep nhan)\b",
    ),
    "required_documents": (
        r"\b(?:giay to|thanh phan ho so|ho so gom|ho so can (?:nhung )?gi)\b",
        r"\b(?:can|chuan bi) (?:nhung )?gi\b",
        r"\b(?:can |phai )?mang(?: theo)? (?:giay to )?gi\b",
    ),
    "fees": (r"\b(?:phi|le phi|bao nhieu tien|ton bao nhieu|chi phi|mien phi|fees)\b",),
    "processing_times": (
        r"\b(?:thoi gian|bao lau|may ngay|bao nhieu ngay|thoi han|hen tra|khi nao co ket qua)\b",
    ),
    "submission_methods": (
        r"\b(?:hinh thuc|phuong thuc|truc tuyen|online|buu dien|buu chinh|nop cach nao)\b",
        r"\b(?:nop|lam) (?:qua mang|truc tiep)\b",
        r"\b(?:cach nop|nop (?:ho so )?bang (?:nhung )?hinh thuc|nop .* nhu the nao)\b",
    ),
    "steps": (r"\b(?:trinh tu|cac buoc|quy trinh|buoc nao|lam the nao)\b",),
    "legal_bases": (r"\b(?:can cu phap ly|co so phap ly)\b",),
    "applicant_scope": (r"\b(?:doi tuong|ai duoc|ai co the)\b",),
}


def detect_fields(query: str, names=()) -> set[str]:
    text = " " + normalize(query) + " "
    # A procedure title can contain words such as fees/time without asking that field.
    for name in sorted(set(names), key=len, reverse=True):
        text = text.replace(" " + normalize(name) + " ", " ")
    fields = {f for f, patterns in PATTERNS.items() if any(re.search(p, text) for p in patterns)}
    # "hồ sơ" is the object of a submission/location question, not a document intent.
    if re.search(r"\bho so\b", text) and (
        not fields or re.search(r"\bho so va\b|\bva ho so\b", text)
    ):
        fields.add("required_documents")
    if re.search(r"\bdocuments\b", text):
        fields.add("required_documents")
    return fields
