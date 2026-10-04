# 内置规则数审计
采集时间: 2026-09-10T22:54:10+08:00

## 结论
README 三处写 72 条，实际为 108 条。源文件逐条统计与运行时 /health 一致。

## 源文件逐条统计（YAML 解析）
```
  14  aegis_community_data_extraction.yml
   5  aegis_community_essential_patterns.yml
  22  aegis_community_evasion_attempts.yml
   3  aegis_community_harmful_content.yml
  12  aegis_community_indirect_prompt_injection.yml
   6  aegis_community_jailbreak_attempts.yml
   7  aegis_community_output_leakage.yml
   4  aegis_community_pii_detection.yml
  10  aegis_community_prompt_injection.yml
   3  aegis_community_social_engineering.yml
  13  mitre_patterns.yml
   9  owasp_top10.yml
----------------------------------------
 108  合计
```

## 运行时自报
```
/health → rules_loaded: {"community": 108, "custom": 0, "compiled_patterns": 423}
```

## README 中的错误口径
```
14:- **Catch the threats — 72 rules + Guardian ML.** OWASP LLM Top 10 + 28 agent-attack chains, detected while the agent is still running. Offline ML catches what regex misses. [Details ↓](#optional-ml-detection-layer--aegis-guardian)
55:> - **威胁检测**：72 条规则 + Guardian ML 检测层，覆盖提示注入、数据泄露、越狱攻击等 OWASP LLM Top 10 威胁
164:Scans every prompt, response, and natural-language tool input for prompt injection (direct + indirect), jailbreaks, PII leaks, credential exfiltration, and tool-result injection. 72 rules covering the OWASP LLM Top 10 + 28 agent-attack chains. Monitor by default; opt-in block mode for hard-stop.
```
