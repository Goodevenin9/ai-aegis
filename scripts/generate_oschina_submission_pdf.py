"""Generate the OSCHINA 2026 competition project-introduction PDF.

The document is intentionally generated from repository evidence and avoids
claiming planned enterprise capabilities as already delivered.
"""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "AI-Aegis-2026上海开源软件应用创新大赛-作品介绍.pdf"
LOGO = ROOT / "docs" / "brand" / "ai-aegis-logo-master.png"
TRACE_SCREENSHOT = ROOT / "docs" / "screenshots" / "agent-runs.png"

PAGE_W, PAGE_H = A4
MARGIN_X = 17 * mm
MARGIN_TOP = 18 * mm
MARGIN_BOTTOM = 16 * mm

NAVY = colors.HexColor("#07152E")
NAVY_2 = colors.HexColor("#0B2348")
BLUE = colors.HexColor("#0B6BFF")
CYAN = colors.HexColor("#13C8E8")
TEAL = colors.HexColor("#00B894")
PURPLE = colors.HexColor("#7048E8")
RED = colors.HexColor("#F05454")
ORANGE = colors.HexColor("#FF9F43")
INK = colors.HexColor("#152238")
MUTED = colors.HexColor("#5D6B82")
LIGHT = colors.HexColor("#F3F7FC")
BORDER = colors.HexColor("#DCE6F2")
WHITE = colors.white


def register_fonts() -> None:
    regular = Path(r"C:\Windows\Fonts\msyh.ttc")
    bold = Path(r"C:\Windows\Fonts\msyhbd.ttc")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("AegisCN", str(regular)))
        pdfmetrics.registerFont(TTFont("AegisCN-Bold", str(bold)))
    else:
        fallback = Path(r"C:\Windows\Fonts\simhei.ttf")
        pdfmetrics.registerFont(TTFont("AegisCN", str(fallback)))
        pdfmetrics.registerFont(TTFont("AegisCN-Bold", str(fallback)))


register_fonts()


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CNBody",
        fontName="AegisCN",
        fontSize=9.2,
        leading=15,
        textColor=INK,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="CNBodySmall",
        parent=styles["CNBody"],
        fontSize=7.5,
        leading=11.5,
        textColor=MUTED,
    )
)
styles.add(
    ParagraphStyle(
        name="CNTitle",
        fontName="AegisCN-Bold",
        fontSize=24,
        leading=32,
        textColor=NAVY,
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        name="CNSection",
        fontName="AegisCN-Bold",
        fontSize=15.5,
        leading=22,
        textColor=NAVY,
        spaceBefore=4,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="CNSub",
        fontName="AegisCN-Bold",
        fontSize=10.5,
        leading=15,
        textColor=NAVY_2,
        spaceBefore=4,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="CNTableHeader",
        fontName="AegisCN-Bold",
        fontSize=7.9,
        leading=11.5,
        textColor=WHITE,
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="CNWhite",
        fontName="AegisCN",
        fontSize=10,
        leading=16,
        textColor=WHITE,
    )
)
styles.add(
    ParagraphStyle(
        name="CNWhiteSmall",
        parent=styles["CNWhite"],
        fontSize=8,
        leading=12,
        textColor=colors.HexColor("#DCE9FF"),
    )
)
styles.add(
    ParagraphStyle(
        name="CNKicker",
        fontName="AegisCN-Bold",
        fontSize=8,
        leading=11,
        textColor=BLUE,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="CNCoverTitle",
        fontName="AegisCN-Bold",
        fontSize=26,
        leading=36,
        textColor=WHITE,
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="CNCoverSub",
        fontName="AegisCN",
        fontSize=12,
        leading=19,
        textColor=colors.HexColor("#DCE9FF"),
    )
)
styles.add(
    ParagraphStyle(
        name="CNTiny",
        fontName="AegisCN",
        fontSize=6.7,
        leading=9.5,
        textColor=MUTED,
    )
)


def P(text: str, style: str = "CNBody") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str, style: str = "CNBody") -> Paragraph:
    return Paragraph(f"<font color='#0B6BFF'>●</font>&nbsp;&nbsp;{text}", styles[style])


