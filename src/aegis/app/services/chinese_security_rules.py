"""High-precision Chinese Boundary signals for multi-turn Agent attacks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChineseBoundaryMatch:
    code: str
    severity: Literal["medium", "high", "critical"]
    message: str


_DEFENSIVE_CONTEXT = re.compile(
    r"(?:如何|怎么|怎样|用于|为了|请|需要)?(?:防止|防范|检测|识别|阻止|禁止|避免|修复|审计)"
    r".{0,18}(?:越狱|注入|绕过|提权|窃取|泄露|删除审计)|"
    r"(?:不要|不得|禁止|切勿).{0,18}(?:绕过|忽略|泄露|窃取|删除|关闭)|"
    r"(?:解释|说明).{0,12}(?:为什么|为何).{0,8}(?:不能|不应|不可以).{0,12}"
    r"(?:绕过|忽略|泄露|窃取|删除|关闭)",
    re.I,
)

_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("instruction_override", r"忽略.{0,16}(?:之前|以上|系统).{0,16}(?:指令|规则|要求)", "high", "Instruction override attempt"),
    ("safety_bypass", r"绕过.{0,16}(?:安全|权限|限制|审计|策略|防护)", "high", "Security control bypass request"),
    ("covert_action", r"(?:不要|无需).{0,10}(?:告诉|通知|记录|留下).{0,12}(?:用户|管理员|日志|痕迹)", "high", "Covert action request"),
    ("unrestricted_role", r"(?:进入|切换到|启用).{0,10}(?:开发者|无限制|无审查|越狱).{0,6}模式", "high", "Unrestricted role request"),
    ("pretend_no_policy", r"(?:假装|设想|模拟).{0,12}(?:没有|不存在|不受).{0,12}(?:安全|规则|权限|限制)", "high", "Policy-removal role play"),
    ("privilege_escalation", r"(?:获取|提升|取得|申请).{0,12}(?:root|管理员|系统|最高).{0,8}(?:权限|权限级别|访问权)", "high", "Privilege escalation request"),
    ("credential_access", r"(?:读取|导出|查找|窃取|获取).{0,16}(?:密钥|口令|密码|令牌|token|凭据|私钥)", "high", "Credential access request"),
    ("audit_erasure", r"(?:清除|删除|覆盖|篡改|关闭).{0,12}(?:审计|安全|操作).{0,6}(?:日志|记录|告警)", "critical", "Audit evidence destruction request"),
    ("evasion_encoding", r"(?:编码|加密|分段|拆分|变形).{0,16}(?:绕过|逃避|避开).{0,12}(?:检测|审计|规则|过滤)", "high", "Detection evasion through obfuscation"),
    ("staged_attack", r"(?:分步|逐步|一轮一轮).{0,16}(?:提权|绕过|获取权限|扩大范围)", "high", "Staged privilege expansion"),
    ("data_exfiltration", r"(?:上传|发送|外传|转发).{0,18}(?:密钥|凭据|隐私|数据库|用户数据).{0,18}(?:外部|公网|服务器|接口|网站)?", "high", "Sensitive-data exfiltration request"),
)


def match_chinese_boundary(text: str) -> tuple[ChineseBoundaryMatch, ...]:
    """Return matches, suppressing only rules covered by defensive wording."""

    if not text:
        return ()
    defensive_spans = [match.span() for match in _DEFENSIVE_CONTEXT.finditer(text)]
    matches = []
    for suffix, pattern, severity, message in _RULES:
        hits = list(re.finditer(pattern, text, re.I))
        risky_hit = next(
            (
                hit for hit in hits
                if not any(start <= hit.end() and end >= hit.start() for start, end in defensive_spans)
            ),
            None,
        )
        if risky_hit:
            matches.append(
                ChineseBoundaryMatch(
                    code=f"boundary.zh.{suffix}",
                    severity=severity,  # type: ignore[arg-type]
                    message=message,
                )
            )
    return tuple(matches)


__all__ = ["ChineseBoundaryMatch", "match_chinese_boundary"]
