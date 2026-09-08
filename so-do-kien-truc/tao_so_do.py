"""Generate editable draw.io diagrams and matching standalone SVG previews.

Run: python so-do-kien-truc/tao_so_do.py
All generated paths are relative to this script. No third-party dependency.
The diagrams describe a proposed architecture, not implemented services.
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
import html
import textwrap


OUT = Path(__file__).resolve().parent
FONT = "Segoe UI"
INK = "#172B4D"
MUTED = "#56677F"
PAPER = "#F5F7FB"
PALETTE = {
    "blue": ("#EDF4FF", "#A9C5F4", "#2455A4"),
    "green": ("#EDF8F4", "#A0CFC0", "#147D66"),
    "purple": ("#F3EEFC", "#C5B2E9", "#7143AD"),
    "amber": ("#FFF7E8", "#E6C68D", "#A86A12"),
    "slate": ("#F1F4F8", "#C1CBD8", "#50627B"),
}


def esc(value):
    return html.escape(str(value), quote=True)


def wrap(value, width, size):
    # Text stays editable. Wrap at word boundaries; actual output is inspected.
    chars = max(12, int(width / (size * 0.51)))
    lines = []
    for line in value.split("\n"):
        lines.extend(textwrap.wrap(line, chars, break_long_words=False,
                                   break_on_hyphens=False) or [""])
    return lines


@dataclass
class Card:
    id: str
    x: float
    y: float
    w: float
    h: float
    title: str
    body: str = ""
    tone: str = "blue"
    eyebrow: str = ""
    diamond: bool = False

    def anchor(self, where):
        side, fraction = where if isinstance(where, tuple) else (where, 0.5)
        return {
            "L": (self.x, self.y + self.h * fraction),
            "R": (self.x + self.w, self.y + self.h * fraction),
            "T": (self.x + self.w * fraction, self.y),
            "B": (self.x + self.w * fraction, self.y + self.h),
        }[side]


@dataclass
class Link:
    source: str
    target: str
    start: object = "R"
    end: object = "L"
    via: list = field(default_factory=list)
    label: str = ""
    label_at: tuple = None
    color: str = "#536C90"
    dashed: bool = False
    both: bool = False


class Diagram:
    def __init__(self, slug, name, width, height, title, subtitle):
        self.slug, self.name = slug, name
        self.width, self.height = width, height
        self.title, self.subtitle = title, subtitle
        self.cards, self.links, self.sections, self.notes = {}, [], [], []

    def card(self, id, x, y, w, h, title, body="", tone="blue", eyebrow="",
             diamond=False):
        assert id not in self.cards
        self.cards[id] = Card(id, x, y, w, h, title, body, tone, eyebrow, diamond)

    def link(self, *args, **kwargs):
        self.links.append(Link(*args, **kwargs))

    def section(self, x, y, w, h, title, subtitle=""):
        self.sections.append((x, y, w, h, title, subtitle))

    def note(self, x, y, w, text, size=18, color=MUTED, bold=False):
        self.notes.append((x, y, w, text, size, color, bold))

    def validate(self):
        cards = list(self.cards.values())
        for n in cards:
            assert n.w > 0 and n.h > 0
            assert 0 <= n.x < n.x + n.w <= self.width, n.id
            assert 0 <= n.y < n.y + n.h <= self.height, n.id
            if not n.diamond:
                title_lines = wrap(n.title, n.w - 44, 23)
                body_lines = wrap(n.body, n.w - 44, 18)
                required = 47 + len(title_lines) * 29 + len(body_lines) * 24 + 15
                assert required <= n.h, (n.id, "text exceeds card", required, n.h)
        for i, a in enumerate(cards):
            for b in cards[i + 1:]:
                intersection_w = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
                intersection_h = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
                assert intersection_w <= 0 or intersection_h <= 0, (a.id, b.id)
        for e in self.links:
            assert e.source in self.cards and e.target in self.cards
            points = [self.cards[e.source].anchor(e.start), *e.via,
                      self.cards[e.target].anchor(e.end)]
            for x, y in points:
                assert 0 <= x <= self.width and 0 <= y <= self.height

    def shapes(self):
        # Yield common primitives so SVG and mxGraph use the same layout.
        yield ("rect", "canvas", 0, 0, self.width, self.height, PAPER, PAPER, 0, 0)
        yield ("text", "brand", 55, 25, self.width - 110, 24,
               "LUẬT ĐÚNG LÚC  /  TRỢ LÝ HÀNH CHÍNH CÔNG", 14, MUTED, True, "left")
        yield ("text", "title", 55, 57, self.width - 110, 57,
               self.title, 39, INK, True, "left")
        yield ("text", "subtitle", 58, 117, self.width - 115, 30,
               self.subtitle, 19, MUTED, False, "left")
        for i, (x, y, w, h, title, sub) in enumerate(self.sections):
            yield ("rect", f"section-{i}", x, y, w, h,
                   "#FFFFFF", "#DCE4EF", 1.2, 16)
            yield ("text", f"section-title-{i}", x + 24, y + 16, w - 48, 24,
                   title, 16, MUTED, True, "left")
            if sub:
                yield ("text", f"section-sub-{i}", x + 24, y + 43, w - 48, 24,
                       sub, 17, MUTED, False, "left")

    def node_shapes(self, n):
        fill, stroke, accent = PALETTE[n.tone]
        if n.diamond:
            yield ("diamond", n.id + "-box", n.x, n.y, n.w, n.h,
                   fill, stroke, 1.7, 0)
            lines = n.title.split("\n")
            top = n.y + (n.h - len(lines) * 25) / 2
            for i, line in enumerate(lines):
                yield ("text", n.id + f"-line-{i}", n.x + 15, top + i * 25,
                       n.w - 30, 25, line, 19, INK, True, "center")
            return
        yield ("rect", n.id + "-box", n.x, n.y, n.w, n.h,
               fill, stroke, 1.5, 12)
        yield ("rect", n.id + "-accent", n.x, n.y + 18, 5, n.h - 36,
               accent, accent, 0, 2)
        yield ("text", n.id + "-eyebrow", n.x + 22, n.y + 15,
               n.w - 44, 21, n.eyebrow, 13, accent, True, "left")
        title_lines = wrap(n.title, n.w - 44, 23)
        body_lines = wrap(n.body, n.w - 44, 18)
        y = n.y + 43
        for i, line in enumerate(title_lines):
            yield ("text", n.id + f"-title-{i}", n.x + 22, y, n.w - 44,
                   29, line, 23, INK, True, "left")
            y += 29
        y += 5
        for i, line in enumerate(body_lines):
            yield ("text", n.id + f"-body-{i}", n.x + 22, y, n.w - 44,
                   24, line, 18, MUTED, False, "left")
            y += 24

    def label_shapes(self):
        for i, e in enumerate(self.links):
            if e.label and e.label_at:
                x, y = e.label_at
                width = len(e.label) * 8.8 + 20
                yield ("rect", f"el-bg-{i}", x - width/2, y - 13,
                       width, 26, "#FFFFFF", "#FFFFFF", 0, 4)
                yield ("text", f"el-text-{i}", x - width/2, y - 13,
                       width, 26, e.label, 15, e.color, False, "center")
        for i, (x, y, w, text, size, color, bold) in enumerate(self.notes):
            for j, line in enumerate(text.split("\n")):
                yield ("text", f"note-{i}-{j}", x, y + j*(size+8), w,
                       size + 8, line, size, color, bold, "left")

    def xml(self):
        model = ET.Element("mxGraphModel", dx=str(self.width), dy=str(self.height),
                           grid="1", gridSize="10", guides="1", tooltips="1",
                           connect="1", arrows="1", fold="1", page="1",
                           pageScale="1", pageWidth=str(self.width),
                           pageHeight=str(self.height), math="0", shadow="0")
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")

        def primitive(p, parent="1", origin=(0, 0)):
            kind, id, x, y, w, h, *rest = p
            x, y = x - origin[0], y - origin[1]
            if kind == "text":
                value, size, color, bold, align = rest
                style = (f"text;html=0;strokeColor=none;fillColor=none;align={align};"
                         f"verticalAlign=middle;whiteSpace=wrap;rounded=0;spacing=0;"
                         f"fontFamily={FONT};fontSize={size};fontColor={color};"
                         f"fontStyle={1 if bold else 0};")
            else:
                fill, stroke, weight, radius = rest
                value = ""
                shape = "rhombus" if kind == "diamond" else "rectangle"
                style = (f"shape={shape};rounded={1 if radius else 0};"
                         f"absoluteArcSize=1;arcSize={radius * 2};"
                         f"fillColor={fill};strokeColor={stroke};strokeWidth={weight};")
            cell = ET.SubElement(root, "mxCell", id=id, value=value, style=style,
                                 vertex="1", parent=parent)
            ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w),
                          height=str(h), attrib={"as": "geometry"})

        for p in self.shapes():
            primitive(p)
        for i, e in enumerate(self.links):
            source, target = self.cards[e.source], self.cards[e.target]
            a, b = source.anchor(e.start), target.anchor(e.end)
            ex, ey = (a[0]-source.x)/source.w, (a[1]-source.y)/source.h
            ix, iy = (b[0]-target.x)/target.w, (b[1]-target.y)/target.h
            style = ("edgeStyle=none;html=0;rounded=0;endArrow=block;endFill=1;"
                     f"strokeWidth=2;strokeColor={e.color};"
                     f"dashed={1 if e.dashed else 0};"
                     f"startArrow={'block' if e.both else 'none'};startFill=1;"
                     f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
                     f"entryX={ix};entryY={iy};entryDx=0;entryDy=0;")
            cell = ET.SubElement(root, "mxCell", id=f"edge-{i}", value="",
                                 style=style, edge="1", parent="1",
                                 source=e.source, target=e.target)
            geo = ET.SubElement(cell, "mxGeometry", relative="1",
                                attrib={"as": "geometry"})
            if e.via:
                points = ET.SubElement(geo, "Array", attrib={"as": "points"})
                for x, y in e.via:
                    ET.SubElement(points, "mxPoint", x=str(x), y=str(y))
        for n in self.cards.values():
            group = ET.SubElement(root, "mxCell", id=n.id, value="",
                                  style="group;", vertex="1", connectable="1", parent="1")
            ET.SubElement(group, "mxGeometry", x=str(n.x), y=str(n.y),
                          width=str(n.w), height=str(n.h), attrib={"as": "geometry"})
            for p in self.node_shapes(n):
                primitive(p, parent=n.id, origin=(n.x, n.y))
        for p in self.label_shapes():
            primitive(p)
        return model

    def svg(self):
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}" '
            'role="img" aria-labelledby="diagram-title diagram-description">',
            f'<title id="diagram-title">{esc(self.title)}</title>',
            f'<desc id="diagram-description">{esc(self.subtitle)}</desc>',
            '<defs>',
        ]
        colors = sorted({e.color for e in self.links})
        for c in colors:
            parts.append(f'<marker id="arrow-{c[1:]}" viewBox="0 0 10 10" '
                         'refX="9" refY="5" markerWidth="8" markerHeight="8" '
                         f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
        parts.append('</defs>')

        def primitive(p):
            kind, id, x, y, w, h, *rest = p
            if kind == "text":
                value, size, color, bold, align = rest
                tx = x+w/2 if align == "center" else x
                anchor = "middle" if align == "center" else "start"
                parts.append(f'<text id="{esc(id)}" x="{tx}" y="{y+h/2}" '
                             f'font-family="Segoe UI, Arial, sans-serif" font-size="{size}" '
                             f'font-weight="{700 if bold else 400}" fill="{color}" '
                             f'text-anchor="{anchor}" dominant-baseline="central">{esc(value)}</text>')
            else:
                fill, stroke, weight, radius = rest
                if kind == "diamond":
                    points = f"{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}"
                    parts.append(f'<polygon id="{id}" points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{weight}"/>')
                else:
                    parts.append(f'<rect id="{id}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{weight}"/>')
        for p in self.shapes():
            primitive(p)
        for i, e in enumerate(self.links):
            points = [self.cards[e.source].anchor(e.start), *e.via,
                      self.cards[e.target].anchor(e.end)]
            path = " ".join(f"{'M' if j == 0 else 'L'} {x} {y}" for j, (x,y) in enumerate(points))
            dash = ' stroke-dasharray="7 5"' if e.dashed else ""
            start = f' marker-start="url(#arrow-{e.color[1:]})"' if e.both else ""
            parts.append(f'<path id="edge-{i}" d="{path}" fill="none" stroke="{e.color}" stroke-width="2" '
                         f'marker-end="url(#arrow-{e.color[1:]})"{start}{dash}/>')
        for n in self.cards.values():
            for p in self.node_shapes(n):
                primitive(p)
        for p in self.label_shapes():
            primitive(p)
        parts.append("</svg>")
        return "\n".join(parts)


def overview():
    d = Diagram("01-tong-quan", "01 - Tổng quan", 1920, 1130,
                "Kiến trúc tổng quan",
                "Bản báo cáo mentor • Phạm vi: hỏi đáp và hướng dẫn thủ tục hành chính công • Định hướng đề xuất v0.2")
    d.section(40, 172, 1840, 538, "A  /  PHỤC VỤ NGƯỜI DÙNG",
              "Backend điều phối; dữ liệu được lưu theo người dùng, cuộc hội thoại và hồ sơ thủ tục.")
    d.card("web", 75, 260, 330, 156, "Web / người dùng",
           "Chat · lịch sử · hồ sơ\nNguồn tham khảo · upload", "blue", "01 / GIAO DIỆN")
    d.card("api", 505, 260, 420, 156, "Backend / API",
           "Session + quyền conversation/case\nLưu message + outbox trước queue", "blue", "02 / TIẾP NHẬN & ĐỊNH DANH")
    d.card("queue", 1025, 260, 450, 156, "Queue + Conversation Worker",
           "Tuần tự trong mỗi conversation\nSong song giữa các conversation", "blue", "03 / ĐIỀU PHỐI TẢI")
    d.card("socket", 1555, 260, 280, 156, "Socket.IO",
           "Trạng thái tức thời\nGửi answer đã duyệt", "blue", "06 / REALTIME")
    d.card("memory", 75, 470, 420, 192, "PostgreSQL / bộ nhớ",
           "User · session · conversation · case\nMessages · facts · summary · audit\nLưu lâu dài; truy xuất đúng hồ sơ", "green", "DỮ LIỆU CÁ NHÂN & TRẠNG THÁI")
    d.card("orch", 695, 470, 560, 192, "Luồng xử lý nghiệp vụ",
           "Context Builder + Case Card Validator\nProcedure Engine + Answer Verifier\nHỏi thêm nếu thiếu; duyệt rồi mới gửi", "amber", "04 / CÁC MODULE TRONG BACKEND")
    d.card("qwen", 1455, 470, 380, 192, "Qwen lightweight",
           "Hiểu yêu cầu / trích Case Card\nDiễn giải / tóm tắt theo dữ liệu\nMột runtime dùng chung", "purple", "05 / LLM 1.7B–4B · Q4/Q5 SAU EVAL")
    d.section(40, 742, 1840, 260, "B  /  TRI THỨC & HUẤN LUYỆN",
              "Cập nhật thủ tục qua kho dữ liệu; phát hành model qua một pipeline offline riêng.")
    d.card("ingest", 75, 823, 485, 153, "Công ty / admin dữ liệu",
           "Import → chuẩn hóa → review → index\nKiểm thử → publish phiên bản", "slate", "NGUỒN THỦ TỤC CHÍNH THỨC")
    d.card("rag", 695, 823, 560, 153, "Procedure Store + RAG",
           "Thủ tục có phiên bản + điều kiện + nguồn\nTìm đúng đối tượng, nơi và thời điểm", "green", "KHO TRI THỨC NGHIỆP VỤ")
    d.card("train", 1390, 823, 445, 153, "Fine-tune → nén → đánh giá",
           "Dữ liệu được phép + gold/SFT\nĐạt quality gate → phát hành model", "purple", "OFFLINE / TÀI NGUYÊN CÔNG TY")
    d.link("web", "api", label="HTTPS", label_at=(455, 325))
    d.link("api", "queue", label="Sau commit", label_at=(975, 325))
    d.link("queue", "orch", start="B", end=("T", .65),
           via=[(1250, 442), (1059, 442)])
    d.link("orch", "qwen", label="Gọi model / kết quả", label_at=(1355, 544),
           color="#7143AD", both=True)
    d.link("orch", "memory", start="L", end="R", label="Đọc / ghi đúng case",
           label_at=(595, 548), color="#147D66", dashed=True, both=True)
    d.link("api", "memory", start=("B", .2), end=("T", .85),
           via=[(589, 444), (432, 444)], color="#147D66", dashed=True)
    d.link("rag", "orch", start="T", end="B", label="Schema + evidence",
           label_at=(975, 720), color="#147D66", both=True)
    d.link("orch", "socket", start=("R", .15), end=("B", .3),
           via=[(1340, 499), (1340, 445), (1639, 445)],
           label="Đã kiểm tra + đã lưu", label_at=(1505, 445))
    d.link("socket", "web", start="T", end="T",
           via=[(1695, 240), (240, 240)],
           label="Cập nhật trạng thái / trả kết quả", label_at=(967, 240))
    d.link("ingest", "rag", label="Publish", label_at=(627, 878),
           color="#147D66", dashed=True)
    d.link("train", "qwen", start=("T", .6), end="B",
           via=[(1657, 715), (1645, 715)], label="Model version",
           label_at=(1720, 715), color="#7143AD", dashed=True)
    d.note(65, 1020, 1800,
           "Màu: xanh dương = hệ thống/API    •    xanh lá = dữ liệu/RAG    •    tím = model    •    vàng = kiểm tra & quy tắc", 18)
    d.note(65, 1054, 1800,
           "MVP: Docker Compose + cấu hình môi trường + theo dõi chất lượng. Các khối logic có thể dùng chung một backend/worker.", 18)
    d.note(65, 1086, 1800,
           "LLM là một thành phần của sản phẩm; lịch sử và ngữ cảnh được backend lưu, kiểm tra và nạp lại khi người dùng quay về.", 18, INK, True)
    return d


def detailed():
    d = Diagram("02-chi-tiet", "02 - Chi tiết", 2680, 2220,
                "Kiến trúc chi tiết & luồng một tin nhắn",
                "Đọc theo số 01 → 14 • Hai hàng đầu đi theo đường zíc zắc • D1–D4 / M1 là tài nguyên dùng chung • Đề xuất v0.2")
    d.section(40, 170, 2600, 1060, "A  /  RUNTIME — TỪ CÂU HỎI ĐẾN CÂU TRẢ LỜI",
              "Các ô là module logic. API/worker gọi cùng Qwen; PostgreSQL giữ trạng thái; draft chưa kiểm tra nằm nội bộ.")
    d.card("web", 85, 270, 280, 181, "Web / Frontend",
           "Prompt + cookie/session\nConversation đang chọn\nLịch sử · case · nguồn", "blue", "01 / NGƯỜI DÙNG")
    d.card("api", 435, 270, 340, 181, "API + Session",
           "Xác thực + ownership\nTạo message_id / turn_seq\ncase_id có thể chưa có", "blue", "02 / BACKEND · D1")
    d.card("outbox", 845, 270, 310, 181, "Message + outbox",
           "Ghi cùng transaction\nCommit → publish job\nChống trùng request", "green", "03 / LƯU TRƯỚC QUEUE · D1")
    d.card("queue", 1225, 270, 350, 181, "Redis + Worker",
           "Thứ tự conversation\nRetry / idempotency\nKhóa hoặc version case", "blue", "04 / XỬ LÝ BẤT ĐỒNG BỘ")
    d.card("context", 1645, 270, 380, 181, "Context Builder",
           "Facts + summary + recent\nĐúng user/case/turn_seq\nGiới hạn token đầu vào", "blue", "05 / BACKEND · ĐỌC D1")
    d.card("extract", 2100, 270, 420, 181, "Qwen: hiểu yêu cầu",
           "Đề xuất ý định / thủ tục\nCase Card + Memory Delta\nField chưa biết → unknown", "purple", "06 / GỌI M1 LẦN 1")
    d.card("validate", 2100, 535, 420, 181, "Case Card Validator",
           "Schema + nguồn fact + mâu thuẫn\nBackend chọn/tạo case có quyền\nDữ kiện hợp lệ mới được ghi D1", "amber", "07 / KIỂM TRA ĐỀ XUẤT")
    d.card("lookup", 1645, 535, 380, 181, "Tra thủ tục sơ bộ",
           "Tìm ứng viên / procedure schema\nLấy required_facts + điều kiện\nĐủ cho câu hỏi đang được hỏi?", "green", "08 / ĐỌC D2 · QUA TOOL/MCP")
    d.card("enough", 1320, 557, 235, 136, "Đủ dữ kiện\nquyết định?", tone="amber", diamond=True)
    d.card("rag", 845, 523, 395, 224, "RAG + Evidence Bundle",
           "Exact + BM25 + BGE-M3 dense\nFusion → BGE reranker\nLọc đối tượng / nơi / thời điểm\nGói thủ tục + version + nguồn\nThiếu nguồn → phản hồi theo mẫu", "green", "09 / FULL RETRIEVAL · D2, D3, D4")
    d.card("engine", 435, 535, 340, 224, "Procedure Engine",
           "Checklist theo điều kiện\nXét giấy tờ thay thế\nTrạng thái + bước kế tiếp\nCó giấy ≠ đã được xác minh", "amber", "10 / RULES TRONG BACKEND")
    d.card("generate", 85, 535, 280, 224, "Qwen: diễn giải",
           "Case + state + evidence\nDraft + claims có nguồn\nNguồn user / nguồn thủ tục\nChưa gửi draft ra web", "purple", "11 / GỌI M1 LẦN 2")
    d.card("ask", 1940, 765, 580, 131, "Hỏi thêm / xác nhận dữ kiện",
           "Mẫu hỏi backend đã duyệt; lưu rồi chờ user.", "amber", "TỪ REQUIRED_FACTS / THIẾU, MÂU THUẪN DỮ KIỆN")
    d.card("verify", 85, 945, 470, 227, "Answer Verifier + kiểm nội dung",
           "Schema · citation · giá trị · điều kiện\nĐối chiếu evidence và cả text hiển thị\nNội dung trọng yếu render từ cấu trúc\nLỗi → viết lại tối đa 1 lần, rồi kiểm lại", "amber", "12 / BACKEND · SEMANTIC CHECK LÀ BỔ SUNG")
    d.card("pass", 625, 988, 180, 130, "Đạt kiểm\ntra?", tone="amber", diamond=True)
    d.card("commit", 875, 970, 425, 177, "Commit kết quả",
           "Answer + audit + memory đã duyệt\ncase_version → ghi D1 → ACK job\nTạo event sau khi commit", "green", "13 / NGUỒN LƯU TRỮ LÂU DÀI")
    d.card("socket", 1450, 970, 430, 177, "Socket.IO Gateway",
           "Room theo quyền conversation\nStatus sớm; answer sau kiểm tra\nReconnect → history API / D1", "blue", "14 / REALTIME VỀ CÙNG WEB")
    d.card("safe", 1940, 970, 580, 177, "Phản hồi theo mẫu / hỗ trợ",
           "Thiếu nguồn phù hợp hoặc không đạt sau sửa\nHỏi lại / báo chưa đủ căn cứ / chuyển hỗ trợ\nMẫu backend đã duyệt → lưu ở bước 13", "amber", "NHÁNH KHÔNG ĐẠT — KHÔNG GỬI DRAFT")
    # The first row reads left to right.
    for a, b in [("web","api"),("api","outbox"),("outbox","queue"),
                 ("queue","context"),("context","extract")]:
        d.link(a,b)
    d.link("extract","validate",start="B",end="T")
    d.link("validate","lookup",start="L",end="R",
           label="Đề xuất hợp lệ",label_at=(2063,505),color="#A86A12")
    d.link("lookup","enough",start="L",end="R")
    d.link("enough","rag",start="L",end="R",via=[(1280,625),(1280,635)],
           label="Đủ",label_at=(1278,605),color="#147D66")
    d.link("rag","engine",start="L",end="R")
    d.link("engine","generate",start="L",end="R")
    d.link("generate","verify",start="B",end=("T",.3),
           via=[(225,840),(226,840)],label="Draft + claims",label_at=(285,865))
    d.link("verify","pass",start="R",end="L")
    d.link("pass","commit",start="R",end="L",label="PASS",label_at=(839,1029),color="#147D66")
    d.link("commit","socket",label="Sau commit",label_at=(1375,1027))
    d.link("socket","web",start=("T",.8),end="T",
           via=[(1794,924),(2600,924),(2600,243),(225,243)],
           label="Status tức thời + answer đã duyệt",label_at=(1530,243),color="#2455A4")
    d.link("enough","ask",start="B",end="L",
           via=[(1437.5,831)],label="Thiếu → hỏi lại",label_at=(1710,801),color="#A86A12")
    d.link("validate","ask",start="B",end=("T",.7),
           via=[(2310,739),(2346,739)],color="#A86A12")
    d.link("ask","commit",start="B",end=("T",.65),
           via=[(2230,915),(1151.25,915)],label="Lưu câu hỏi + facts hợp lệ",
           label_at=(1435,915),color="#A86A12",dashed=True)
    d.link("pass","safe",start="B",end=("B",.6),
           via=[(715,1195),(2288,1195)],label="FAIL sau lần sửa",label_at=(1575,1195),color="#A86A12")
    d.link("safe","commit",start=("T",.8),end=("T",.85),
           via=[(2404,938),(1236.25,938)],color="#A86A12",dashed=True)
    d.section(40,1260,2600,275,"B  /  TÀI NGUYÊN DÙNG CHUNG — CÁC THAM CHIẾU D1–D4 / M1",
              "Các module ở trên dùng kho theo mã tương ứng; D1 và D2 có thể cùng PostgreSQL nhưng khác bảng/schema và quyền.")
    d.card("d1",85,1345,435,160,"PostgreSQL / app state",
           "User → case → conversation\nMessages · facts · summary · audit","green","D1 / API · CONTEXT · COMMIT")
    d.card("d2",565,1345,435,160,"Procedure Store",
           "Schema · rule · hồ sơ · bước · phí\nVersion · phạm vi · evidence_id","green","D2 / TRI THỨC CẤU TRÚC ĐÃ DUYỆT")
    d.card("d3",1045,1345,450,160,"Chỉ mục tìm kiếm",
           "Exact: D2 · BM25: lexical index\nDense: BGE-M3 / Qdrant · rerank","green","D3 / BGE-RERANKER-V2-M3")
    d.card("d4",1540,1345,450,160,"MinIO / file & snapshot",
           "Nguồn chính thức có snapshot\nUpload cá nhân tách user/case","green","D4 / PHÂN QUYỀN THEO LOẠI DỮ LIỆU")
    d.card("m1",2035,1345,485,160,"Một Qwen runtime dùng chung",
           "1.7B–4B · Q4/Q5 sau quality gate\nTrích xuất + diễn giải + summary","purple","M1 / LLM SERVER · GPU NỘI BỘ")
    d.section(40,1570,2600,250,"C  /  CẬP NHẬT TRI THỨC — ĐỘC LẬP VỚI LUỒNG TRẢ LỜI",
              "Chỉ bản dữ liệu đã kiểm thử và publish mới được runtime truy xuất. Upload cá nhân không tự thành nguồn thủ tục chính thức.")
    d.card("admin",85,1650,385,147,"Admin / nguồn công ty",
           "Import hoặc MCP đọc nguồn\nPhân quyền · metadata · nguồn","slate","NHẬP DỮ LIỆU CHÍNH THỨC")
    d.card("parse",530,1650,420,147,"Ingestion Worker",
           "Parse / OCR → procedure schema\nReview nội dung / rule / phiên bản","slate","REDIS INGESTION QUEUE")
    d.card("index",1010,1650,420,147,"Staging + kiểm thử",
           "Chunk/embed → lexical/vector index\nKiểm tra retrieval / regression","slate","CHƯA CHO RUNTIME ĐỌC")
    d.card("publish",1490,1650,430,147,"Publish version",
           "D2 + D3 + D4 cùng phiên bản\nRollback nếu kiểm tra không đạt","green","KÍCH HOẠT TRI THỨC")
    d.card("private",1990,1650,530,147,"Upload cá nhân / memory",
           "D4 riêng → facts đề xuất → Validator 07\nSummary job → validate → D1; có nguồn","blue","NHÁNH RIÊNG CỦA TỪNG USER / CASE")
    for a,b in [("admin","parse"),("parse","index"),("index","publish")]:
        d.link(a,b,color="#147D66",dashed=True)
    d.section(40,1850,2600,228,"D  /  HUẤN LUYỆN OFFLINE — TÀI NGUYÊN CÔNG TY",
              "Không train lại theo từng tin nhắn. Fine-tune hành vi; tri thức thủ tục được cập nhật qua nhánh C.")
    d.card("data",85,1925,515,130,"Dữ liệu được phép + gold/SFT",
           "Tách train / dev / test; giữ nguồn dữ liệu","purple","01 / CHUẨN BỊ")
    d.card("tune",680,1925,520,130,"Fine-tune + lượng tử hóa",
           "QLoRA/SFT → BF16 đối chứng → Q5/Q4","purple","02 / TÀI NGUYÊN HUẤN LUYỆN")
    d.card("eval",1280,1925,515,130,"Đánh giá từng tầng + E2E",
           "Case Card · RAG · verifier · VRAM · latency","purple","03 / QUALITY GATE")
    d.card("release",1875,1925,645,130,"Phát hành model version → M1",
           "Đạt ngưỡng chất lượng và nhẹ trên phần cứng triển khai","purple","04 / MODEL REGISTRY & ROLLBACK")
    for a,b in [("data","tune"),("tune","eval"),("eval","release")]:
        d.link(a,b,color="#7143AD",dashed=True)
    d.note(65,2105,2550,
           "TRIỂN KHAI  /  Docker Compose · Gateway HTTPS · API/Worker · DB/Redis/Qdrant/MinIO/model trong mạng nội bộ · .env.example không chứa secret",18,INK,True)
    d.note(65,2139,2550,
           "VẬN HÀNH  /  trace_id · queue lag · retry · thời gian phản hồi · VRAM/RAM · phiên bản model/index · audit nguồn · kiểm thử cách ly user/case",18)
    d.note(65,2173,2550,
           "CHÚ GIẢI  /  Đường liền: luồng online/gọi module. Nét đứt: nhánh phụ/offline. Verifier kiểm theo dữ liệu đã duyệt; không chứng minh đúng tuyệt đối.",18)
    return d


def save_mxfile(path, diagrams):
    root = ET.Element("mxfile", host="app.diagrams.net",
                      agent="Codex architecture generator", version="24.7.17",
                      type="device", compressed="false")
    for d in diagrams:
        page = ET.SubElement(root,"diagram",id=d.slug,name=d.name)
        page.append(d.xml())
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def main():
    diagrams = [overview(), detailed()]
    for d in diagrams:
        d.validate()
        save_mxfile(OUT / (d.slug + ".drawio"), [d])
        svg_path = OUT / (d.slug + ".svg")
        svg_path.write_text(d.svg(), encoding="utf-8")
        ET.parse(svg_path)
        print(f"{d.slug}: {len(d.cards)} cards, {len(d.links)} connections, {d.width}x{d.height}")
    save_mxfile(OUT / "kien-truc-hanh-chinh-cong.drawio", diagrams)
    for path in OUT.glob("*.drawio"):
        tree = ET.parse(path)
        for page in tree.getroot().findall("diagram"):
            cells = page.findall(".//mxCell")
            ids = [c.attrib["id"] for c in cells]
            assert len(ids) == len(set(ids)), path
            for c in cells:
                for key in ("source","target","parent"):
                    if key in c.attrib:
                        assert c.attrib[key] in ids, (path, c.attrib)
        print(f"Validated: {path.name}")


if __name__ == "__main__":
    main()