class SectionTitle(Flowable):
    def __init__(self, number: str, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.number = number
        self.title = title
        self.subtitle = subtitle
        self.width = PAGE_W - 2 * MARGIN_X
        self.height = 24 * mm if subtitle else 18 * mm

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(BLUE)
        c.roundRect(0, self.height - 11 * mm, 11 * mm, 11 * mm, 2.2 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("AegisCN-Bold", 9)
        c.drawCentredString(5.5 * mm, self.height - 7.4 * mm, self.number)
        c.setFillColor(NAVY)
        c.setFont("AegisCN-Bold", 18)
        c.drawString(16 * mm, self.height - 8.2 * mm, self.title)
        c.setStrokeColor(CYAN)
        c.setLineWidth(1.2)
        c.line(16 * mm, self.height - 11.5 * mm, self.width, self.height - 11.5 * mm)
        if self.subtitle:
            c.setFillColor(MUTED)
            c.setFont("AegisCN", 8)
            c.drawString(16 * mm, 2 * mm, self.subtitle)


class MetricCard(Flowable):
    def __init__(self, value: str, label: str, accent=BLUE, note: str = "", width=52 * mm) -> None:
        super().__init__()
        self.value = value
        self.label = label
        self.accent = accent
        self.note = note
        self.width = width
        self.height = 28 * mm

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(WHITE)
        c.setStrokeColor(BORDER)
        c.roundRect(0, 0, self.width, self.height, 3 * mm, fill=1, stroke=1)
        c.setFillColor(self.accent)
        c.roundRect(0, 0, 2.4 * mm, self.height, 1.2 * mm, fill=1, stroke=0)
        c.setFont("AegisCN-Bold", 16)
        c.drawString(6 * mm, self.height - 10 * mm, self.value)
        c.setFillColor(INK)
        c.setFont("AegisCN-Bold", 8)
        c.drawString(6 * mm, self.height - 16 * mm, self.label)
        if self.note:
            c.setFillColor(MUTED)
            c.setFont("AegisCN", 6.4)
            c.drawString(6 * mm, 4 * mm, self.note)


class PipelineDiagram(Flowable):
    def __init__(self) -> None:
        super().__init__()
        self.width = PAGE_W - 2 * MARGIN_X
        self.height = 52 * mm

    def draw(self) -> None:
        c = self.canv
        labels = [
            ("Boundary", "硬边界", BLUE),
            ("Capability", "能力清单", CYAN),
            ("Radius", "影响半径", TEAL),
            ("Drift", "会话漂移", PURPLE),
            ("Friction", "最终裁决", ORANGE),
        ]
        gap = 3 * mm
        box_w = (self.width - gap * 4) / 5
        y = 15 * mm
        for i, (en, cn, col) in enumerate(labels):
            x = i * (box_w + gap)
            c.setFillColor(colors.Color(col.red, col.green, col.blue, alpha=0.12))
            c.setStrokeColor(col)
            c.setLineWidth(1.2)
            c.roundRect(x, y, box_w, 24 * mm, 3 * mm, fill=1, stroke=1)
            c.setFillColor(col)
            c.setFont("Helvetica-Bold", 8.3)
            c.drawCentredString(x + box_w / 2, y + 15.5 * mm, en)
            c.setFillColor(NAVY)
            c.setFont("AegisCN-Bold", 8.6)
            c.drawCentredString(x + box_w / 2, y + 8.5 * mm, cn)
            if i < 4:
                ax = x + box_w + 0.8 * mm
                ay = y + 12 * mm
                c.setStrokeColor(MUTED)
                c.line(ax, ay, ax + gap - 1.6 * mm, ay)
                c.setFillColor(MUTED)
                c.drawPath(_arrow_path(c, ax + gap - 1.7 * mm, ay), fill=1, stroke=0)
        c.setFillColor(LIGHT)
        c.roundRect(0, 0, self.width, 10 * mm, 2 * mm, fill=1, stroke=0)
        c.setFillColor(MUTED)
        c.setFont("AegisCN", 7)
        c.drawCentredString(
            self.width / 2,
            3.5 * mm,
            "规则处理确定性风险 · LLM 仅提取离散语义证据 · 状态机与决策表负责最终裁决",
        )


def _arrow_path(c, x: float, y: float):
    p = c.beginPath()
    p.moveTo(x, y + 1.5 * mm)
    p.lineTo(x + 2.2 * mm, y)
    p.lineTo(x, y - 1.5 * mm)
    p.close()
    return p


class ArchitectureDiagram(Flowable):
    def __init__(self) -> None:
        super().__init__()
        self.width = PAGE_W - 2 * MARGIN_X
        self.height = 86 * mm

    def draw(self) -> None:
        c = self.canv
        bands = [
            ("接入层", "Claude Code · Codex · Cursor · Copilot CLI · OpenClaw · SDK / Proxy", "#E9F3FF", BLUE),
            ("运行时治理层", "PreTool Hook → 五段管线 → Allow / Confirm / Block", "#E8FBFD", CYAN),
            ("会话与证据层", "Trace / Drift 状态 · Manifest · 哈希链审计 · 脱敏与关联", "#EEFAF6", TEAL),
            ("安全运营层", "Agent 调查 · RAG 证据检索 · 免疫学习 · 报告与 SIEM", "#F4EEFF", PURPLE),
            ("存储与部署层", "本地优先 · SQLite · Docker / 私有化 · 可选 DeepSeek", "#FFF5E8", ORANGE),
        ]
        h = 13 * mm
        gap = 3 * mm
        for idx, (name, detail, fill, edge) in enumerate(bands):
            y = self.height - (idx + 1) * h - idx * gap
            c.setFillColor(colors.HexColor(fill))
            c.setStrokeColor(edge)
            c.roundRect(0, y, self.width, h, 2.5 * mm, fill=1, stroke=1)
            c.setFillColor(edge)
            c.setFont("AegisCN-Bold", 8.5)
            c.drawString(5 * mm, y + 4.2 * mm, name)
            c.setFillColor(INK)
            c.setFont("AegisCN", 8)
            c.drawString(38 * mm, y + 4.2 * mm, detail)
            if idx < len(bands) - 1:
                cx = self.width / 2
                c.setStrokeColor(MUTED)
                c.line(cx, y - 0.8 * mm, cx, y - gap + 0.6 * mm)


def table(data, widths, header=True, font_size=7.8, aligns=None) -> Table:
    rendered = []
    for r, row in enumerate(data):
        rendered.append(
            [
                P(str(v), "CNTableHeader" if header and r == 0 else "CNBodySmall")
                for v in row
            ]
        )
    t = Table(rendered, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY_2),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
    ]
    if aligns:
        for col, align in enumerate(aligns):
            commands.append(("ALIGN", (col, 1), (col, -1), align))
    t.setStyle(TableStyle(commands))
    return t


def benchmark_chart() -> Drawing:
    d = Drawing(475, 170)
    chart = VerticalBarChart()
    chart.x = 48
    chart.y = 35
    chart.height = 112
    chart.width = 395
    chart.data = [
        (89.20, 90.34, 96.58, 96.96),
        (17.05, 16.48, 0.00, 0.00),
    ]
    chart.categoryAxis.categoryNames = ["AgentHarm\nJudge", "AgentHarm\n五段", "InjecAgent\nJudge", "InjecAgent\n五段"]
    chart.categoryAxis.labels.fontName = "AegisCN"
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueStep = 20
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 6.5
    chart.valueAxis.labelTextFormat = "%d%%"
    chart.bars[0].fillColor = BLUE
    chart.bars[1].fillColor = ORANGE
    chart.barSpacing = 2
    chart.groupSpacing = 8
    d.add(chart)
    d.add(Rect(95, 157, 9, 6, fillColor=BLUE, strokeColor=None))
    d.add(String(108, 157, "攻击检出率", fontName="AegisCN", fontSize=7, fillColor=INK))
    d.add(Rect(190, 157, 9, 6, fillColor=ORANGE, strokeColor=None))
    d.add(String(203, 157, "正常误报率", fontName="AegisCN", fontSize=7, fillColor=INK))
    return d


def cover_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(NAVY_2)
    canvas.circle(PAGE_W - 14 * mm, PAGE_H - 12 * mm, 67 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(colors.Color(CYAN.red, CYAN.green, CYAN.blue, alpha=0.35))
    canvas.setLineWidth(1)
    for i in range(7):
        canvas.circle(PAGE_W - 16 * mm, PAGE_H - 15 * mm, (20 + i * 9) * mm, fill=0, stroke=1)
    canvas.setFillColor(BLUE)
    canvas.rect(0, 0, 7 * mm, PAGE_H, fill=1, stroke=0)
    canvas.restoreState()


def normal_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_X, PAGE_H - 12 * mm, PAGE_W - MARGIN_X, PAGE_H - 12 * mm)
    canvas.setFillColor(BLUE)
    canvas.setFont("AegisCN-Bold", 7)
    canvas.drawString(MARGIN_X, PAGE_H - 9 * mm, "AI AEGIS · 作品介绍")
    canvas.setFillColor(MUTED)
    canvas.setFont("AegisCN", 6.5)
    canvas.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 9 * mm, "2026 上海开源软件应用创新大赛")
    canvas.line(MARGIN_X, 11 * mm, PAGE_W - MARGIN_X, 11 * mm)
    canvas.drawString(MARGIN_X, 6.7 * mm, "开源 AI 工具赛道 · AI 编程、调试与可观测工具")
    canvas.drawRightString(PAGE_W - MARGIN_X, 6.7 * mm, f"{doc.page}")
    canvas.restoreState()


