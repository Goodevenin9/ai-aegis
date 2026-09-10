"""Run a real-model investigation in an isolated temporary database."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.security_operations import SecurityOperationsRepository
from aegis.app.services.evidence_processing import EvidenceProcessor
from aegis.app.services.security_agent import AgentTask, SecurityAnalystAgent


async def run() -> None:
    with tempfile.TemporaryDirectory(prefix="aegis-agent-smoke-") as folder:
        db = DatabaseConnection(Path(folder) / "agent.db")
        try:
            await run_migrations(db)
            repo = SecurityOperationsRepository(db)
            evidence = await repo.save_evidence(EvidenceProcessor().process(
                "synthetic-incident.txt",
                "演示记录：用户只要求总结 README。工具尝试将项目文件发送到外部地址。安全网关已拒绝，未发生外发。".encode(),
            ))
            agent = SecurityAnalystAgent(repo)
            result = await agent.start(AgentTask(
                query="帮我看看这个智能体是不是被带偏了，请依据记录解释，不要编造。",
                evidence_ids=(evidence["evidence_id"],),
            ))
            status = agent.model.primary.status()
            if result["status"] != "completed" or result["result"].get("degraded"):
                print(json.dumps({"status": result["status"], "model": status,
                                  "error": result.get("error"), "result": result.get("result")}, ensure_ascii=False))
                raise RuntimeError("Live Agent smoke failed or degraded")
            if result["result"].get("model_mode") != "deepseek":
                raise RuntimeError("Real model was not used")
            output = ROOT / "reports" / "delivery" / "agent-live-smoke.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"model": status, "run": result,
                                           "scope": "synthetic isolated evidence, no tools executed"},
                                          ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"status": result["status"], "model": status,
                              "task_type": result["state"]["task_type"],
                              "citations": len(result["result"]["citations"]),
                              "report": str(output)}, ensure_ascii=False))
        finally:
            await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    args = parser.parse_args()
    os.environ["AEGIS_DEEPSEEK_API_KEY_FILE"] = str(args.key_file.resolve())
    asyncio.run(run())
