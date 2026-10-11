#!/usr/bin/env python3
"""Generate the Chinese-first Workshop AI product case-study portfolio PDF."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "pdf" / "Workshop-AI-AI-Product-Case-Study-Zhan-Jin.pdf"
TMP = ROOT / "tmp" / "pdfs" / "workshop-ai-portfolio"
ASSETS = ROOT / "showcase" / "assets"

W, H = landscape(A4)
M = 46

BG = HexColor("#08121F")
PANEL = HexColor("#111F31")
PANEL_2 = HexColor("#17283D")
INK = HexColor("#F4F8FC")
MUTED = HexColor("#AFC0D3")
MINT = HexColor("#68D5B5")
MINT_SOFT = HexColor("#DDF8EF")
ORANGE = HexColor("#FFB35C")
RED = HexColor("#FF7F7F")
LINE = HexColor("#2B4058")
WHITE = HexColor("#FFFFFF")


def register_font() -> None:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("CJK", str(path)))
            return
    raise FileNotFoundError("No CJK-capable font found")


def wrap(text: str, width: float, size: float) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + ch
        if pdfmetrics.stringWidth(candidate, "CJK", size) <= width:
            current = candidate
        else:
            if ch in "。，；！？、：”’)]）】」』" and current:
                current += ch
                continue
            if current:
                lines.append(current)
            current = ch.lstrip()
    if current:
        lines.append(current)
    return lines


def draw_text(c: Canvas, text: str, x: float, y: float, width: float, size: float = 12,
              leading: float | None = None, color=INK, max_lines: int | None = None) -> float:
    leading = leading or size * 1.55
    lines = wrap(text, width, size)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while pdfmetrics.stringWidth(last + "…", "CJK", size) > width and last:
            last = last[:-1]
        lines[-1] = last + "…"
    c.setFont("CJK", size)
    c.setFillColor(color)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def label(c: Canvas, text: str, x: float, y: float, color=MINT) -> None:
    c.setFillColor(color)
    c.setFont("CJK", 8.5)
    c.drawString(x, y, text.upper())


def page_base(c: Canvas, page_no: int, section: str, source: str = "") -> None:
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.line(M, 34, W - M, 34)
    c.setFont("CJK", 8)
    c.setFillColor(MUTED)
    c.drawString(M, 20, f"WORKSHOP AI  |  {section}")
    if source:
        c.drawCentredString(W / 2, 20, source)
    c.drawRightString(W - M, 20, f"{page_no:02d} / 12")


def title(c: Canvas, kicker: str, headline: str, subtitle: str | None = None) -> float:
    label(c, kicker, M, H - 56)
    y = draw_text(c, headline, M, H - 84, W - 2 * M, 27, 35, INK, 2)
    if subtitle:
        y = draw_text(c, subtitle, M, y - 2, W - 2 * M, 11, 17, MUTED, 2)
    return y


def round_rect(c: Canvas, x: float, y: float, w: float, h: float, fill=PANEL, stroke=LINE, radius=12) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def card(c: Canvas, x: float, y: float, w: float, h: float, number: str, heading: str,
         body: str, accent=MINT, body_size=10.2) -> None:
    round_rect(c, x, y, w, h)
    c.setFillColor(accent)
    c.roundRect(x + 14, y + h - 35, 28, 22, 7, fill=1, stroke=0)
    c.setFillColor(BG)
    c.setFont("CJK", 9)
    c.drawCentredString(x + 28, y + h - 28, number)
    draw_text(c, heading, x + 52, y + h - 21, w - 66, 13, 18, INK, 2)
    draw_text(c, body, x + 16, y + h - 57, w - 32, body_size, body_size * 1.55, MUTED)


def draw_pill(c: Canvas, text: str, x: float, y: float, fill=MINT, ink=BG) -> float:
    w = pdfmetrics.stringWidth(text, "CJK", 8.5) + 22
    c.setFillColor(fill)
    c.roundRect(x, y - 3, w, 20, 10, fill=1, stroke=0)
    c.setFillColor(ink)
    c.setFont("CJK", 8.5)
    c.drawCentredString(x + w / 2, y + 3, text)
    return w


def image_contain(c: Canvas, path: Path, x: float, y: float, w: float, h: float,
                  border=True, pad=0) -> None:
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min((w - 2 * pad) / iw, (h - 2 * pad) / ih)
    dw, dh = iw * scale, ih * scale
    dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
    if border:
        round_rect(c, x, y, w, h, PANEL_2, LINE, 10)
    c.drawImage(ImageReader(str(path)), dx, dy, dw, dh, preserveAspectRatio=True, mask="auto")


def image_crop(c: Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    with Image.open(path) as im:
        iw, ih = im.size
        target = w / h
        current = iw / ih
        if current > target:
            nw = int(ih * target)
            left = (iw - nw) // 2
            crop = im.crop((left, 0, left + nw, ih))
        else:
            nh = int(iw / target)
            top = (ih - nh) // 2
            crop = im.crop((0, top, iw, top + nh))
        tmp = TMP / f"crop-{path.stem}-{int(w)}-{int(h)}.jpg"
        crop.convert("RGB").save(tmp, quality=92)
    c.saveState()
    p = c.beginPath()
    p.roundRect(x, y, w, h, 10)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(str(tmp), x, y, w, h, preserveAspectRatio=False)
    c.restoreState()
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 10, fill=0, stroke=1)


def image_region(c: Canvas, path: Path, region: tuple[int, int, int, int],
                 x: float, y: float, w: float, h: float) -> None:
    with Image.open(path) as im:
        crop = im.crop(region)
        tmp = TMP / f"region-{path.stem}.jpg"
        crop.convert("RGB").save(tmp, quality=94)
    c.saveState()
    p = c.beginPath()
    p.roundRect(x, y, w, h, 10)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(str(tmp), x, y, w, h, preserveAspectRatio=False)
    c.restoreState()
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 10, fill=0, stroke=1)


def prepare_diagrams() -> dict[str, Path]:
    TMP.mkdir(parents=True, exist_ok=True)
    converter = shutil.which("rsvg-convert") or "/opt/anaconda3/bin/rsvg-convert"
    names = ["ai-confirmation-flow", "local-full-stack", "public-demo-stack"]
    result: dict[str, Path] = {}
    for name in names:
        src = ASSETS / "diagrams" / f"{name}.svg"
        dst = TMP / f"{name}.png"
        subprocess.run([converter, "-w", "960", "-o", str(dst), str(src)], check=True)
        result[name] = dst
    return result


def p1_cover(c: Canvas) -> None:
    page_base(c, 1, "AI PRODUCT CASE STUDY")
    c.setFillColor(MINT)
    c.circle(W - 98, H - 84, 11, fill=1, stroke=0)
    c.setFillColor(ORANGE)
    c.circle(W - 71, H - 84, 5, fill=1, stroke=0)
    label(c, "AI 产品经理作品集 · 个人求职展示版", M, H - 96)
    draw_text(c, "Workshop AI", M, H - 146, 510, 43, 50, INK, 1)
    draw_text(c, "从服务发现、智能决策到预约履约的本地服务 Marketplace", M, H - 198, 650, 21, 31, INK, 2)
    draw_text(c, "不是给交易套一层聊天框，而是让 AI 在正确的时刻读信息、给建议，并把最终决定留给用户。", M, H - 274, 615, 13, 21, MUTED, 3)
    x = M
    for text_, fill in [("Tool Calling", MINT), ("确认后变更", ORANGE), ("决策支持", MINT), ("可复现验证", MINT)]:
        x += draw_pill(c, text_, x, 196, fill) + 9
    c.setFillColor(PANEL)
    c.roundRect(M, 76, W - 2 * M, 82, 14, fill=1, stroke=0)
    draw_text(c, "案例整理与展示版维护：Zhan Jin", M + 20, 133, 390, 11, 16, INK, 1)
    draw_text(c, "角色范围：产品叙事、基线修复、演示安全边界与发布准备。原始课程项目为团队成果。", M + 20, 107, 700, 9.5, 15, MUTED, 2)


def p2_overview(c: Canvas) -> None:
    page_base(c, 2, "EXECUTIVE OVERVIEW", "内容依据：当前 Case Study 与仓库说明")
    title(c, "01 / 一页速览", "让复杂服务交易更容易理解、比较和推进", "招聘者先看产品判断，再看证据覆盖到哪里。")
    card(c, M, 288, 233, 178, "01", "问题", "搜索只是起点。用户还要判断服务区域、资质、评价和价格，并把意向转成可追踪的预约。")
    card(c, M + 249, 288, 233, 178, "02", "产品主张", "把发现、比较、预约、报价、支付、履约和评价串成一条有状态的交易闭环。")
    card(c, M + 498, 288, 251, 178, "03", "AI 原则", "AI 负责理解、整理与建议。凡是改变业务状态的动作，先生成确认卡，再由用户执行。", ORANGE)
    round_rect(c, M, 72, W - 2 * M, 188)
    label(c, "CASE MAP", M + 20, 233)
    items = [
        ("用户", "Customer / Provider / Admin"),
        ("体验", "搜索筛选 / 收藏 / 预约 / 报价 / 模拟支付 / 履约 / 评价"),
        ("AI", "Tool Calling / 推荐卡 / 评价总结 / 确认卡 / 可理解降级"),
        ("证据", "401 项后端测试通过；本地验证不等于上线或运营效果"),
    ]
    y = 204
    for k, v in items:
        c.setFillColor(MINT)
        c.circle(M + 27, y + 3, 3.2, fill=1, stroke=0)
        draw_text(c, k, M + 42, y + 8, 80, 10, 15, INK, 1)
        draw_text(c, v, M + 122, y + 8, W - 2 * M - 150, 10, 15, MUTED, 2)
        y -= 36


def p3_problem(c: Canvas) -> None:
    page_base(c, 3, "PROBLEM & USERS", "内容依据：Case Study / Problem & Journey")
    title(c, "02 / 问题与用户", "用户不是在买“搜索结果”，而是在降低一次交易的不确定性")
    c.setFillColor(PANEL)
    c.roundRect(M, 96, 284, 370, 14, fill=1, stroke=0)
    label(c, "USER TENSION", M + 20, 438)
    tensions = [
        ("发现成本", "按服务类别与位置缩小范围，结果需要对应真实服务区域。"),
        ("信任判断", "资质、评价和服务信息必须可核对；AI 总结不能替代原始信息。"),
        ("交易连续性", "跨页面推进时，用户需要知道当前状态、下一步和异常出口。"),
    ]
    y = 394
    for i, (h, b) in enumerate(tensions, 1):
        c.setFillColor(MINT if i < 3 else ORANGE)
        c.circle(M + 31, y + 4, 13, fill=1, stroke=0)
        c.setFillColor(BG)
        c.setFont("CJK", 9)
        c.drawCentredString(M + 31, y + 1, str(i))
        draw_text(c, h, M + 55, y + 10, 190, 13, 18, INK, 1)
        draw_text(c, b, M + 55, y - 16, 190, 9.5, 15, MUTED, 3)
        y -= 105
    x = M + 310
    round_rect(c, x, 96, W - M - x, 370)
    label(c, "TWO-SIDED JOURNEY", x + 20, 438)
    draw_text(c, "Customer", x + 20, 404, 160, 18, 24, MINT, 1)
    draw_text(c, "找到可信候选 → 描述需求 → 判断报价 → 确认履约 → 留下评价", x + 20, 372, 195, 11, 18, INK, 5)
    draw_text(c, "Provider", x + 252, 404, 160, 18, 24, ORANGE, 1)
    draw_text(c, "呈现服务能力 → 回应需求 → 提交报价 → 完成服务 → 处理异常", x + 252, 372, 195, 11, 18, INK, 5)
    c.setStrokeColor(LINE)
    c.line(x + 229, 182, x + 229, 408)
    draw_text(c, "共同需要：清晰状态、证据可核对、关键动作可撤回或进入争议流程。", x + 20, 141, 430, 12, 19, MUTED, 3)


def p4_journey(c: Canvas) -> None:
    page_base(c, 4, "PRODUCT JOURNEY", "内容依据：Case Study / Journey；支付为模拟演示")
    title(c, "03 / 核心旅程", "八步交易闭环：每一步都有状态，也有明确的下一步")
    steps = [
        ("发现", "位置 + 类别"), ("比较", "范围 + 资质 + 评价"),
        ("收藏", "保存候选"), ("预约", "描述需求"),
        ("报价", "参考历史范围"), ("支付", "模拟推进状态"),
        ("履约", "确认 / 退款 / 投诉"), ("评价", "沉淀上下文"),
    ]
    gap = 12
    cw = (W - 2 * M - gap * 3) / 4
    ch = 148
    for i, (h, b) in enumerate(steps):
        row, col = divmod(i, 4)
        x = M + col * (cw + gap)
        y = 286 if row == 0 else 112
        accent = ORANGE if h in {"支付", "履约"} else MINT
        card(c, x, y, cw, ch, f"{i + 1:02d}", h, b, accent, 10.5)
        if col < 3:
            c.setStrokeColor(LINE)
            c.setLineWidth(1.4)
            c.line(x + cw + 2, y + ch / 2, x + cw + gap - 2, y + ch / 2)
    draw_text(c, "状态不是后台细节，而是用户理解交易进度的产品语言。", M, 84, W - 2 * M, 12, 18, MUTED, 2)


def p5_ai(c: Canvas) -> None:
    page_base(c, 5, "AI & TOOL CALLING", "内容依据：Case Study / AI Layer")
    title(c, "04 / AI 介入点", "AI 先理解意图，再调用业务工具；模型回答不等于交易结果")
    left = M
    right = 478
    round_rect(c, left, 108, 392, 346)
    label(c, "AI CAPABILITY LAYER", left + 20, 425)
    caps = [
        ("01", "需求与推荐", "整理用户描述，调用检索工具并呈现服务商推荐卡。"),
        ("02", "评价总结", "使用数据库评价上下文；保留原始评价与信息不足说明。"),
        ("03", "确认卡", "预约、取消、支付与退款先展示待执行内容。"),
        ("04", "可理解降级", "额度、超时或模型不可用时解释原因，普通流程继续。"),
    ]
    y = 382
    for n, h, b in caps:
        c.setFillColor(MINT if n != "03" else ORANGE)
        c.setFont("CJK", 9)
        c.drawString(left + 20, y + 4, n)
        draw_text(c, h, left + 55, y + 10, 105, 12.5, 17, INK, 1)
        draw_text(c, b, left + 158, y + 10, 210, 9.0, 14.5, MUTED, 3)
        y -= 76
    round_rect(c, right, 108, W - M - right, 346, PANEL_2)
    label(c, "TOOL CALLING CONTRACT", right + 20, 425, ORANGE)
    flow = ["用户自然语言", "意图 + 当前上下文", "业务工具读取 / 草稿", "确认或直接展示", "业务状态回执"]
    y = 378
    for i, item in enumerate(flow):
        c.setFillColor(PANEL if i not in {3, 4} else Color(0.1, 0.25, 0.25))
        c.setStrokeColor(ORANGE if i == 3 else LINE)
        c.roundRect(right + 26, y, 258, 42, 9, fill=1, stroke=1)
        draw_text(c, item, right + 40, y + 27, 230, 10.5, 15, INK, 1)
        if i < len(flow) - 1:
            c.setStrokeColor(MINT)
            c.line(right + 155, y, right + 155, y - 20)
        y -= 63
    draw_text(c, "公开演示不声称使用向量 RAG：评价总结使用 PostgreSQL 数据库上下文。", M, 78, W - 2 * M, 9.5, 15, MUTED, 2)


def p6_confirmation(c: Canvas, diagram: Path) -> None:
    page_base(c, 6, "CONFIRMATION BEFORE MUTATION", "图：ai-confirmation-flow.svg")
    title(c, "05 / 关键机制", "先确认、再变更：把 AI 的“建议权”和用户的“决定权”拆开")
    image_contain(c, diagram, M, 80, 304, 402, False)
    x = 383
    card(c, x, 332, 412, 150, "A", "读取与建议", "搜索、评价与状态读取可以直接展示。结果必须保留来源上下文和不足说明。", MINT)
    card(c, x, 164, 412, 150, "B", "业务变更", "预约、取消、支付或退款先生成操作草稿和确认卡。用户未确认时，不改变状态。", ORANGE)
    draw_text(c, "产品结果：减少误触与“模型说成功但系统未变更”的错觉。", x + 8, 128, 400, 11.5, 18, INK, 2)
    draw_text(c, "失败或待核对状态必须明确展示，不能用自然语言掩盖。", x + 8, 88, 400, 9.5, 15, MUTED, 2)


def p7_decision(c: Canvas) -> None:
    page_base(c, 7, "DECISION SUPPORT", "产品截图：showcase/assets/product/provider-search-*.png")
    title(c, "06 / 决策支持", "把比较依据放在做决定的地方，而不是藏在另一页")
    image_crop(c, ASSETS / "product" / "provider-search-filters-expanded.png", M, 238, 450, 232)
    image_crop(c, ASSETS / "product" / "provider-search-results.png", M + 466, 238, 285, 232)
    mechanisms = [
        ("搜索筛选", "类别、距离、价格、评分和营业状态；支持距离、价格或评分排序。"),
        ("位置级联", "省、市、区逐级选择；上级变化时清除不匹配的下级条件。"),
        ("收藏与比较", "保存意向，回到候选服务商信息和评价继续核对。"),
        ("历史报价参考", "同类别其他预约取最新报价，用均值和固定规则形成范围；不是价格预测。"),
    ]
    gap = 12
    cw = (W - 2 * M - gap * 3) / 4
    for i, (h, b) in enumerate(mechanisms):
        card(c, M + i * (cw + gap), 74, cw, 140, f"{i + 1:02d}", h, b, ORANGE if i == 3 else MINT, 9.2)


def p8_local(c: Canvas, diagram: Path) -> None:
    page_base(c, 8, "LOCAL FULL STACK", "图：local-full-stack.svg")
    title(c, "07 / 完整本地模式", "保留向量检索与后台任务，用于开发和深入演示")
    image_contain(c, diagram, M, 75, 312, 406, False)
    x = 386
    round_rect(c, x, 75, W - M - x, 406)
    label(c, "WHAT IT ENABLES", x + 22, 448)
    draw_text(c, "业务主链", x + 22, 413, 130, 15, 21, MINT, 1)
    draw_text(c, "Expo Web / Mobile → FastAPI → PostgreSQL", x + 22, 385, 360, 10.5, 17, INK, 2)
    draw_text(c, "缓存与任务", x + 22, 337, 130, 15, 21, MINT, 1)
    draw_text(c, "Redis 支持缓存与任务；Celery 处理后台任务。", x + 22, 309, 360, 10.5, 17, INK, 2)
    draw_text(c, "检索依赖", x + 22, 261, 130, 15, 21, ORANGE, 1)
    draw_text(c, "Milvus + etcd + MinIO；TEI / Qwen3 Embedding 提供嵌入服务。", x + 22, 233, 360, 10.5, 17, INK, 3)
    draw_text(c, "边界", x + 22, 164, 130, 15, 21, RED, 1)
    draw_text(c, "这是配置与源码保留的完整模式。运行依赖本地模型、数据库和容器服务配置。", x + 22, 136, 368, 9.6, 15.5, MUTED, 3)


def p9_public(c: Canvas, diagram: Path) -> None:
    page_base(c, 9, "PUBLIC DEMO ARCHITECTURE", "图：public-demo-stack.svg")
    title(c, "08 / 轻量公开模式", "减少常驻依赖，但不把“已验证”写成“已上线”")
    image_contain(c, diagram, M, 75, 305, 405, False)
    x = 379
    card(c, x, 333, 416, 147, "01", "评价总结", "PostgreSQL 数据库评价上下文 → 服务端 LLM API → 总结；保留信息不足与模型不可用说明。", MINT, 8.8)
    card(c, x, 169, 416, 147, "02", "模拟交易", "Demo Payment Adapter 推进演示订单状态，不产生真实扣款；公开部署和浏览器路径仍待验收。", ORANGE, 8.8)
    round_rect(c, x, 75, 416, 76, PANEL_2)
    draw_text(c, "本地验证 ≠ 托管 CI ≠ 线上部署 ≠ 真实运营结果", x + 20, 124, 376, 12, 18, INK, 2)
    draw_text(c, "四层证据必须分别陈述。", x + 20, 90, 376, 9.5, 15, MUTED, 1)


def p10_product(c: Canvas) -> None:
    page_base(c, 10, "PRODUCT EVIDENCE", "截图为历史产品证据；不等于当前浏览器端到端验收")
    title(c, "09 / 产品证据", "真实界面展示了信息层级、筛选条件与候选结果")
    image_contain(c, ASSETS / "product" / "provider-search-filters-expanded.png", M, 175, 475, 298, True, 8)
    image_region(c, ASSETS / "product" / "provider-search-results.png", (300, 185, 850, 650), M + 492, 175, 259, 298)
    round_rect(c, M, 75, W - 2 * M, 78, PANEL_2)
    draw_text(c, "看得到的产品判断", M + 18, 126, 180, 12, 18, MINT, 1)
    draw_text(c, "筛选控件围绕真实决策变量组织；结果卡保留营业状态、服务类别与距离。截图用于说明产品形态，不推导转化率、活跃用户或运营影响。", M + 190, 126, W - 2 * M - 210, 9.8, 15, MUTED, 3)


def p11_evidence(c: Canvas) -> None:
    page_base(c, 11, "VERIFICATION EVIDENCE", "证据：docs/release/foundation-verification.md · 2026-10-10")
    title(c, "10 / 验证证据", "用可复现记录说明“什么被验证了”，也说明“什么没有”")
    metrics = [
        ("401", "后端测试", "PostgreSQL 应用数据 + 真实迁移契约；无失败或跳过"),
        ("138", "聚焦回归", "支付、发布策略与 PostgreSQL 迁移/API 套件"),
        ("54", "发布策略", "独立 publication-policy 测试通过"),
        ("58", "历史前端基线", "对应早期基线；不能代表当前发布验收"),
    ]
    gap = 12
    cw = (W - 2 * M - gap * 3) / 4
    for i, (n, h, b) in enumerate(metrics):
        x = M + i * (cw + gap)
        round_rect(c, x, 290, cw, 168, PANEL if i != 3 else PANEL_2)
        draw_text(c, n, x + 16, 423, cw - 32, 32, 38, ORANGE if i in {1, 3} else MINT, 1)
        draw_text(c, h, x + 16, 377, cw - 32, 12, 18, INK, 2)
        draw_text(c, b, x + 16, 340, cw - 32, 9.2, 14.5, MUTED, 4)
    round_rect(c, M, 78, W - 2 * M, 190)
    label(c, "EVIDENCE LADDER", M + 20, 239)
    rows = [
        ("已验证", "本地测试、迁移往返、规则与扫描、部分构建记录"),
        ("已配置", "后端、移动端、公开文案三个独立 CI 检查任务"),
        ("未声称", "托管 CI 已运行、公开部署可用、真实供应商可用、浏览器旅程已验收、运营指标"),
    ]
    y = 204
    for i, (k, v) in enumerate(rows):
        c.setFillColor([MINT, ORANGE, RED][i])
        c.circle(M + 29, y + 3, 4, fill=1, stroke=0)
        draw_text(c, k, M + 45, y + 9, 100, 11, 16, INK, 1)
        draw_text(c, v, M + 145, y + 9, W - 2 * M - 170, 9.6, 15, MUTED, 3)
        y -= 47


def p12_close(c: Canvas) -> None:
    page_base(c, 12, "LIMITS · NEXT · CREDITS", "案例基线：a803f34")
    title(c, "11 / 边界与下一步", "诚实地展示边界，本身就是产品判断的一部分")
    card(c, M, 290, 233, 168, "01", "支付与数据", "Demo 支付不会扣款；资料为虚构演示数据，不代表真实客户、服务商或交易。", RED)
    card(c, M + 249, 290, 233, 168, "02", "AI 与价格", "模型输出需核对；历史报价范围是统计参考，样本不足时不能给出可靠推断。", ORANGE)
    card(c, M + 498, 290, 251, 168, "03", "运行与发布", "本地检查不替代线上验收；外部服务与浏览器路径需要发布前再次验证。", RED)
    round_rect(c, M, 116, 456, 148)
    label(c, "NEXT STEPS", M + 20, 234)
    nexts = ["完成轻量部署与三角色浏览器冒烟", "制作带字幕的产品录屏并核对移动端可访问性", "验证推荐依据、确认卡理解与报价参考的决策质量"]
    y = 203
    for i, t in enumerate(nexts, 1):
        c.setFillColor(MINT)
        c.circle(M + 28, y + 3, 10, fill=1, stroke=0)
        c.setFillColor(BG)
        c.setFont("CJK", 8)
        c.drawCentredString(M + 28, y, str(i))
        draw_text(c, t, M + 48, y + 7, 390, 9.7, 15, INK, 2)
        y -= 35
    round_rect(c, M + 474, 116, 275, 148, PANEL_2)
    label(c, "CREDITS & CONTACT", M + 494, 234, ORANGE)
    draw_text(c, "案例整理与展示版维护：Zhan Jin", M + 494, 205, 235, 10.5, 16, INK, 2)
    draw_text(c, "电话：153 6612 3264", M + 494, 176, 235, 9.6, 14, ORANGE, 1)
    draw_text(c, "邮箱：jinzhan_2023@163.com", M + 494, 156, 235, 9.2, 14, ORANGE, 1)
    draw_text(c, "来源说明：原始课程项目为团队成果，并获共同授权用于个人求职展示；此处不主张独立完成原项目。", M + 494, 132, 235, 7.7, 11.5, MUTED, 4)
    draw_text(c, "THANK YOU", M, 82, W - 2 * M, 18, 24, MINT, 1)


def build() -> None:
    register_font()
    diagrams = prepare_diagrams()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(OUT), pagesize=(W, H), pageCompression=1)
    c.setTitle("Workshop AI | AI 产品经理案例作品集")
    c.setAuthor("Zhan Jin")
    c.setSubject("AI Product Manager portfolio case study")
    pages = [
        lambda: p1_cover(c), lambda: p2_overview(c), lambda: p3_problem(c),
        lambda: p4_journey(c), lambda: p5_ai(c),
        lambda: p6_confirmation(c, diagrams["ai-confirmation-flow"]),
        lambda: p7_decision(c), lambda: p8_local(c, diagrams["local-full-stack"]),
        lambda: p9_public(c, diagrams["public-demo-stack"]),
        lambda: p10_product(c), lambda: p11_evidence(c), lambda: p12_close(c),
    ]
    for page in pages:
        page()
        c.showPage()
    c.save()
    print(OUT)


if __name__ == "__main__":
    build()