def cover_story():
    story = []
    story.append(Spacer(1, 11 * mm))
    logo = Image(str(LOGO), width=44 * mm, height=44 * mm)
    story.append(logo)
    story.append(Spacer(1, 12 * mm))
    story.append(P("2026 上海开源软件应用创新大赛", "CNWhiteSmall"))
    story.append(Spacer(1, 4 * mm))
    story.append(P("AI Aegis（灵盾）", "CNCoverTitle"))
    story.append(P("面向企业自研 Agent 的开源运行时安全治理与可观测平台", "CNCoverSub"))
    story.append(Spacer(1, 9 * mm))
    tags = Table(
        [[P("五段式安全管线", "CNWhiteSmall"), P("Manifest 最小权限", "CNWhiteSmall"), P("会话级漂移检测", "CNWhiteSmall"), P("可验证审计", "CNWhiteSmall")]],
        colWidths=[40 * mm, 40 * mm, 40 * mm, 36 * mm],
    )
    tags.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#12366B")),
                ("BOX", (0, 0), (-1, -1), 0.7, CYAN),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#3777B9")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(tags)
    story.append(Spacer(1, 43 * mm))
    story.append(P("参赛赛道", "CNWhiteSmall"))
    story.append(P("开源 AI 工具赛道 · AI 编程、调试与可观测工具 · 自主选题", "CNWhite"))
    story.append(Spacer(1, 3 * mm))
    story.append(P("项目负责人：万翔浩　|　提交版本：v1.0　|　日期：2026年9月", "CNWhiteSmall"))
    story.append(Spacer(1, 10 * mm))
    story.append(P("让每一次 Agent 工具调用都可约束、可解释、可追溯、可验证。", "CNWhite"))
    return story


