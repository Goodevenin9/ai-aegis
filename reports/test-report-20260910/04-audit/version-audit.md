# 版本号自证审计
采集时间: 2026-09-10T22:54:09+08:00
采集对象: 源码工作区（未提交状态，HEAD=4acffee）

## 结论
产品版本号共 5 处，1.0.2 升级时只改了 1 处，其余 4 处仍停在 1.0.1。

## 源码中所有版本号字面量
```
src/aegis/app/utils/platform.py:279:    plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
src/aegis/app/utils/platform.py:281:<plist version="1.0">
src/aegis/app/__init__.py:21:__version__ = "1.0.1"
src/aegis/control_plane/app.py:96:        version="1.0.1",
src/aegis/models/policy_models.py:136:            version="1.0.0",
src/aegis/models/policy_models.py:194:            version="1.0.0",
src/aegis/models/policy_models.py:236:            version="1.0.0",
src/aegis/__init__.py:74:__version__ = "1.0.2"
src/aegis/cli.py:50:            "--version", action="version", version="Aegis AI Threat Monitor 1.0.1"
src/aegis/cli_enhanced.py:55:            "--version", action="version", version="Aegis Enhanced CLI 1.0.1"
```

## 装机后各入口自报值（来自干净 venv 安装的 1.0.2）
```
pip 安装的版本      : 1.0.2  (dist-info: ai_aegis-1.0.2.dist-info)
import aegis        : 1.0.2  (src/aegis/__init__.py:74)   ← 唯一正确
import aegis.app    : 1.0.1  (src/aegis/app/__init__.py:21) ← /health 取这里
/health             : 1.0.1
aegis --version     : Aegis AI Threat Monitor 1.0.1  (src/aegis/cli.py:50)
aegis-app --version : Aegis Local Threat Monitor v1.0.1 (src/aegis/cli_enhanced.py:55)
控制面 FastAPI      : 1.0.1  (src/aegis/control_plane/app.py:96)
```

## 影响
runbook 与 README 都把 /health 列为验证动作。测试者装 1.0.2 后看到 1.0.1，
无法区分「装错了」与「版本声明不实」。

## 修复代价
PyPI 同版本内容不可修改，修正这 4 处必须发布 1.0.3。
