"""Generate the frozen, competition-delivery report for AI Aegis.

The report follows the evidence-first structure of the September 14 business
plan while targeting the 2026 Shanghai Open Source Software Application
Innovation Competition. Product facts are frozen to the tracked repository
snapshot and archived benchmark reports dated 2026-09-17/18.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from generate_oschina_submission_pdf import (
    ArchitectureDiagram,
    BLUE,
    BORDER,
    CYAN,
    INK,
    LIGHT,
    LOGO,
    MARGIN_BOTTOM,
    MARGIN_TOP,
    MARGIN_X,
    MUTED,
    NAVY,
    NAVY_2,
    ORANGE,
    PAGE_H,
    PAGE_W,
    P,
    PipelineDiagram,
    PURPLE,
    RED,
    SectionTitle,
    TEAL,
    TRACE_SCREENSHOT,
    WHITE,
    bullet,
    styles,
    table,
)


ROOT = Path(__file__).resolve().parents[1]
DELIVERY = Path(r"C:\Users\19546\Desktop\aiaegis国赛最终交付物")
OUTPUT = DELIVERY / "AI-Aegis-2026上海开源软件应用创新大赛-完整项目报告-冻结版.pdf"
SNAPSHOT = "933a313"
FREEZE_DATE = "2026-09-20"


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


AGENTHARM_PATH = "reports/agentharm-five-stage-optimized-final-20260917/external_benchmark_results.json"
INJEC_PATH = "reports/injecagent-frozen-five-stage-20260917/external_benchmark_results.json"
DEV_PATH = "reports/developer-workflows-v1-20260918/developer_workflow_results.json"
AGENTHARM = load_json(AGENTHARM_PATH)
INJEC = load_json(INJEC_PATH)
DEV = load_json(DEV_PATH)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def result(report: dict, variant: str) -> dict:
    benchmarks = report["benchmarks"]
    if not benchmarks:
        raise KeyError("benchmarks")
    benchmark = benchmarks[0]
    for row in benchmark["results"]:
        if row["variant"] == variant:
            return row
    raise KeyError(variant)


AH_JUDGE = result(AGENTHARM, "deepseek_judge_live")
AH_FIVE = result(AGENTHARM, "five_stage_deepseek_verified_live")
IJ_JUDGE = result(INJEC, "deepseek_judge_live")
IJ_FIVE = result(INJEC, "five_stage_deepseek_verified_live")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def page_break(story: list) -> None:
    story.append(PageBreak())


def callout(title: str, body: str, accent=BLUE) -> Table:
    data = [[P(title, "CNSub"), P(body, "CNBodySmall")]]
    t = Table(data, colWidths=[34 * mm, 142 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return t


def status_table(rows: list[list[str]]) -> Table:
    colors_map = {"已实现": TEAL, "部分实现": ORANGE, "规划中": MUTED, "需复核": RED}
    data = [[P("状态", "CNTableHeader"), P("能力/主张", "CNTableHeader"), P("证据与边界", "CNTableHeader")]]
    for state, claim, evidence in rows:
        data.append([P(f"<b><font color='{colors_map.get(state, MUTED).hexval()}'>{state}</font></b>", "CNBodySmall"), P(claim, "CNBodySmall"), P(evidence, "CNBodySmall")])
    t = Table(data, colWidths=[23 * mm, 61 * mm, 92 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY_2),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def score_chart() -> Drawing:
    d = Drawing(500, 185)
    names = ["技术创新", "场景落地", "开源治理", "长期发展"]
    weights = [30, 30, 20, 20]
    cols = [BLUE, CYAN, TEAL, PURPLE]
    x = 20
    for i, (name, weight, col) in enumerate(zip(names, weights, cols)):
        w = weight * 4.3
        d.add(Rect(x, 82, w, 38, fillColor=col, strokeColor=None))
        d.add(String(x + w / 2, 103, f"{weight}%", fontName="Helvetica-Bold", fontSize=12, textAnchor="middle", fillColor=WHITE))
        d.add(String(x + w / 2, 89, name, fontName="AegisCN-Bold", fontSize=8, textAnchor="middle", fillColor=WHITE))
        x += w
    d.add(String(20, 145, "赛事评分结构", fontName="AegisCN-Bold", fontSize=11, fillColor=NAVY))
    d.add(String(20, 58, "一等奖策略：创新必须落到代码，落地必须落到真实流程，开源必须落到治理文件，规划必须标明边界。", fontName="AegisCN", fontSize=7.5, fillColor=MUTED))
    d.add(Line(20, 45, 480, 45, strokeColor=BORDER, strokeWidth=1))
    d.add(String(20, 26, "本报告不预测名次；“一等奖冲刺版”表示按一等奖证据标准组织，而非保证获奖。", fontName="AegisCN", fontSize=7, fillColor=RED))
    return d


def benchmark_chart() -> Drawing:
    d = Drawing(485, 188)
    chart = VerticalBarChart()
    chart.x = 52
    chart.y = 38
    chart.height = 115
    chart.width = 402
    chart.data = [
        (AH_JUDGE["attack_detection_recall"] * 100, AH_FIVE["attack_detection_recall"] * 100, IJ_JUDGE["attack_detection_recall"] * 100, IJ_FIVE["attack_detection_recall"] * 100),
        (AH_JUDGE["benign_false_positive_rate"] * 100, AH_FIVE["benign_false_positive_rate"] * 100, IJ_JUDGE["benign_false_positive_rate"] * 100, IJ_FIVE["benign_false_positive_rate"] * 100),
    ]
    chart.categoryAxis.categoryNames = ["AH\nJudge", "AH\n五段", "IJ\nJudge", "IJ\n五段"]
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
    d.add(Rect(105, 170, 10, 6, fillColor=BLUE, strokeColor=None))
    d.add(String(119, 169, "攻击检出率", fontName="AegisCN", fontSize=7, fillColor=INK))
    d.add(Rect(210, 170, 10, 6, fillColor=ORANGE, strokeColor=None))
    d.add(String(224, 169, "正常误报率", fontName="AegisCN", fontSize=7, fillColor=INK))
    return d


def freeze_fingerprint_table() -> Table:
    ah_hash = sha256_file(ROOT / AGENTHARM_PATH)
    ij_hash = sha256_file(ROOT / INJEC_PATH)
    dev_hash = sha256_file(ROOT / DEV_PATH)
    rows = [
        ["冻结对象", "冻结值", "用途"],
        ["代码快照", f"Git {SNAPSHOT}", "本报告技术主张的代码基线"],
        ["冻结日期", FREEZE_DATE, "此日期之后的能力不写入本版"],
        ["AgentHarm结果", ah_hash[:20] + "…", "352条公开样本的机器结果"],
        ["InjecAgent结果", ij_hash[:20] + "…", "1,071条冻结配置复测"],
        ["开发工作流结果", dev_hash[:20] + "…", "370条内部工程回归"],
        ["管线配置哈希", AGENTHARM["run_metadata"]["pipeline_config_sha256"][:20] + "…", "阈值与策略配置指纹"],
        ["实现指纹", AGENTHARM["run_metadata"]["implementation_sha256"][:20] + "…", "Benchmark运行时实现指纹"],
    ]
    return table(rows, [34 * mm, 78 * mm, 64 * mm])


def cover_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, 0, 6 * mm, PAGE_H, fill=1, stroke=0)
    canvas.setStrokeColor(colors.Color(CYAN.red, CYAN.green, CYAN.blue, alpha=0.4))
    for i in range(7):
        canvas.circle(PAGE_W - 16 * mm, PAGE_H - 18 * mm, (18 + i * 10) * mm, fill=0, stroke=1)
    canvas.setFillColor(colors.HexColor("#102E5A"))
    canvas.roundRect(18 * mm, 18 * mm, PAGE_W - 36 * mm, 23 * mm, 3 * mm, fill=1, stroke=0)
    canvas.restoreState()


def normal_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, PAGE_H - 12 * mm, PAGE_W - MARGIN_X, PAGE_H - 12 * mm)
    canvas.setFillColor(BLUE)
    canvas.setFont("AegisCN-Bold", 7)
    canvas.drawString(MARGIN_X, PAGE_H - 9 * mm, "AI AEGIS · 完整项目报告 · 冻结版")
    canvas.setFillColor(MUTED)
    canvas.setFont("AegisCN", 6.5)
    canvas.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 9 * mm, "2026 上海开源软件应用创新大赛")
    canvas.line(MARGIN_X, 11 * mm, PAGE_W - MARGIN_X, 11 * mm)
    canvas.drawString(MARGIN_X, 6.7 * mm, f"开源 AI 工具赛道 · 证据快照 {SNAPSHOT}")
    canvas.drawRightString(PAGE_W - MARGIN_X, 6.7 * mm, str(doc.page))
    canvas.restoreState()


def cover_story() -> list:
    story: list = [Spacer(1, 8 * mm)]
    story.append(Image(str(LOGO), width=42 * mm, height=42 * mm))
    story.append(Spacer(1, 10 * mm))
    story.append(P("2026 上海开源软件应用创新大赛", "CNWhiteSmall"))
    story.append(Spacer(1, 3 * mm))
    story.append(P("AI Aegis（灵盾）", "CNCoverTitle"))
    story.append(P("面向企业自研 Agent 的开源运行时安全治理与可观测平台", "CNCoverSub"))
    story.append(Spacer(1, 6 * mm))
    story.append(P("完 整 项 目 报 告 · 冻 结 版", "CNWhite"))
    story.append(Spacer(1, 7 * mm))
    tags = Table([[P("五段式安全管线", "CNWhiteSmall"), P("Manifest安全契约", "CNWhiteSmall"), P("会话级漂移检测", "CNWhiteSmall"), P("可验证审计", "CNWhiteSmall")]], colWidths=[40 * mm, 42 * mm, 42 * mm, 36 * mm])
    tags.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#12366B")),
        ("BOX", (0, 0), (-1, -1), 0.7, CYAN),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#3777B9")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tags)
    story.append(Spacer(1, 43 * mm))
    story.append(P("参赛方向", "CNWhiteSmall"))
    story.append(P("开源 AI 工具赛道 · AI 编程、调试与可观测工具 · 自主选题", "CNWhite"))
    story.append(Spacer(1, 4 * mm))
    story.append(P("项目负责人：万翔浩　|　开源协议：Apache License 2.0", "CNWhiteSmall"))
    story.append(P(f"内容冻结：{FREEZE_DATE}　|　源代码快照：{SNAPSHOT}", "CNWhiteSmall"))
    story.append(Spacer(1, 13 * mm))
    story.append(P("技术主张必须能回到代码，实验数字必须能回到机器报告，规划能力必须明确标注为未来工作。", "CNWhite"))
    return story


def add_toc(story: list) -> None:
    story.append(SectionTitle("目录", "报告结构", "参考 SubVersion 的证据优先模式，压缩为可评审、可复核的完整报告"))
    rows = [
        ["篇章", "内容", "评审作用"],
        ["第一篇 项目与问题", "项目概述、痛点、用户与场景", "说明为什么值得做"],
        ["第二篇 产品与架构", "五段管线、双流观测、Manifest、审计与运营", "说明系统如何工作"],
        ["第三篇 技术创新", "六项创新、闭集证据契约、状态机与免疫学习", "回答技术独创性"],
        ["第四篇 工程实现", "代码索引、接入边界、部署与界面", "让评委能够现场复核"],
        ["第五篇 验证体系", "公开Benchmark、开发工作流、测试及局限", "说明真实效果和证据边界"],
        ["第六篇 开源与发展", "治理、商业模式、路线图、社会价值", "回答长期发展能力"],
        ["附录", "复现命令、数据字典、风险清单、答辩证据索引", "缩短评审核验路径"],
    ]
    story.append(table(rows, [34 * mm, 83 * mm, 59 * mm]))
    story.append(Spacer(1, 7 * mm))
    story.append(P("报告阅读建议", "CNSub"))
    story.append(P("初审可阅读执行摘要、创新矩阵和验证结论；技术评审可沿代码索引定位实现；答辩评审可使用演示脚本和证据索引逐项核查。报告不以篇幅替代证据，每个强结论均配有限定条件。"))
    story.append(Spacer(1, 5 * mm))
    story.append(callout("三种状态词", "已实现：代码与证据可定位；部分实现：存在实现但覆盖或验证不足；规划中：未来工作，不进入当前能力评分。", TEAL))


def build_story() -> list:
    s = cover_story()
    page_break(s)

    s.append(SectionTitle("00", "文档控制与冻结声明", "冻结当前成果，停止在报告中引入未经验证的新能力"))
    s.append(P("本报告以 AI Aegis 当前可追溯仓库和归档机器报告为唯一事实来源。冻结不代表项目停止迭代，而是确保评委看到的代码、配置、实验数字和材料口径一致。"))
    s.append(freeze_fingerprint_table())
    s.append(Spacer(1, 5 * mm))
    s.append(status_table([
        ["已实现", "五段式 PreTool 管线、Manifest、会话状态、审计链、插件和安全运营原型", "代码和测试位于冻结快照；具体边界在后文逐项说明。"],
        ["部分实现", "多运行时覆盖、轻量服务器部署、企业控制面", "入口已存在，但不同宿主的阻断语义、容器运行和企业能力仍需逐环境验证。"],
        ["规划中", "SSO/RBAC、多租户、高可用、组织级审批和大规模灰度", "属于企业产品化路线，不写成当前交付。"],
        ["需复核", "版本字符串一致性", "包版本为1.0.2，但部分内部CLI/服务仍显示1.0.1；本报告不隐去该问题。"],
    ]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("冻结范围不包含工作区中未纳入 Git 的临时实验目录。对外可引用的核心实验均来自已跟踪 JSON/CSV/Markdown 报告。", "CNBodySmall"))
    page_break(s)

    s.append(SectionTitle("01", "执行摘要", "从内容过滤器升级为 Agent 行为治理层"))
    s.append(P("AI Aegis 是面向 AI 编程 Agent 与企业自研 Agent 的开源运行时安全治理平台。系统位于 Agent 与工具之间，在文件、Shell、Git、网络和 MCP 动作真正执行前进行分层判断，并将每次决定写入可验证审计记录。"))
    s.append(P("项目的核心主张可以压缩为一句话：<b>LLM提取语义证据，确定性代码维护状态并作出最终裁决。</b>这使系统既能理解多轮中文语义风险，又不把阈值、分数和阻断权交给不可复现的端到端Judge。"))
    s.append(ArchitectureDiagram())
    s.append(Spacer(1, 3 * mm))
    summary = [
        ["问题", "解决方案", "可验证证据"],
        ["单步正常、多轮逐步越界", "Drift会话状态机累积主题偏移、权限试探和重复重试", "Trace时间线、状态分数和单元测试"],
        ["规则不懂语义、LLM裁决不稳定", "闭集语义标签 + 固定权重/阈值/决策表", "semantic_evidence.py与配置哈希"],
        ["Agent权限边界模糊", "Manifest声明能力、目录、网络和影响半径", "Manifest设计器、模拟结果和审计版本"],
        ["阻断后无法解释", "Signal[]证据、Allow/Confirm/Block和哈希链审计", "UI回放、审计验证和机器报告"],
    ]
    s.append(table(summary, [43 * mm, 78 * mm, 55 * mm]))
    page_break(s)

    add_toc(s)
    page_break(s)

    s.append(SectionTitle("02", "赛事适配与一等奖证据策略", "按技术创新30%、场景落地30%、开源治理20%、长期发展20%组织证据"))
    s.append(score_chart())
    score_rows = [
        ["评分维度", "本项目主证据", "仍需诚实说明的边界"],
        ["技术创新 30%", "五段管线、Drift状态机、闭集语义契约、受治理免疫学习", "创新来自组合与工程闭环，不宣称每个基础技术首次出现"],
        ["场景落地 30%", "真实插件、Manifest、前端、公开数据集复测、开发工作流回归", "公开Benchmark是离线PreTool重放，不等于原生Agent ASR"],
        ["开源治理 20%", "Apache-2.0、NOTICE、SECURITY、来源与依赖说明", "社区运营量仍有限，不虚构Issue/PR活跃度"],
        ["长期发展 20%", "社区版 + Team + 企业服务路线、适配器生态、私有化方向", "价格与收入为假设，不是签约收入"],
    ]
    s.append(table(score_rows, [35 * mm, 85 * mm, 56 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(callout("一等奖冲刺原则", "不再堆叠普通功能，而是用一条完整链证明：真实Agent接入 → 正常任务低干扰 → 高风险调用被控制 → 会话证据可回放 → 实验结果可复现。", BLUE))
    page_break(s)

    s.append(SectionTitle("03", "项目愿景、定位与边界", "让 Agent 的能力增长建立在可控、可解释、可审计的基础上"))
    for title, body in [
        ("产品定位", "面向开发者、高校实验室和企业AI平台团队的开源Agent运行时安全工具，而不是通用聊天应用。"),
        ("核心用户", "AI编程工具使用者、自研Agent团队、MCP工具管理者、安全运营人员和Agent安全研究者。"),
        ("部署形态", "本地优先；规则、Guardian、Manifest、审计和前端在无外部API Key时仍可运行；语义模型为可选增强。"),
        ("保护边界", "应用层Hook/Proxy覆盖的事件和工具调用；未接入的宿主路径、操作系统内核和旁路流量不在保护范围。"),
        ("价值主张", "在不牺牲正常开发效率的前提下，把Agent动作变成受安全契约约束、可复核的执行。"),
    ]:
        s.append(callout(title, body, TEAL if title != "保护边界" else ORANGE))
        s.append(Spacer(1, 3 * mm))
    page_break(s)

    s.append(SectionTitle("04", "问题定义：风险发生在完整语义行为链", "系统调用可能完全合法，问题在于动作是否偏离原始任务意图"))
    problem = [
        ["风险类型", "示例", "单点检测为何不足", "需要的上下文"],
        ["权限爬升", "从读项目逐步转向系统目录、凭据和外网", "每一步都可能是合法工具调用", "初始任务、Manifest、范围变化和重试"],
        ["间接提示注入", "网页或MCP结果诱导Agent外传信息", "恶意内容出现在工具结果，不在用户Prompt", "意图流、工具结果与后续行为"],
        ["中文链式越狱", "用角色扮演、分步请求和语义反转绕过规则", "关键词可被拆分、变形和混淆", "多轮语义证据与状态累计"],
        ["高影响合法操作", "部署、推送、删除和云权限调整", "内容本身未必恶意，但影响半径大", "工具、目标、作用域和审批状态"],
        ["事后抵赖", "删除或修改本地日志", "普通日志缺少链式完整性证明", "哈希链、检查点和外部锚定边界"],
    ]
    s.append(table(problem, [32 * mm, 49 * mm, 51 * mm, 44 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("项目因此不把“是否出现危险词”作为唯一问题，而是持续回答三个问题：<b>想做什么、被允许做什么、实际正在做什么。</b>"))
    page_break(s)

    s.append(SectionTitle("05", "目标用户与应用场景", "以AI编程与企业自研Agent为主场景，以高校攻防实验形成开源入口"))
    scenarios = [
        ["用户", "当前任务", "主要痛点", "AI Aegis交付"],
        ["个人开发者", "使用Claude Code/Codex修改项目", "高危命令和凭据外传难以预知", "本地插件、推荐Manifest、Trace与审计"],
        ["高校实验室", "开展Agent安全教学和攻防实验", "缺少可复现、可观察的运行时框架", "数据集回放、五层信号、阈值实验和报告"],
        ["企业Agent团队", "自研Agent连接文件、数据库和内部API", "权限清单、上线审核和行为审计缺失", "Manifest安全契约、策略模拟和集中治理路线"],
        ["安全运营人员", "调查异常会话和跨工具链事件", "证据分散、报告制作慢", "只读SecOps Agent、证据RAG、哈希链与SIEM"],
        ["MCP生态维护者", "管理第三方工具和Skill", "工具描述、结果和包本身可携带风险", "静态扫描、MCP策略、运行时记录"],
    ]
    s.append(table(scenarios, [34 * mm, 48 * mm, 49 * mm, 45 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(callout("市场进入顺序", "先通过开源社区和高校实验获得真实反馈与适配器贡献，再向小型研发团队验证Team订阅，最后以私有化部署和专业服务进入企业。", BLUE))
    page_break(s)

    s.append(SectionTitle("06", "总体技术架构", "接入层、治理层、证据层、运营层和部署层相互解耦"))
    s.append(ArchitectureDiagram())
    arch = [
        ["层级", "关键组件", "信任边界"],
        ["接入层", "Claude Code/Codex/Cursor/Copilot/OpenClaw Hook、SDK、Proxy", "仅能治理实际进入Hook或Proxy的事件"],
        ["运行时治理层", "规则、Guardian、五段管线、策略引擎", "LLM不得直接决定分数、阈值或最终Verdict"],
        ["会话与证据层", "Trace、Drift、Manifest、JIT、审计链、SQLite", "敏感载荷持久化前脱敏；哈希链有明确威胁边界"],
        ["安全运营层", "SecOps Agent、RAG、免疫学习、报告、SIEM", "Agent只有闭集只读工具；策略修改需要人工审批"],
        ["部署层", "本地进程、Docker Demo、轻量控制面", "多租户、高可用和企业身份仍属产品化路线"],
    ]
    s.append(table(arch, [27 * mm, 79 * mm, 70 * mm]))
    page_break(s)

    s.append(SectionTitle("07", "意图流与行为流", "用统一Trace把Prompt、模型响应、工具结果与实际调用串成因果链"))
    flow = [
        ["事件", "所属流", "主要字段", "安全用途"],
        ["user_prompt / llm_input", "意图流", "任务目标、会话、轮次、脱敏摘要", "捕获直接注入与原始任务意图"],
        ["llm_output", "意图流", "模型计划、工具建议、敏感内容", "发现泄漏和模型被诱导迹象"],
        ["tool_result", "意图流/桥接", "来源工具、返回摘要、不可信标记", "发现间接提示注入"],
        ["pre_tool_call", "行为流", "tool_name、参数、路径、网络目标", "五段管线执行前裁决"],
        ["post_tool_call", "行为流", "执行结果、影响和失败状态", "补全审计和后续Drift证据"],
    ]
    s.append(table(flow, [38 * mm, 29 * mm, 61 * mm, 48 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("关联键包括 traceId、sessionId、turnIndex、parentSpanId 和 requestId。它们把扁平日志重建为会话、轮次和调用链，同时避免依赖宿主平台主动提供完整安全语义。"))
    s.append(callout("实现边界", "不同运行时可提供的事件类型不同。支持某个Agent入口不代表其所有执行路径都已覆盖；每个适配器必须按事件类型和宿主版本单独验收。", ORANGE))
    page_break(s)

    s.append(SectionTitle("08", "五段式 PreTool 管线总览", "分层提取证据，统一状态累计，单一出口执行副作用"))
    s.append(PipelineDiagram())
    layers = [
        ["阶段", "确定性职责", "语义模型职责", "能否独立Block"],
        ["Boundary", "归一化、混淆、高危命令、敏感路径", "默认不参与；仅可补充变形语义", "Critical红线可以"],
        ["Capability", "tool_name与Manifest集合匹配", "仅处理隐式能力意图", "通常不独立Block"],
        ["Radius", "项目/本机/用户/系统/外网范围", "模糊范围扩张标签", "通常不独立Block"],
        ["Drift", "固定状态转移、重试、去重、分数上限", "输出闭集布尔/枚举证据", "输出分数，不执行副作用"],
        ["Friction", "固定权重、阈值、决策表", "不参与最终裁决", "是最终Verdict出口"],
    ]
    s.append(table(layers, [26 * mm, 67 * mm, 55 * mm, 28 * mm]))
    s.append(Spacer(1, 4 * mm))
    s.append(P("同一证据、同一状态和同一配置必须产生相同分数与Verdict。模型失败、字段未知或类型不匹配时，系统丢弃该语义证据并回退到规则，而不是让自由文本进入决策。"))
    page_break(s)

    s.append(SectionTitle("09", "Boundary与中文对抗归一化", "让确定性红线保持毫秒级、可测试、可解释"))
    boundary = [
        ["处理步骤", "示例", "输出"],
        ["Unicode归一化", "全角字符、同形字符、组合字符", "统一文本表示"],
        ["不可见字符处理", "零宽空格、方向控制符", "混淆信号与规范化文本"],
        ["编码与命令模式", "Base64、Shell拼接、危险解释器调用", "规则命中与严重级别"],
        ["路径安全", "系统目录、凭据目录、目录穿越", "路径范围与越界信号"],
        ["中文语义红线", "越狱、绕过、提权、外传和破坏性意图", "高置信风险信号"],
    ]
    s.append(table(boundary, [40 * mm, 76 * mm, 60 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(callout("设计取舍", "混淆特征本身不必然等于攻击，默认作为证据而非一律阻断；只有确定性高危命令、敏感路径或明确红线进入Critical。", BLUE))
    s.append(Spacer(1, 5 * mm))
    s.append(P("核心实现：<font color='#0B6BFF'>src/aegis/app/services/chinese_security_rules.py</font>；管线组合：<font color='#0B6BFF'>src/aegis/app/services/pretool_pipeline.py</font>。"))
    page_break(s)

    s.append(SectionTitle("10", "Capability、Radius与Manifest安全契约", "从“这个Agent可信”转向“这次调用是否属于被授权能力和范围”"))
    manifest = [
        ["维度", "声明示例", "运行时判断"],
        ["能力", "file_read / file_write / shell_exec / network_outbound", "工具能力是否在会话允许集合"],
        ["文件范围", "project / user / system与具体路径", "目标是否越出项目或批准目录"],
        ["网络范围", "允许、确认、拒绝的域名或目的地", "外联是否扩大影响半径"],
        ["动作类型", "read / build / test / deploy / delete / publish", "同一工具内部区分低风险与高影响动作"],
        ["授权生命周期", "会话级、15分钟、1小时", "JIT授权是否仍有效"],
        ["版本", "manifest_id、version、proposal_hash", "审计记录本次调用依据的策略版本"],
    ]
    s.append(table(manifest, [35 * mm, 70 * mm, 71 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("当前仓库已交付开发Manifest设计器、能力集合、路径/网络范围及运行时持久化。自动从安全历史生成Manifest草案、组织级签名和跨设备灰度属于下一阶段，不写成当前已完成。"))
    s.append(callout("低误报机制", "推荐开发Manifest在内部370条开发工作流回归集中，将300条日常开发步骤的干扰率从无Manifest时的75%降到0%；这是内部合成回归结果，不是生产环境证明。", TEAL))
    page_break(s)

    s.append(SectionTitle("11", "Drift会话状态机", "语义证据进入状态机，但分数更新权不交给模型"))
    drift = [
        ["证据", "状态更新", "误报抑制"],
        ["轻微能力越界", "按固定权重累积", "同一意图修订去重"],
        ["相似风险重试", "按风险指纹累计重试惩罚", "普通参数变化不被误认成新攻击"],
        ["主题偏移", "闭集布尔标签进入固定加分", "单一低置信语义标签降权"],
        ["权限试探/请求升级", "组合证据提升会话风险", "需要能力、半径或历史信号共现"],
        ["免疫模式命中", "仅Active抗体增加有限分值", "单会话贡献封顶25，不能独立Block"],
        ["风险衰减", "按会话和冷却策略降低历史影响", "避免长期污染正常会话"],
    ]
    s.append(table(drift, [47 * mm, 57 * mm, 72 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("默认确认阈值40、阻断阈值80、总分上限100。阈值来自配置而非模型输出；无人值守模式可将Confirm升级为Block。"))
    s.append(P("实现与测试：<font color='#0B6BFF'>src/aegis/app/services/pretool_pipeline.py</font>；<font color='#0B6BFF'>tests/unit/app/test_pretool_pipeline.py</font>。"))
    page_break(s)

    s.append(SectionTitle("12", "闭集语义证据契约与Friction裁决", "把模型限制为不可信特征提取器，而不是安全控制器"))
    evidence = [
        ["模型可输出", "类型", "模型不可输出"],
        ["theme_shifted", "bool", "风险分数"],
        ["permission_probing", "bool", "确认/阻断阈值"],
        ["request_escalation", "bool", "最终Allow/Confirm/Block"],
        ["explicit_harm", "bool", "自由文本策略"],
        ["irreversible_impact", "预定义枚举", "动态工具、代码或副作用"],
        ["confidence band", "预定义枚举", "任意浮点权重"],
    ]
    s.append(table(evidence, [66 * mm, 42 * mm, 68 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("Friction合并原有单轮判定、Boundary、Capability、Radius和Drift：Critical硬边界优先；其余信号按固定决策表输出Allow、Confirm或Block。告警解释由模板生成，避免模型生成解释反向影响裁决。"))
    s.append(callout("失败语义", "模型超时、返回字段缺失或类型错误时，语义证据被丢弃，系统继续使用规则和现有会话状态。不同适配器的fail-open/fail-closed行为必须按部署模式明确配置。", ORANGE))
    page_break(s)

    s.append(SectionTitle("13", "JIT授权与可验证审计", "既减少频繁确认，也保留谁在何时批准了什么"))
    jit = [
        ["机制", "当前实现", "安全属性"],
        ["临时授权", "15分钟、1小时或当前会话", "到期自动失效，避免永久扩大权限"],
        ["授权作用域", "工具/能力与会话关联", "授权不能跨越未声明的对象范围"],
        ["审计记录", "事件、Verdict、原因、策略版本、前序哈希", "支持完整性验证和因果回放"],
        ["脱敏", "密钥、令牌和敏感字段在持久化前处理", "减少审计系统成为泄密源"],
        ["SIEM", "OCSF 1.3.0、Webhook、NDJSON及平台模板", "接入企业已有SOC流程"],
    ]
    s.append(table(jit, [35 * mm, 73 * mm, 68 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(callout("能力边界", "SHA-256哈希链主要用于发现事后文件级篡改。若攻击者控制系统并重写整条链，可靠检测需要外部锚定或受信任检查点；本项目不宣称哈希链能阻止运行时内存攻击。", RED))
    page_break(s)

    s.append(SectionTitle("14", "受治理免疫学习", "记住攻击序列，但不允许自动学习直接获得阻断权"))
    immune = [
        ["阶段", "行为", "是否影响裁决"],
        ["Candidate", "从完整会话提取工具、能力、半径和风险序列签名", "否"],
        ["Shadow", "记录新会话匹配、相似度和潜在贡献", "否"],
        ["Active", "人工批准后向Drift提供受限风险分", "是，但受上限约束"],
        ["Decaying", "命中减少或超时后逐步降低影响", "有限"],
        ["Retired", "撤销或过期，不再参与状态更新", "否"],
    ]
    s.append(table(immune, [34 * mm, 103 * mm, 39 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("免疫签名不保存原始敏感Prompt，单会话贡献默认最多25分，低于Confirm阈值40，因此不能单独触发Block。人工批准、Shadow验证、衰减和退役共同降低记忆投毒风险。"))
    s.append(callout("验证状态", "生命周期、审批和上限已实现；严格的train→shadow→独立test免疫增益实验尚未完成，因此本报告不宣称免疫学习已经提高公开Benchmark成绩。", ORANGE))
    page_break(s)

    s.append(SectionTitle("15", "安全运营Agent、证据RAG与多模态输入", "允许自然语言调查，但不给调查Agent任意执行权"))
    secops = [
        ["能力", "当前实现", "控制措施"],
        ["动态路由", "知识查询、事件调查、数据集评测、策略提案", "基于受控LangGraph节点，不开放动态工具注册"],
        ["闭集工具", "读取证据、会话时间线和哈希链验证", "无任意Shell和文件写权限"],
        ["证据处理", "TXT/Markdown/YAML/JSON/CSV/PDF/DOCX/截图OCR", "大小、页数、像素、超时、去重和脱敏限制"],
        ["混合检索", "章节切片、BM25、哈希向量、重排和引用", "回答必须附来源；引用存在不等于结论正确"],
        ["策略变更", "先模拟、生成提案哈希、人工审批、幂等应用", "模型不能自行修改运行时策略"],
        ["模型工程", "超时、重试、并发上限、调用预算和确定性降级", "避免单次调查消耗失控"],
    ]
    s.append(table(secops, [35 * mm, 79 * mm, 62 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("当前图片能力主要是OCR与安全截图证据提取，不等同于通用视觉理解；报告不把OCR描述为多模态大模型能力。"))
    page_break(s)

    s.append(SectionTitle("16", "运行时接入与覆盖矩阵", "每个适配器分别验收，不用“支持Agent”掩盖事件覆盖差异"))
    adapters = [
        ["运行时", "接入方式", "主要事件", "冻结版表述"],
        ["Claude Code", "原生插件/Hook", "UserPromptSubmit、PreToolUse、PostToolUse", "主要演示入口；可做执行前裁决"],
        ["OpenAI Codex", "原生插件", "工具调用与审计", "实现与HTTP E2E已归档"],
        ["Copilot CLI", "原生插件", "工具事件与版本探针", "实现存在；按CLI版本验收"],
        ["Cursor", "插件/Hook", "宿主提供的Hook事件", "Beta宿主，阻断语义需版本复核"],
        ["OpenClaw", "原生插件/Proxy", "LLM与工具事件", "可观测与阻断模式边界不同"],
        ["LangChain/LangGraph/CrewAI", "SDK或LLM Proxy", "框架/HTTP事件", "只有接入路径内流量受保护"],
        ["MCP", "Server与策略层", "工具定义、调用和结果", "覆盖已配置MCP路径"],
    ]
    s.append(table(adapters, [29 * mm, 38 * mm, 59 * mm, 50 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(callout("验收原则", "适配器完成度由“事件能否捕获、策略能否执行、失败语义是否明确、审计是否落盘”四项决定，而不是只看安装按钮是否存在。", BLUE))
    page_break(s)

    s.append(SectionTitle("17", "产品界面与演示闭环", "让评委在五分钟内看到正常任务、攻击、漂移和审计"))
    if TRACE_SCREENSHOT.exists():
        s.append(Image(str(TRACE_SCREENSHOT), width=176 * mm, height=49 * mm))
        s.append(P("图17-1　Agent Run Trace：按会话展示工具调用、Allow/Block结果与原因。", "CNTiny"))
    demo = [
        ["步骤", "操作", "应观察到的证据"],
        ["1", "连接Claude Code或Codex，加载推荐开发Manifest", "运行时、Manifest版本和会话ID可见"],
        ["2", "读取README、运行测试、项目内修改", "正常步骤Allow，低摩擦"],
        ["3", "尝试项目外写入或未知网络目的地", "Capability/Radius产生Confirm信号"],
        ["4", "触发高危命令或敏感数据外传", "Boundary Critical或证据堆叠Block"],
        ["5", "重复权限试探", "Drift分数、重试指纹和轮次证据累计"],
        ["6", "后台回放、验证哈希链并导出", "从告警回到完整因果链和策略版本"],
    ]
    s.append(table(demo, [18 * mm, 81 * mm, 77 * mm]))
    page_break(s)

    s.append(SectionTitle("18", "六项核心技术创新", "每项创新都有实现路径、可验证对象和明确边界"))
    innovations = [
        ["#", "创新", "技术贡献", "验证对象"],
        ["1", "会话级Drift", "连接原始任务、能力边界、范围变化和重复风险序列", "状态机测试与会话Trace"],
        ["2", "五段证据堆叠", "从内容边界移动到动作边界，逐层收集互补证据", "消融方案和机器报告"],
        ["3", "闭集语义契约", "LLM只填布尔/枚举槽位，不能返回分数和Verdict", "Schema验证、失败回退"],
        ["4", "Manifest安全契约", "把能力、目录、网络和影响范围变成运行时可执行契约", "设计器、模拟与版本记录"],
        ["5", "受治理免疫学习", "模式需Shadow与人工批准，贡献封顶且不能独立Block", "生命周期测试与审批记录"],
        ["6", "可验证审计与策略治理", "哈希链、提案哈希、模拟、审批和幂等应用", "链验证和策略变更日志"],
    ]
    s.append(table(innovations, [10 * mm, 39 * mm, 82 * mm, 45 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("这些创新不是六个孤立功能。它们共同实现一条可信控制链：<b>声明权限 → 捕获意图与行为 → 提取证据 → 累积会话状态 → 确定性裁决 → 记录与复核。</b>"))
    page_break(s)

    s.append(SectionTitle("19", "与直接DeepSeek Judge及纯规则方案的区别", "不是“多调用几次模型”，而是重新分配模型与代码的责任"))
    compare = [
        ["维度", "纯规则", "直接LLM Judge", "AI Aegis五段管线"],
        ["确定性风险", "强", "可识别但成本高", "规则优先"],
        ["模糊语义", "弱", "强", "LLM提取闭集证据"],
        ["多轮状态", "需额外实现", "通常把全文重新送入模型", "Drift状态机增量维护"],
        ["最终裁决", "代码", "模型", "固定决策表"],
        ["可复现性", "高", "受采样和模型版本影响", "核心裁决高，语义证据可审计"],
        ["延迟/成本", "低", "每次调用约秒级", "确定性路径低，语义按需异步/门控"],
        ["离线能力", "可", "不可", "核心可离线，语义增强可选"],
        ["解释与调参", "规则级", "通常是自然语言理由", "信号、权重、阈值、状态转移均可定位"],
    ]
    s.append(table(compare, [31 * mm, 39 * mm, 48 * mm, 58 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(callout("避免误区", "五段管线不是五层各调用一次DeepSeek；Drift不是让模型直接输出漂移分数；Friction不让模型决定阻断。", RED))
    page_break(s)

    s.append(SectionTitle("20", "技术主张到代码文件的可验证索引", "评委可以从报告直接回到仓库实现"))
    code = [
        ["技术主张", "实现文件", "主要验证"],
        ["五段式管线", "src/aegis/app/services/pretool_pipeline.py", "tests/unit/app/test_pretool_pipeline.py"],
        ["闭集语义证据", "src/aegis/app/services/semantic_evidence.py", "Schema/失败回退测试"],
        ["中文边界规则", "src/aegis/app/services/chinese_security_rules.py", "中文混淆与归一化用例"],
        ["运行时策略/Manifest", "src/aegis/app/server/routes/runtime_pipeline.py", "持久化、模拟与路由测试"],
        ["免疫学习", "src/aegis/app/services/immune_learning.py", "tests/unit/app/test_immune_learning.py"],
        ["JIT授权", "src/aegis/app/server/routes/jit_access.py", "授权生命周期测试"],
        ["哈希链审计", "src/aegis/app/database/migrations.py / repositories", "完整性验证与迁移测试"],
        ["证据处理", "src/aegis/app/services/evidence_processing.py", "文件类型、限制与脱敏测试"],
        ["安全运营Agent", "src/aegis/app/services/security_agent.py", "工具闭集、预算和审批测试"],
        ["安全RAG", "src/aegis/app/services/security_rag.py", "检索、重排和引用评测"],
        ["SIEM/OCSF", "src/aegis/app/services/siem_ocsf.py", "事件映射与转发测试"],
    ]
    s.append(table(code, [42 * mm, 82 * mm, 52 * mm]))
    page_break(s)

    s.append(SectionTitle("21", "工程规模与部署路径", "规模不作为创新替代品，但说明产品不是一次性演示脚本"))
    eng = [
        ["项目", "冻结快照事实", "说明"],
        ["核心技术栈", "Python / FastAPI / JavaScript / SQLite", "后端、策略、前端和本地存储"],
        ["测试文件", "104个Python测试文件、20个JavaScript测试文件", "文件数量不等于全部已在同一环境通过"],
        ["数据库Schema", "迁移版本47", "会话、审计、策略、免疫和控制面持续演进"],
        ["本地启动", "pip安装或源码运行，Web UI默认8741", "无DeepSeek Key也可启动核心能力"],
        ["容器", "Demo/Agent/控制平面Compose与Dockerfile", "本地曾缺Docker；服务器运行需单独验收"],
        ["平台", "Windows与Linux为主要目标", "不同插件依赖宿主版本"],
        ["数据默认", "本地优先、敏感字段脱敏、外发需配置", "模型增强开启后选定内容会发往提供商"],
    ]
    s.append(table(eng, [36 * mm, 75 * mm, 65 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(callout("版本已知问题", "冻结快照的包版本声明为1.0.2，但app内部、部分CLI和控制平面仍有1.0.1字符串。它不改变核心功能，但会影响交付一致性，发布前应统一为新补丁版本。", ORANGE))
    page_break(s)

    s.append(SectionTitle("22", "四层验证体系", "从自动化测试到公开Benchmark，再到真实开发工作流"))
    validation = [
        ["层级", "内容", "冻结证据", "可支持的结论"],
        ["L1", "单元、插件、UI和HTTP测试", "归档测试输出与仓库测试文件", "组件行为与接口合同"],
        ["L2", "公开安全Benchmark", "AgentHarm 352、InjecAgent 1,071", "同一离线网关合同下的检测、误报与延迟"],
        ["L3", "开发工作流回归", "日常300、合法敏感40、危险30", "Manifest对开发摩擦和危险控制的影响"],
        ["L4", "真实用户/企业试点", "尚无可公开的充分生产数据", "不能宣称生产误报率或企业采用"],
    ]
    s.append(table(validation, [17 * mm, 48 * mm, 61 * mm, 50 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("参考SubVersion的核心写法被保留：把验证分层，明确每层可以证明什么、不能证明什么。公开数据集结果不替代真实用户试用，内部回归不冒充第三方Benchmark。"))
    page_break(s)

    s.append(SectionTitle("23", "AgentHarm：同分片探索性优化结果", "352条公开样本：176攻击、176正常；候选工具未执行"))
    s.append(benchmark_chart())
    ah = [
        ["方案", "检出率", "正常误报率", "Precision", "F1", "P95延迟"],
        ["DeepSeek直接Judge", pct(AH_JUDGE["attack_detection_recall"]), pct(AH_JUDGE["benign_false_positive_rate"]), pct(AH_JUDGE["precision"]), pct(AH_JUDGE["f1"]), f"{AH_JUDGE['p95_latency_ms']:.2f} ms"],
        ["五段+DeepSeek+聚焦复核", pct(AH_FIVE["attack_detection_recall"]), pct(AH_FIVE["benign_false_positive_rate"]), pct(AH_FIVE["precision"]), pct(AH_FIVE["f1"]), f"{AH_FIVE['p95_latency_ms']:.2f} ms"],
    ]
    s.append(table(ah, [53 * mm, 26 * mm, 31 * mm, 23 * mm, 20 * mm, 31 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P(f"相对直接Judge，五段方案在该配置下检出率提高 {AH_FIVE['attack_detection_recall']*100-AH_JUDGE['attack_detection_recall']*100:.2f} 个百分点，正常误报率降低 {AH_JUDGE['benign_false_positive_rate']*100-AH_FIVE['benign_false_positive_rate']*100:.2f} 个百分点。"))
    s.append(callout("证据边界", "Pipeline默认值、聚焦复核门控和策略曾使用同一AgentHarm公开分片开发，因此该结果属于同分片探索性优化，不是独立泛化证明，也不能直接与论文Harm Score比较。", RED))
    page_break(s)

    s.append(SectionTitle("24", "InjecAgent：冻结配置跨数据集复测", "1,071条适配样本：1,054攻击、17正常；未按本轮结果调参"))
    ij = [
        ["方案", "检出率", "硬阻断率", "正常误报", "Precision", "F1", "P95"],
        ["DeepSeek直接Judge", pct(IJ_JUDGE["attack_detection_recall"]), pct(IJ_JUDGE["hard_prevention_rate"]), "0/17", pct(IJ_JUDGE["precision"]), pct(IJ_JUDGE["f1"]), f"{IJ_JUDGE['p95_latency_ms']:.2f}ms"],
        ["五段+DeepSeek证据", pct(IJ_FIVE["attack_detection_recall"]), pct(IJ_FIVE["hard_prevention_rate"]), "0/17", pct(IJ_FIVE["precision"]), pct(IJ_FIVE["f1"]), f"{IJ_FIVE['p95_latency_ms']:.2f}ms"],
    ]
    s.append(table(ij, [48 * mm, 24 * mm, 27 * mm, 25 * mm, 23 * mm, 18 * mm, 25 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("五段方案检出1,022/1,054条攻击，比直接Judge多4条；但更多风险被送入Confirm，硬阻断率从90.42%降为52.75%。这说明Friction强调分级处置，而不是以全部Block制造安全成绩。"))
    s.append(P("五段方案检出率 Wilson 95%区间为95.75%-97.84%。正常对照只有17条，0/17的95%区间仍可达到0%-18.43%，因此不能宣传总体误报率为零。", "CNBodySmall"))
    s.append(callout("跨集价值", "AgentHarm上冻结的单标签降权、证据堆叠和工具影响组合没有在间接提示注入数据上造成明显召回崩塌，但仓库历史曾接入InjecAgent，不能称为严格密封盲测。", ORANGE))
    page_break(s)

    s.append(SectionTitle("25", "开发工作流回归：安全与可用性必须同时报告", "370条内部合成样本，不调用LLM、不执行命令"))
    dev_rows = [
        ["策略配置", "日常干扰率", "日常硬阻断率", "敏感复核率", "危险保护率"],
        ["无Manifest", "75.00%", "21.67%", "80.00%", "100.00%"],
        ["本地开发Manifest", "16.67%", "3.33%", "10.00%", "70.00%"],
        ["推荐开发Manifest", "0.00%", "0.00%", "0.00%", "70.00%"],
    ]
    s.append(table(dev_rows, [50 * mm, 32 * mm, 34 * mm, 31 * mm, 29 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("该结果证明Manifest能显著改变开发摩擦，但同时暴露两个缺口：推荐Manifest下有40个合法敏感动作未复核，且9个高风险混淆执行样本未干预。因此下一步应细化Shell、Git、网络和目标级策略，而不是继续扩大能力白名单。"))
    s.append(callout("不可越界的结论", "这是一套项目内部工程回归集，不是第三方公共Benchmark，也不是生产环境误报率证明。它用于固定策略回归和比较Manifest配置。", RED))
    page_break(s)

    s.append(SectionTitle("26", "自动化、安装与运行证据", "把“能跑”拆成安装、启动、接口、插件和安全不变量"))
    tests = [
        ["证据", "归档结果", "口径"],
        ["默认Python测试", "1,071 passed / 6 skipped / 191 deselected（2026-09-10归档）", "默认配置明确排除integration标记"],
        ["插件与UI测试", "216项归档结果；另有14项HTTP E2E记录", "不同运行日期和范围，不能相加成一次测试"],
        ["干净环境安装", "Python 3.14新venv安装、启动、/health与凭据往返成功", "归档commit 4acffee，不等同当前HEAD复测"],
        ["无API Key启动", "核心服务可启动，key_source为none", "语义增强不可用，但规则/审计可用"],
        ["扩展integration", "仍存在失败和环境错误", "不能宣称全部测试通过"],
        ["容器", "Compose静态解析与轻量服务器Demo路径", "完整Ubuntu资源限制与恢复验收仍需独立记录"],
    ]
    s.append(table(tests, [36 * mm, 76 * mm, 64 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("本报告优先引用机器原始输出，而不是把README宣传数字当作测试证据。所有测试数字必须附日期、commit和运行范围。"))
    page_break(s)

    s.append(SectionTitle("27", "当前限制与已实施缓解", "一等奖材料的可信度来自知道系统不能做什么"))
    limits = [
        ["当前限制", "已实施缓解", "下一步验证"],
        ["AgentHarm正常误报仍为16.48%", "证据降权、组合门控、聚焦复核", "独立validation/test切分与真实开发轨迹"],
        ["规则-only难以识别语义型攻击", "可选DeepSeek证据与本地Guardian", "独立语义模型、超时与迟到证据测量"],
        ["不同宿主的确认/阻断语义不一致", "适配器独立路由和headless升级策略", "按版本建立宿主兼容矩阵"],
        ["推荐Manifest仍漏掉部分高风险动作", "Critical规则和范围信号仍保留", "Shell/Git/网络动作级策略"],
        ["哈希链不能抵御整链重写", "链完整性验证与可选SIEM转发", "签名检查点和外部锚定"],
        ["企业级身份、租户、高可用未完成", "本地UI Token和轻控制面原型", "SSO/RBAC、租户隔离、恢复演练"],
        ["真实用户证据不足", "内部回归、公开Benchmark和安装归档", "高校实验室/团队试点与匿名指标"],
    ]
    s.append(table(limits, [48 * mm, 62 * mm, 66 * mm]))
    page_break(s)

    s.append(SectionTitle("28", "开源治理与合规", "二次开发的创新必须建立在透明归属和可持续贡献机制上"))
    governance = [
        ["治理项", "当前状态", "一等奖提交动作"],
        ["许可证", "Apache License 2.0", "保留根LICENSE与插件副本"],
        ["上游归属", "NOTICE记录来源、版权与变更", "禁止因品牌替换删除法定归属"],
        ["安全披露", "SECURITY.md", "明确支持版本、报告渠道和响应流程"],
        ["依赖合规", "requirements/setup及来源记录", "生成依赖许可清单与SBOM"],
        ["贡献机制", "文档和仓库基础存在", "补齐CONTRIBUTING、行为准则、Issue/PR模板"],
        ["版本治理", "Git提交与Benchmark实现/配置哈希", "创建赛事冻结标签和Release说明"],
        ["数据集许可", "报告记录数据来源与许可", "提交时附数据只用于安全研究的限制"],
    ]
    s.append(table(governance, [36 * mm, 67 * mm, 73 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("项目的独立贡献主要包括五段管线、中文安全规则、会话状态、Manifest治理、安全运营与评测体系；上游代码和模型资产不被重新表述为团队原创。"))
    page_break(s)

    s.append(SectionTitle("29", "社区版与企业版产品路线", "社区版形成实验框架和反馈入口，企业版围绕组织级治理与服务收费"))
    editions = [
        ["能力", "Community / Academic", "Team（规划）", "Business / Enterprise（规划）"],
        ["运行时", "本地规则、Guardian、五段管线", "共享策略与设备视图", "中央编排、灰度与例外治理"],
        ["Manifest", "单机设计器和预设", "团队模板、版本共享", "组织签名、审批链与策略继承"],
        ["审计", "本地哈希链和导出", "团队留存与查询", "长期留存、跨设备关联和合规报表"],
        ["身份", "本地UI Token", "团队账号", "SSO、RBAC与租户隔离"],
        ["部署", "本地/轻量Docker", "托管或单租户", "私有化、高可用和灾备"],
        ["支持", "社区文档", "基础支持", "SLA、实施、定制和安全评估"],
    ]
    s.append(table(editions, [32 * mm, 47 * mm, 45 * mm, 52 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(callout("商业边界", "当前可交付的是社区版原型和轻量Demo。Team与Enterprise列为产品路线，不得在答辩中称为已上线企业版本。", RED))
    page_break(s)

    s.append(SectionTitle("30", "盈利模式与保守收入情景", "收入数字是可检验假设，不是合同、利润或估值"))
    business = [
        ["收入来源", "建议价格", "交付内容"],
        ["Community / Academic", "免费开源", "单机治理、基础插件、实验框架和社区文档"],
        ["Team订阅", "499美元/团队/年（计划）", "策略共享、团队审计、基础支持"],
        ["安全评估", "2,000-5,000美元/次（假设）", "Agent接入评估、Manifest梳理和风险报告"],
        ["私有化部署", "12,000美元起/年（假设）", "控制面、组织集成、部署与升级"],
        ["专业服务", "按项目报价", "适配器、规则、合规报表和培训"],
    ]
    s.append(table(business, [43 * mm, 47 * mm, 86 * mm]))
    s.append(Spacer(1, 5 * mm))
    forecast = [
        ["完整商业年", "Team订阅", "评估/试点", "企业部署/服务", "年度情景收入"],
        ["Year 1", "20×$499=$9,980", "3×$2,000=$6,000", "$0", "$15,980"],
        ["Year 2", "75×$499=$37,425", "8×$5,000=$40,000", "$0", "$77,425"],
        ["Year 3", "200×$499=$99,800", "$30,000", "15×$12,000=$180,000", "$309,800"],
    ]
    s.append(table(forecast, [34 * mm, 38 * mm, 37 * mm, 42 * mm, 33 * mm]))
    s.append(P("上述情景未扣除模型、服务器、销售、支持和交付成本；没有真实签约数据时，不可作为估值或盈利承诺。", "CNBodySmall"))
    page_break(s)

    s.append(SectionTitle("31", "市场进入与验证路线", "先证明有人能装、愿意用、干扰可控，再扩大组织能力"))
    gtm = [
        ["阶段", "目标对象", "动作", "验收指标"],
        ["开源验证", "开发者与高校实验室", "发布快速开始、实验模板和复现Benchmark", "安装成功、真实Issue/PR、匿名轨迹"],
        ["团队试点", "初创与小型Agent团队", "提供Manifest梳理和安全评估", "日常干扰<5%、高危覆盖、支持工时"],
        ["产品验证", "有自研Agent的企业部门", "单租户私有化试点", "身份、隔离、恢复和审计验收"],
        ["规模化", "企业AI平台与安全团队", "控制面、SIEM/SOC和合规集成", "续费、扩设备、SLA与合规复核"],
    ]
    s.append(table(gtm, [31 * mm, 42 * mm, 66 * mm, 45 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("开源社区不是获客装饰，而是发现适配器边界、真实误报和新攻击序列的核心反馈渠道。企业收费点则集中在组织身份、策略协作、私有部署、审计留存和专业服务。"))
    page_break(s)

    s.append(SectionTitle("32", "未来12个月路线图", "冻结当前能力后，下一阶段只接受有明确验收结果的工作"))
    roadmap = [
        ["时间", "主题", "可验收交付"],
        ["2026 Q4", "冻结与参赛", "统一版本、创建Release、复现实验、演示视频、SBOM和贡献指南"],
        ["2027 Q1", "端到端评测", "AgentDojo/真实开发Harness，同一模型下报告ASR、Utility、误报和延迟"],
        ["2027 Q2", "真实试点", "至少1个高校实验室与3-5名开发者，匿名记录≥1,000次工具调用"],
        ["2027 Q2", "细粒度策略", "Shell/Git/网络目标级策略，Audit/Balanced/Strict三档模式"],
        ["2027 Q3", "团队产品", "共享Manifest、设备策略、审计留存和支持流程，验证499美元年费"],
        ["2027 Q4", "企业试点", "SSO/RBAC、租户隔离、恢复演练和SIEM闭环"],
    ]
    s.append(table(roadmap, [29 * mm, 44 * mm, 103 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("每个阶段都同时约束安全收益与正常任务损失。只有召回上升而误报、确认次数或任务失败同步恶化的方案，不能被视为产品进步。"))
    page_break(s)

    s.append(SectionTitle("33", "社会价值与开源生态价值", "让高校、个人开发者和中小团队也能获得可验证的Agent安全能力"))
    values = [
        ["价值", "具体表现"],
        ["安全普惠", "核心能力本地、开源、无需注册或云账号，降低Agent安全实验门槛"],
        ["教育与科研", "五层信号、数据集回放和可解释状态机适合课程、毕设和攻防实验"],
        ["隐私保护", "本地优先、持久化前脱敏、外发需管理员配置"],
        ["开源协作", "适配器、规则和Manifest模板可由不同Agent社区共同维护"],
        ["产业治理", "为企业自研Agent提供可执行权限契约和可追溯审计，而不是只提供内容审核"],
        ["标准化潜力", "Manifest、Signal[]、Trace和审计事件可逐步形成跨Agent治理接口"],
    ]
    s.append(table(values, [42 * mm, 134 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(P("项目希望建立一套可讨论、可复现、可贡献的Agent安全工程语言：能力、影响半径、漂移、摩擦和证据。它的长期价值不依赖某一个大模型供应商。"))
    page_break(s)

    s.append(SectionTitle("34", "一等奖答辩主线", "评委只需要记住三个创新、一个闭环和一组诚实数据"))
    pitch = [
        ["要点", "答辩表达", "现场证据"],
        ["创新一", "LLM只提取闭集证据，代码维护状态并裁决", "Schema与五段管线代码"],
        ["创新二", "Manifest把Agent权限变成运行时安全契约", "设计器、策略模拟和开发回归"],
        ["创新三", "意图流与行为流组成会话级因果链", "多轮攻击、Drift曲线和Trace回放"],
        ["产品闭环", "接入→正常开发→风险确认/阻断→审计复核", "五分钟演示"],
        ["实测数据", "AgentHarm、InjecAgent和370条开发工作流", "机器JSON、配置哈希和报告"],
        ["可信边界", "主动说明离线重放、正常样本量和未完成企业能力", "限制章节与冻结声明"],
    ]
    s.append(table(pitch, [29 * mm, 87 * mm, 60 * mm]))
    s.append(Spacer(1, 6 * mm))
    s.append(callout("核心句", "我们不是用另一个大模型替代安全策略，而是让模型只能提供证据，让确定性系统掌握阻断权。", BLUE))
    page_break(s)

    s.append(SectionTitle("35", "五分钟现场演示脚本", "所有展示都必须可回到实际代码和审计记录"))
    script = [
        ["时间", "操作", "讲解重点"],
        ["0:00-0:30", "打开仪表盘与会话安全页", "项目定位、本地优先、当前连接运行时"],
        ["0:30-1:20", "执行README读取、测试和项目内写入", "推荐Manifest下正常开发Allow"],
        ["1:20-2:10", "尝试项目外写入与未知域名访问", "Capability/Radius将模糊风险送入Confirm"],
        ["2:10-3:00", "触发敏感信息外传或高危Shell", "Boundary和Friction在执行前Block"],
        ["3:00-3:50", "连续权限试探", "Drift状态按轮次积累，不是模型直接给分"],
        ["3:50-4:30", "打开Agent Run Trace和证据详情", "从Verdict回到规则、标签、Manifest和请求"],
        ["4:30-5:00", "验证哈希链并展示Benchmark", "可验证证据、数据边界和下一步试点"],
    ]
    s.append(table(script, [28 * mm, 69 * mm, 79 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("演示失败预案：保留预生成的安全会话、审计导出和机器报告；不得用视频替代所有现场操作，也不得在网络不稳定时临时修改阈值制造结果。"))
    page_break(s)

    s.append(SectionTitle("36", "复现命令与证据入口", "让评委能够在仓库中重复核心结果"))
    reproduce = [
        ["任务", "命令/路径"],
        ["本地启动", "PYTHONPATH=src python -m aegis.app.main --web --port 8741 --proxy --mode analyze"],
        ["默认测试", "pytest tests/（默认排除integration标记，以pyproject配置为准）"],
        ["公开Benchmark", "scripts/run_external_benchmarks.py --benchmarks injecagent agentharm"],
        ["AgentHarm机器报告", AGENTHARM_PATH],
        ["InjecAgent机器报告", INJEC_PATH],
        ["开发工作流", DEV_PATH],
        ["五段设计", "docs/FIVE_STAGE_PRETOOL_PIPELINE.md"],
        ["验收边界", "docs/COMPETITION_ACCEPTANCE.md"],
        ["部署手册", "docs/SECURITY_AGENT_RUNBOOK.md / docs/SELF_HOSTED_CONTROL_PLANE.md"],
        ["开源合规", "LICENSE / NOTICE / SECURITY.md"],
    ]
    s.append(table(reproduce, [42 * mm, 134 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("候选危险工具只做离线重放，不在Benchmark中真实执行。运行付费语义基线需要显式配置模型密钥和费用预算；密钥不得写入仓库或报告。", "CNBodySmall"))
    page_break(s)

    s.append(SectionTitle("37", "数据与结论合规清单", "避免最容易导致评审失信的八类表述"))
    forbidden = [
        ["禁止表述", "正确写法"],
        ["五段管线全面优于所有Judge", "在指定冻结配置和离线网关合同下，与同次DeepSeek响应比较"],
        ["误报率为0%", "InjecAgent正常对照0/17；样本不足以证明总体为零"],
        ["100%攻击防御", "区分检出、Confirm、硬阻断和原生Agent攻击成功率"],
        ["全部测试通过", "分别报告默认、插件/UI、HTTP和扩展integration范围"],
        ["已完成企业版", "当前为社区版/轻量原型；企业能力为路线图"],
        ["已有企业客户和收入", "如无合同，只报告试点计划、定价假设和访谈"],
        ["论文已发表/录用", "如无正式录用，仅称研究稿或工作稿"],
        ["完全自主原创", "明确Apache-2.0上游来源与团队新增模块"],
    ]
    s.append(table(forbidden, [67 * mm, 109 * mm]))
    page_break(s)

    s.append(SectionTitle("38", "最终结论与提交信息", "一个可运行、可测试、可解释、可演进的开源Agent安全工具"))
    s.append(P("AI Aegis 已从单轮威胁检测扩展为包含运行时权限、会话漂移、分层裁决、Manifest安全契约、可验证审计和安全运营的完整原型。项目最有竞争力的地方不是页面数量，而是把语义证据与安全控制权分开，并用公开数据和开发工作流同时衡量安全与可用性。"))
    pillars = Table([
        [P("可运行", "CNSub"), P("可测试", "CNSub"), P("可解释", "CNSub"), P("可治理", "CNSub")],
        [P("插件、后台、本地与轻量部署", "CNBodySmall"), P("机器报告、配置哈希和复现入口", "CNBodySmall"), P("Signal、状态、阈值和Verdict可追溯", "CNBodySmall"), P("Manifest、JIT、审批和审计闭环", "CNBodySmall")],
    ], colWidths=[44 * mm] * 4)
    pillars.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9F3FF")),
        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    s.append(pillars)
    s.append(Spacer(1, 8 * mm))
    info = [
        ["项目", "AI Aegis（灵盾）：面向企业自研Agent的开源运行时安全治理与可观测平台"],
        ["赛道", "开源 AI 工具赛道 - AI 编程、调试与可观测工具 - 自主选题"],
        ["负责人", "万翔浩"],
        ["仓库", "GitHub: https://github.com/Goodevenin9/ai-aegis<br/>Gitee: https://gitee.com/wan-xianghao/ai-aegis"],
        ["许可证", "Apache License 2.0；上游来源和变更见NOTICE"],
        ["冻结", f"{FREEZE_DATE} / Git {SNAPSHOT}"],
    ]
    s.append(table(info, [34 * mm, 142 * mm], header=False))
    s.append(Spacer(1, 6 * mm))
    s.append(callout("最终声明", "本报告按一等奖评审标准组织证据，但不保证奖项。所有当前能力、实验数字、规划和商业假设均按证据等级区分，评委可沿附录入口逐项核查。", BLUE))
    page_break(s)

    s.append(SectionTitle("附A", "Benchmark机器数据摘要", "关键运行元数据、样本和结果均来自已跟踪JSON"))
    meta = [
        ["字段", "AgentHarm", "InjecAgent"],
        ["生成时间", AGENTHARM["run_metadata"]["generated_at"], INJEC["run_metadata"]["generated_at"]],
        ["实现commit", AGENTHARM["run_metadata"]["aegis_commit"][:12], INJEC["run_metadata"]["aegis_commit"][:12]],
        ["工作区", "clean" if not AGENTHARM["run_metadata"]["aegis_worktree_dirty"] else "dirty", "clean" if not INJEC["run_metadata"]["aegis_worktree_dirty"] else "dirty"],
        ["模型", AGENTHARM["run_metadata"]["deepseek"]["model"], INJEC["run_metadata"]["deepseek"]["model"]],
        ["主响应", str(AGENTHARM["run_metadata"]["deepseek"]["primary_responses"]), str(INJEC["run_metadata"]["deepseek"]["primary_responses"])],
        ["聚焦复核", str(AGENTHARM["run_metadata"]["deepseek"]["focused_verifier_responses"]), str(INJEC["run_metadata"]["deepseek"]["focused_verifier_responses"])],
        ["失败", str(AGENTHARM["run_metadata"]["deepseek"]["failed_samples"]), str(INJEC["run_metadata"]["deepseek"]["failed_samples"])],
        ["估算成本", f"${AGENTHARM['run_metadata']['deepseek']['estimated_cost_usd']:.6f}", f"${INJEC['run_metadata']['deepseek']['estimated_cost_usd']:.6f}"],
        ["工具执行", AGENTHARM["run_metadata"]["tool_execution"], INJEC["run_metadata"]["tool_execution"]],
    ]
    s.append(table(meta, [37 * mm, 69 * mm, 70 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("Direct Judge与五段方案复用同一条主响应；五段方案只为命中门控的样本增加聚焦布尔复核。这样降低了模型响应差异对方案比较的干扰，但仍不能消除同分片开发带来的校准偏差。", "CNBodySmall"))
    page_break(s)

    s.append(SectionTitle("附B", "术语表", "统一评委、开发者和安全人员使用的概念"))
    glossary = [
        ["术语", "定义"],
        ["PreTool", "工具真正执行前的拦截与裁决点"],
        ["Boundary", "确定性硬边界与规范化检测层"],
        ["Capability", "Agent在当前会话中获准使用的能力集合"],
        ["Radius", "工具调用可能影响的项目、本机、用户、系统或外部范围"],
        ["Drift", "跨轮次累积的行为偏离与风险状态"],
        ["Friction", "综合证据后输出Allow/Confirm/Block的唯一最终裁决层"],
        ["Manifest", "声明Agent能力、路径、网络和动作范围的运行时安全契约"],
        ["闭集语义证据", "只接受预定义布尔和枚举字段，不接受自由分数和Verdict"],
        ["受治理免疫", "需Shadow与人工批准、贡献封顶、不能独立Block的模式记忆"],
        ["哈希链", "每条记录包含前序摘要，用于发现链内不一致修改"],
        ["SCOPED", "只在已接入且已验收的事件与工具边界内提供控制"],
    ]
    s.append(table(glossary, [48 * mm, 128 * mm]))
    page_break(s)

    s.append(SectionTitle("附C", "提交清单与答辩证据索引", "提交前逐项勾选，避免材料与代码版本错位"))
    checklist = [
        ["项目", "状态", "验收方式"],
        ["公开代码仓库可访问", "待提交前复核", "无密钥、LICENSE/NOTICE完整、冻结标签存在"],
        ["安装与启动", "已有归档", "陌生环境按README完成安装、/health通过"],
        ["五分钟演示", "脚本已定义", "正常Allow、范围Confirm、高危Block、Trace与审计"],
        ["Benchmark复现", "机器报告已归档", "固定commit、数据哈希、配置哈希与模型"],
        ["作品介绍PDF", "本报告", "背景、架构、场景、创新、验证、治理与路线齐全"],
        ["演示视频", "已有历史视频，需核对版本", "画面、字幕、语音与冻结UI一致"],
        ["用户/试点证据", "不足", "不得用生成评价替代真实记录"],
        ["版本一致性", "需修复", "包、app、CLI、控制面和文档统一补丁版本"],
        ["赛事报名", "人工完成", "截止日期、邮箱、联系人和线下路演信息复核"],
    ]
    s.append(table(checklist, [52 * mm, 34 * mm, 90 * mm]))
    s.append(Spacer(1, 5 * mm))
    s.append(P("本附录中的“待复核/需修复”不会因为报告完成而自动变为通过。冻结的价值正是防止材料继续漂移，并把剩余风险显式交给提交负责人。"))
    return s


def build_pdf() -> None:
    DELIVERY.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="AI Aegis 完整项目报告 - 2026上海开源软件应用创新大赛",
        author="万翔浩",
        subject="开源AI工具赛道一等奖冲刺材料 - 冻结版",
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