def build_story():
    s = cover_story()
    s.append(PageBreak())

    s.append(SectionTitle("01", "项目摘要", "从“模型是否安全”转向“Agent 行为是否越界”"))
    s.append(P("<b>AI Aegis（灵盾）</b>是一套面向 AI 编程 Agent 与企业自研 Agent 的开源运行时安全治理平台。它位于 LLM、Agent 与工具执行之间，在文件写入、Shell 命令、网络访问、MCP 调用等动作真正发生前进行策略判断，并把每次决定记录为可复核的证据。"))
    s.append(Spacer(1, 2 * mm))
    cards = Table(
        [[MetricCard("PreTool", "执行前控制", BLUE, "风险动作发生前介入"), MetricCard("5 STAGES", "分层证据决策", PURPLE, "规则 + 语义证据 + 状态机"), MetricCard("LOCAL", "本地优先", TEAL, "无 API Key 也可运行")]],
        colWidths=[57 * mm, 57 * mm, 57 * mm],
    )
    cards.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
    s.append(cards)
    s.append(Spacer(1, 6 * mm))
    s.append(P("核心价值", "CNSub"))
    for x in [
        "面向开发者：正常任务尽量无感放行，高风险动作给出确认或阻断，并展示原因。",
        "面向企业管理员：用 Manifest 定义 Agent 可以做什么、能影响多大范围，并在后台集中查看证据。",
        "面向高校与研究团队：提供开放的 Agent 攻防实验框架、可复现 Benchmark 与消融测试能力。",
        "面向安全运营人员：将 Prompt、模型响应、工具调用和策略版本串成同一条因果链。",
    ]:
        s.append(bullet(x))
    s.append(Spacer(1, 4 * mm))
    s.append(P("产品边界", "CNSub"))
    s.append(P("社区版当前交付以单机/轻量服务器部署、运行时管控、审计与安全运营原型为主。多租户 SSO/RBAC、高可用集群、组织级审批链与大规模策略灰度属于企业产品化路线，不在本次材料中冒充已完成能力。", "CNBodySmall"))
    s.append(PageBreak())

    s.append(SectionTitle("02", "项目背景与问题定义", "Agent 的风险不只存在于一句 Prompt，而存在于完整的意图与行为链"))
    s.append(P("传统内容安全通常回答“这句话是否有害”，系统安全通常回答“这个进程是否调用了危险接口”。但 Agent 会把自然语言转化为连续工具动作：读取文件、运行命令、访问网络、调用企业系统。许多单步动作本身合法，组合起来却可能形成权限爬升、数据外传或破坏性操作。"))
    pain = [
        ["真实痛点", "传统方案的缺口", "AI Aegis 的处理方式"],
        ["单轮正常，多轮逐步越界", "只检查当前工具调用，无法看见会话漂移", "以 traceId 重建会话，Drift 状态机累积证据"],
        ["工具调用字段结构化，但意图是自然语言", "纯正则无法理解语义，纯 LLM 又不稳定", "规则处理确定性问题，LLM 只提取闭集标签"],
        ["企业 Agent 权限边界不清", "只有全局允许/禁止，缺少任务范围", "Manifest 声明能力、目录、网络和工具范围"],
        ["阻断后无法解释与追责", "只有告警，没有完整因果证据", "哈希链审计、会话回放、策略版本关联"],
        ["安全过严影响开发", "默认全拒绝导致高摩擦", "Allow / Confirm / Block 分级处置与授权复用"],
    ]
    s.append(table(pain, [39 * mm, 61 * mm, 76 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("目标", "CNSub"))
    s.append(P("构建一套不依赖单点大模型 Judge、能在真实开发工作流中运行、能够被测试和审计的 Agent 安全治理工具：既阻止高确定性危险行为，也对模糊语义风险给出可解释的分层证据。"))
    s.append(PageBreak())

    s.append(SectionTitle("03", "总体技术架构", "插件主动绑定上下文，安全决策与业务 Agent 解耦"))
    s.append(ArchitectureDiagram())
    s.append(Spacer(1, 3 * mm))
    arch = [
        ["层级", "职责", "主要实现"],
        ["接入层", "捕获 Prompt、响应与工具调用", "原生 Hook、SDK、HTTP Proxy、MCP 适配器"],
        ["治理层", "执行前判断与分级处置", "Boundary / Capability / Radius / Drift / Friction"],
        ["证据层", "关联会话、保存状态与证明", "traceId、Manifest、SQLite、SHA-256 哈希链"],
        ["运营层", "调查、检索、报告、学习", "受控 LangGraph、混合 RAG、免疫生命周期、SIEM"],
        ["部署层", "满足本地与私有化环境", "Windows/Linux、Docker、本地模型与可选云模型"],
    ]
    s.append(table(arch, [27 * mm, 55 * mm, 94 * mm]))
    s.append(Spacer(1, 4 * mm))
    s.append(P("双流观测", "CNSub"))
    s.append(P("系统区分<b>意图流</b>（用户输入、模型输入输出、工具结果中的注入信息）和<b>行为流</b>（工具名、参数、目标路径、网络目的地及执行结果）。两条流通过 traceId、sessionId、turnIndex 和 parentSpanId 关联，避免只看到 HTTP 报文或孤立工具调用。"))
    s.append(PageBreak())

    s.append(SectionTitle("04", "五段式 PreTool 决策管线", "确定性检查优先，模糊语义按需调用模型，最终裁决由代码完成"))
    s.append(PipelineDiagram())
    pipeline = [
        ["阶段", "主要输入", "实现方式", "输出及作用"],
        ["Boundary", "命令、路径、文本与编码特征", "硬规则为主：归一化、零宽/全角、高危 Shell、敏感路径", "命中明确红线时直接产生 Critical 信号"],
        ["Capability", "tool_name、Manifest 能力集合", "结构化集合匹配；自然语言隐式能力可选语义解析", "识别未声明能力，通常进入 Confirm"],
        ["Radius", "路径、网络目标、影响对象", "规则解析项目/本机/用户/系统/外网范围", "判断任务作用域是否扩大"],
        ["Drift", "历史信号、重试、语义标签", "确定性状态机累计分数；LLM 只输出布尔/枚举标签", "捕获主题偏移、权限试探和请求升级"],
        ["Friction", "原始检测 + 前四层证据", "固定权重、阈值与决策表", "输出 Allow / Confirm / Block"],
    ]
    s.append(table(pipeline, [23 * mm, 40 * mm, 57 * mm, 56 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("设计原则", "CNSub"))
    principle = Table(
        [[P("性能", "CNSub"), P("确定性", "CNSub"), P("可解释", "CNSub"), P("可替换", "CNSub")],
         [P("大部分检查毫秒级完成", "CNBodySmall"), P("相同证据得到相同裁决", "CNBodySmall"), P("每个信号可追溯到来源", "CNBodySmall"), P("可替换 DeepSeek/本地模型而不改状态机", "CNBodySmall")]],
        colWidths=[44 * mm] * 4,
    )
    principle.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("BOX", (0, 0), (-1, -1), 0.5, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    s.append(principle)
    s.append(PageBreak())

    s.append(SectionTitle("05", "核心产品能力", "不是聊天壳，而是贯穿安装前、运行时与事后审计的安全工具"))
    features = [
        ["能力域", "已经实现的能力", "用户价值"],
        ["运行时安全", "五段管线、规则引擎、Guardian 本地分类器、Allow/Confirm/Block", "危险工具调用在执行前被控制"],
        ["权限治理", "能力 Manifest、目录与影响范围、JIT 临时授权、无人值守升级策略", "从“全能 Agent”转向最小权限"],
        ["会话可观测", "Trace 时间线、Drift 曲线、Agent Map、调用与成本关联", "快速回答谁在何时因何规则被拦截"],
        ["审计取证", "SHA-256 哈希链、脱敏预览、链完整性验证、报告导出", "降低日志被静默修改后的取证风险"],
        ["安全运营 Agent", "受控工作流、只读工具、证据 RAG、人工审批策略提案", "自然语言调查，但模型不能自行改策略"],
        ["免疫学习", "Candidate→Shadow→Active→Decaying→Retired", "从历史攻击序列学习，同时限制自动误杀"],
        ["证据处理", "PDF/DOCX/表格/日志/截图 OCR、去重、限额与脱敏", "把制度、告警和现场材料纳入调查"],
        ["生态接入", "Claude Code、Codex、Cursor、Copilot CLI、OpenClaw、SDK/Proxy", "覆盖主流 AI 编程和自研 Agent"],
    ]
    s.append(table(features, [30 * mm, 89 * mm, 57 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("可选模型，而非启动前提", "CNSub"))
    s.append(P("不配置 DeepSeek API Key 时，规则、Guardian 本地模型、Manifest、审计和前端均可运行；配置模型后，系统按需增加主题偏移、权限试探、请求升级、明确有害目标等语义证据。模型不可直接返回最终风险分数，也不能绕过 Friction 决策表。"))
    s.append(PageBreak())

    s.append(SectionTitle("06", "典型应用场景", "同一治理内核服务开发者、高校实验室和企业管理员"))
    scenarios = [
        ["场景", "典型风险", "演示流程", "交付价值"],
        ["AI 编程助手", "误删项目、越权读文件、泄露密钥、危险 Git/Shell", "正常读取放行 → 越界写入确认 → 高危命令阻断 → Trace 回放", "减少开发干扰并保留责任链"],
        ["企业自研 Agent", "工具权限过宽、跨系统访问、网络外传", "生成 Manifest → 绑定 Agent → 运行策略 → 管理员复核与导出", "形成可审计的 Agent 上线门槛"],
        ["MCP 生态治理", "恶意工具描述、工具结果注入、未授权能力", "扫描工具/Skill → 运行时检查 → MCP 策略与日志", "降低插件和工具供应链风险"],
        ["高校攻防实验", "中文多轮越狱、链式诱导、权限爬升", "回放数据集 → 观察五层信号 → 调阈值 → 比较召回与误报", "可复现实验与教学框架"],
        ["安全运营调查", "告警分散、证据无关联、报告制作慢", "上传证据 → RAG 检索 → 会话调查 → 人工审批 → 导出报告", "提升调查效率并控制 Agent 权限"],
    ]
    s.append(table(scenarios, [31 * mm, 47 * mm, 59 * mm, 39 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("推荐现场演示闭环", "CNSub"))
    for i, x in enumerate([
        "导入一个 AI 编程 Agent，并加载推荐开发 Manifest。",
        "执行正常的 README 读取与项目内修改，展示无干扰 Allow。",
        "触发项目外写入、敏感信息外传和破坏性命令，展示 Confirm/Block。",
        "重复进行权限试探，展示 Drift 分数与会话证据累积。",
        "在后台回放完整 Trace，验证哈希链并导出审计报告。",
    ], start=1):
        s.append(P(f"<b><font color='#0B6BFF'>{i:02d}</font></b>&nbsp;&nbsp;{x}"))
    s.append(PageBreak())

    s.append(SectionTitle("07", "关键创新点", "创新不在“多调用几次 LLM”，而在安全决策的工程解耦与证据闭环"))
    innovation = [
        ["创新", "技术内容", "相对直接 LLM Judge 的优势"],
        ["五层证据堆叠", "将硬边界、能力范围、影响半径、会话漂移和处置摩擦分层", "每层职责清晰，便于消融、调参和测试"],
        ["状态机主导的 Drift", "LLM 只提取离散标签，分值、重试惩罚和阈值由代码维护", "避免模型直接打分的随机性与不可复现"],
        ["意图流 + 行为流", "同时关联 Prompt、模型输出、工具结果与实际调用", "发现单步合法但组合危险的链式攻击"],
        ["Manifest 最小权限", "能力、路径、网络及影响范围显式声明", "把模糊“可信 Agent”转化为可审计契约"],
        ["受治理免疫学习", "序列签名进入候选和影子态，人工批准后受限贡献 Drift", "可以学习新攻击，但不能自行形成无限权重阻断"],
        ["检测与副作用解耦", "检测器输出 Signal[]，最上层统一执行阻断、确认或脱敏", "支持离线评测、A/B 测试和模型替换"],
        ["可验证证据链", "审计记录串联前序哈希并提供完整性校验", "帮助发现事后文件级篡改，明确不夸大为内存防护"],
    ]
    s.append(table(innovation, [35 * mm, 84 * mm, 57 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("工程取舍", "CNSub"))
    s.append(P("项目优先解决运行时权限、会话漂移和审计证据，不在本阶段引入 eBPF、复杂微沙箱或大规模模型训练。这样既保持本科团队可实现性，也让创新点能够通过代码、测试和演示被评委复核。"))
    s.append(PageBreak())

    s.append(SectionTitle("08", "实验验证与证据边界", "公开数据集用于离线 PreTool 网关重放，候选工具从未执行"))
    s.append(benchmark_chart())
    s.append(Spacer(1, 2 * mm))
    results = [
        ["数据集 / 方案", "攻击样本", "正常样本", "检出率", "正常误报率", "P95 延迟"],
        ["AgentHarm · DeepSeek 直接 Judge", "176", "176", "89.20%", "17.05%", "1133.91 ms"],
        ["AgentHarm · 五段 + 证据 + 聚焦复核", "176", "176", "90.34%", "16.48%", "1251.91 ms"],
        ["InjecAgent · DeepSeek 直接 Judge", "1054", "17", "96.58%", "0/17", "1049.05 ms"],
        ["InjecAgent · 五段 + DeepSeek 证据", "1054", "17", "96.96%", "0/17", "1049.29 ms"],
    ]
    s.append(table(results, [55 * mm, 23 * mm, 23 * mm, 25 * mm, 28 * mm, 30 * mm]))
    s.append(Spacer(1, 4 * mm))
    s.append(P("必须同时说明的边界", "CNSub"))
    for x in [
        "AgentHarm 参数在同一公开分片上开发，属于同分片探索性优化，不是独立泛化证明。",
        "InjecAgent 使用冻结配置跨数据集复测；正常对照仅 17 条，0/17 不能宣传为总体误报率为零。",
        "这里报告的是网关检测/处置结果，不能与论文中的原生攻击成功率、Utility 或 Harm Score 直接横比。",
        "开发工作流回归集含 370 条内部合成样本；推荐 Manifest 在该集合上日常干扰率为 0%，危险保护率为 70%，但不代表生产环境结论。",
    ]:
        s.append(bullet(x, "CNBodySmall"))
    s.append(PageBreak())

    s.append(SectionTitle("09", "产品界面与审计体验", "一次调查从告警进入会话，再落到工具调用与证据"))
    if TRACE_SCREENSHOT.exists():
        img = Image(str(TRACE_SCREENSHOT), width=176 * mm, height=49 * mm)
        s.append(img)
        s.append(P("图 1　Agent Run Trace：按会话展示每次工具调用的 Allow / Block 结果及原因。截图仅展示不含历史品牌标识的运行轨迹区域。", "CNTiny"))
    s.append(Spacer(1, 5 * mm))
    ui = [
        ["界面模块", "核心问题", "用户操作"],
        ["会话安全", "本次会话是否发生主题偏移或权限试探？", "查看 Drift 曲线、分层信号、Allow/Confirm/Block"],
        ["Agent Runs", "哪一步、哪个工具、哪个参数触发了策略？", "按运行时与会话回放 Trace，展开证据"],
        ["Manifest 管理", "Agent 被允许使用哪些能力？", "选择预设、设置范围、模拟变更、发布版本"],
        ["即时审计", "历史记录是否包含高危行为或凭据？", "扫描本地会话、脱敏、导出报告"],
        ["安全运营", "告警背后的制度和上下文是什么？", "检索证据、运行调查 Agent、人工审批提案"],
        ["完整性验证", "审计记录是否被删除或修改？", "一键验证 SHA-256 哈希链"],
    ]
    s.append(table(ui, [34 * mm, 73 * mm, 69 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("中英文一致性", "CNSub"))
    s.append(P("前端提供中英文切换，核心功能、风险原因和操作提示使用统一词典；参赛演示以中文为主，保留英文术语以便国际化展示。"))
    s.append(PageBreak())

    s.append(SectionTitle("10", "部署、隐私与开源治理", "本地优先不等于孤立：既能离线运行，也能接入企业安全体系"))
    deploy = [
        ["维度", "当前交付", "企业扩展方向"],
        ["部署", "Windows/Linux 本地运行，轻量 Docker Demo", "私有化控制平面、高可用 Worker、Kubernetes"],
        ["数据", "SQLite、本地日志、默认只保存脱敏预览", "PostgreSQL、对象存储、组织级留存策略"],
        ["身份", "本地 UI Token 与敏感接口保护", "SSO、RBAC、审批链与租户隔离"],
        ["模型", "规则和本地 Guardian 默认可用，DeepSeek 可选", "企业模型网关、本地大模型、调用配额与审计"],
        ["外部集成", "Webhook、NDJSON、基础 SIEM 适配", "Splunk、Sentinel、Datadog、OTLP 与工单系统"],
    ]
    s.append(table(deploy, [30 * mm, 74 * mm, 72 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("隐私与安全原则", "CNSub"))
    for x in [
        "默认本地运行，无需注册账号或上传原始 Prompt；外发仅在管理员显式配置目标后发生。",
        "密钥和敏感字段在持久化前脱敏；审计预览限制长度，不保存原始载荷。",
        "安全运营 Agent 使用闭集只读工具，不能获得任意 Shell，也不能直接修改执行策略。",
        "高风险策略变更必须先模拟，再按提案哈希人工审批并幂等应用。",
    ]:
        s.append(bullet(x))
    s.append(Spacer(1, 4 * mm))
    s.append(P("开源治理", "CNSub"))
    s.append(P("项目采用 Apache License 2.0，保留 LICENSE、NOTICE、SECURITY、变更记录及第三方来源说明。代码同时托管于 GitHub 与 Gitee，并计划以贡献指南、Issue/PR 模板、公开 Roadmap 和安全披露流程持续建设社区。"))
    s.append(PageBreak())

    s.append(SectionTitle("11", "项目可持续发展", "社区版积累真实反馈，企业版围绕组织级治理与服务形成收入"))
    model = [
        ["版本", "目标用户", "核心价值", "商业方式"],
        ["Community / Academic", "个人开发者、高校实验室、开源社区", "Agent 攻防实验、单机治理、Benchmark 与基础插件", "Apache-2.0 免费开源，积累适配器和真实反馈"],
        ["Team", "初创团队与小型研发组织", "团队策略、共享 Manifest、审计留存和基础支持", "规划定价 499 美元/年；属于商业计划，不是已发生收入"],
        ["Business / Enterprise", "中大型企业、自研 Agent 平台和安全团队", "SSO/RBAC、集中策略、私有化部署、合规审计与 SLA", "年度订阅 + 私有化授权 + 专业实施与定制服务"],
    ]
    s.append(table(model, [35 * mm, 42 * mm, 64 * mm, 43 * mm]))
    s.append(Spacer(1, 6 * mm))
    roadmap = [
        ["阶段", "目标", "可验收结果"],
        ["参赛交付", "稳定安装、五分钟演示、公开复现", "版本化仓库、PDF、演示视频、Benchmark 脚本"],
        ["社区验证", "高校实验室与开发团队试用", "真实 Issue/PR、匿名开发轨迹、误报标注集"],
        ["团队产品", "策略共享与小规模集中管理", "组织空间、设备同步、审计保留、支持服务"],
        ["企业产品", "私有化治理控制面", "SSO/RBAC、审批链、高可用、租户隔离、SIEM/SOC 集成"],
    ]
    s.append(table(roadmap, [30 * mm, 67 * mm, 79 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("长期壁垒", "CNSub"))
    s.append(P("产品壁垒将来自三类积累：跨 Agent 的运行时适配与权限语义、真实开发工作流中的低误报策略数据、以及可追溯的 Manifest/审计治理标准。项目不以单一模型能力作为护城河。"))
    s.append(PageBreak())

    s.append(SectionTitle("12", "总结与提交信息", "让 Agent 的能力增长建立在可控、可解释、可审计的基础上"))
    s.append(P("AI Aegis 面向正在快速普及的 AI 编程 Agent 和企业自研 Agent，提供从执行前安全决策到事后审计调查的完整闭环。项目以五段式管线为核心，将确定性规则、语义证据、会话状态机和分级处置解耦，避免把安全完全托付给随机的大模型判断。"))
    s.append(Spacer(1, 5 * mm))
    conclusion = Table(
        [
            [P("可运行", "CNSub"), P("可测试", "CNSub"), P("可解释", "CNSub"), P("可演进", "CNSub")],
            [P("插件、后台与本地部署形成完整产品闭环", "CNBodySmall"), P("公开基准、内部回归、JSON/CSV/Markdown 结果", "CNBodySmall"), P("信号、分数、策略版本与处置理由可追溯", "CNBodySmall"), P("社区版与企业治理控制面路线清晰", "CNBodySmall")],
        ],
        colWidths=[44 * mm] * 4,
    )
    conclusion.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9F3FF")), ("BOX", (0, 0), (-1, -1), 0.7, BLUE), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    s.append(conclusion)
    s.append(Spacer(1, 9 * mm))
    s.append(P("提交信息", "CNSub"))
    info = [
        ["项目名称", "AI Aegis（灵盾）：面向企业自研 Agent 的开源运行时安全治理与可观测平台"],
        ["参赛方向", "开源 AI 工具赛道 - AI 编程、调试与可观测工具 - 自主选题"],
        ["项目负责人", "万翔浩"],
        ["代码仓库", "GitHub: https://github.com/Goodevenin9/ai-aegis<br/>Gitee: https://gitee.com/wan-xianghao/ai-aegis"],
        ["开源协议", "Apache License 2.0（上游来源与变更说明见 NOTICE）"],
    ]
    s.append(table(info, [35 * mm, 141 * mm], header=False))
    s.append(Spacer(1, 8 * mm))
    s.append(P("声明：本文档所列“当前交付”均以仓库代码和归档报告为依据；规划能力、计划定价与企业产品化方向均明确标注，不作为已完成或已产生收入的事实陈述。", "CNBodySmall"))
    s.append(PageBreak())

    s.append(SectionTitle("附", "证据索引与复现入口", "便于评委从结论回到代码、配置与原始报告"))
    evidence = [
        ["证据类型", "仓库路径 / 入口", "说明"],
        ["五段管线设计", "docs/FIVE_STAGE_PRETOOL_PIPELINE.md", "各层输入、信号、阈值与决策原则"],
        ["交付验收", "docs/COMPETITION_ACCEPTANCE.md", "功能边界、测试、部署和未完成项"],
        ["AgentHarm 机器报告", "reports/agentharm-five-stage-optimized-final-20260917/", "JSON、CSV、Markdown 与实现/配置哈希"],
        ["InjecAgent 冻结复测", "reports/injecagent-frozen-five-stage-20260917/", "跨数据集复测及 Wilson 区间说明"],
        ["开发工作流回归", "reports/developer-workflows-v1-20260918/", "370 条内部工程回归样本和 Manifest 对照"],
        ["安装与使用", "docs/GETTING_STARTED.md · docs/INSTALLATION.md", "本地安装、启动与接入流程"],
        ["API 与 SDK", "docs/API_SPECIFICATION.md · docs/SDK_USAGE.md", "接口契约和 Agent 集成"],
        ["开源合规", "LICENSE · NOTICE · SECURITY.md", "协议、来源、商标与安全披露"],
    ]
    s.append(table(evidence, [38 * mm, 77 * mm, 61 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("Benchmark 复现原则", "CNSub"))
    for x in [
        "固定数据版本、代码提交、配置哈希、模型名称和证据 Schema。",
        "候选工具只进行离线重放，禁止真实执行危险命令。",
        "同时报告攻击检出率、正常误报率、确认率、硬阻断率、Precision、F1 与延迟。",
        "开发集、验证集和测试集隔离；免疫学习不得使用测试真值生成抗体。",
        "任何对外数字必须能回溯到机器可读 JSON/CSV 和明确口径。",
    ]:
        s.append(bullet(x))
    s.append(Spacer(1, 5 * mm))
    s.append(P("赛事资料来源", "CNSub"))
    s.append(P("2026 上海开源软件应用创新大赛官网：https://www.oschina.net/os2026/。本项目按“开源 AI 工具赛道 - AI 编程、调试与可观测工具”准备材料。", "CNBodySmall"))
    return s


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="AI Aegis 作品介绍 - 2026上海开源软件应用创新大赛",
        author="万翔浩",
        subject="开源 AI 工具赛道参赛作品介绍",
    )
    cover_frame = Frame(MARGIN_X, 20 * mm, PAGE_W - 2 * MARGIN_X, PAGE_H - 36 * mm, id="cover", showBoundary=0)
    normal_frame = Frame(MARGIN_X, MARGIN_BOTTOM, PAGE_W - 2 * MARGIN_X, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="normal", showBoundary=0)
    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], onPage=cover_page, autoNextPageTemplate="Normal"),
        PageTemplate(id="Normal", frames=[normal_frame], onPage=normal_page),
    ])
    doc.build(build_story())
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
