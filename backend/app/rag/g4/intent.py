"""Lexical field intent, independent of procedure identification."""

import re

from app.rag.retrieval import normalize

PATTERNS = {
    "receiving_authority": (
        r"\b(?:nop|gui|tiep nhan)(?: ho so)? (?:o |tai )?dau\b",
        r"\b(?:den|toi) (?:dau|co quan nao)\b",
        r"\b(?:o dau|tai dau|co quan nao)\b",
        r"\b(?:noi nop|noi tiep nhan|dia diem|co quan tiep nhan|don vi tiep nhan)\b",
        r"\b(?:co quan|don vi|bo phan) (?:nao )?(?:tiep nhan|giai quyet|xu ly)\b",
        r"\b(?:ai|noi nao) (?:tiep nhan|giai quyet|xu ly)\b",
        r"\b(?:co quan|don vi|bo phan) nao\b",
        r"\b(?:mang|dua|gui).{0,80}\b(?:toi|den) (?:dung )?(?:co quan|don vi|bo phan|noi) nao\b",
    ),
    "required_documents": (
        r"\b(?:thanh phan ho so|ho so gom|ho so can (?:co |nhung )?gi)\b",
        r"\b(?:giay to|tai lieu|bo ho so).{0,60}\b(?:gom|can co|nhung gi|gi nao|gi)\b",
        r"\b(?:can|chuan bi) (?:nhung )?gi\b",
        r"\b(?:can |phai )?mang(?: theo)? (?:giay to |tai lieu )?(?:gi|nhung gi|gi nao)\b",
    ),
    "fees": (r"\b(?:phi|le phi|bao nhieu tien|ton bao nhieu|chi phi|mien phi|fees)\b",),
    "processing_times": (
        r"\b(?:thoi gian|bao lau|may ngay|bao nhieu ngay|thoi han|hen tra|khi nao co ket qua)\b",
        r"\b(?:giai quyet|xu ly) (?:trong )?(?:bao lau|may ngay)\b",
        r"\bcho.{0,60}\bket qua.{0,30}\b(?:bao lau|may ngay)\b",
    ),
    "submission_methods": (
        r"\b(?:hinh thuc|phuong thuc|truc tuyen|online|buu dien|buu chinh|nop cach nao)\b",
        r"\b(?:nop|lam) (?:qua mang|truc tiep)\b",
        r"\b(?:gui|chuyen|nop)(?: ho so)? (?:qua|bang) (?:mang|online|buu dien|buu chinh)\b",
        r"\b(?:cach nop|nop (?:ho so )?bang (?:nhung )?hinh thuc|nop .* nhu the nao)\b",
        r"\bho so.{0,60}\b(?:gui|chuyen).{0,40}\b(?:cach nao|the nao)\b",
    ),
    "steps": (r"\b(?:trinh tu|cac buoc|quy trinh|buoc nao|lam the nao|lan luot)\b",),
    "legal_bases": (
        r"\b(?:can cu phap ly|co so phap ly|van ban nao.{0,50}can cu|quy dinh.{0,50}van ban nao)\b",
    ),
    "applicant_scope": (r"\b(?:doi tuong|ai duoc|ai co the|nhung ai|truong hop nao)\b",),
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
