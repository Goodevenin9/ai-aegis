"""
Logging utilities for the AI Threat Monitor SDK.

Copyright (c) 2025 SecureVector
Copyright (c) 2026 Aegis (derived work; see NOTICE)
Licensed under the Apache License, Version 2.0
"""

import logging
import sys
from typing import Optional

from aegis.models.config_models import LogLevel


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability"""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        # Add color to level name
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}" f"{self.COLORS['RESET']}"
            )

        # Format the message
        formatted = super().format(record)

        # Add emoji indicators for key message types
        if "THREAT DETECTED" in formatted or "🚨" in formatted:
            formatted = f"🚨 {formatted}"
        elif "✅" in formatted or "Clean prompt" in formatted:
            formatted = f"✅ {formatted}"
        elif "⚡" in formatted or "Enhanced" in formatted:
            formatted = f"⚡ {formatted}"

        return formatted


def get_logger(name: str, level: LogLevel = LogLevel.INFO) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Logging level

    Returns:
        logging.Logger: Configured logger
    """
    logger = logging.getLogger(name)

    # Convert LogLevel enum to logging level
    log_level_map = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
        LogLevel.CRITICAL: logging.CRITICAL,
    }

    logger.setLevel(log_level_map.get(level, logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler - use stderr to avoid breaking MCP stdio communication
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level_map.get(level, logging.INFO))

    # Create formatter
    formatter = ColoredFormatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to avoid duplicate messages
    logger.propagate = False

    return logger


class SecurityLogger:
    """Specialized logger for security events"""

    def __init__(self, name: str = "Aegis", level: LogLevel = LogLevel.INFO):
        self.logger = get_logger(name, level)
        self.session_stats = {"requests": 0, "threats": 0, "blocks": 0}

    def log_threat(
        self,
        threat_type: str,
        risk_score: int,
        description: str,
        analysis_time_ms: float,
        action: str = "detected",
    ) -> None:
        """Log a security threat"""
        self.session_stats["threats"] += 1
        if action == "blocked":
            self.session_stats["blocks"] += 1

        self.logger.warning(
            f"🚨 THREAT {action.upper()}: {threat_type} "
            f"(Risk: {risk_score}/100, {analysis_time_ms:.1f}ms) - {description}"
        )

    def log_clean_request(self, analysis_time_ms: float, method: str = "local") -> None:
        """Log a clean request"""
        self.session_stats["requests"] += 1
        self.logger.info(f"✅ Request analyzed (Clean - {analysis_time_ms:.1f}ms, {method})")

    def log_performance(self, operation: str, duration_ms: float, success: bool = True) -> None:
        """Log performance metrics"""
        status = "✅" if success else "❌"
        self.logger.debug(f"{status} {operation} completed in {duration_ms:.1f}ms")

    def log_mode_switch(self, from_mode: str, to_mode: str, reason: str) -> None:
        """Log mode switching"""
        self.logger.info(f"🔄 Mode switched: {from_mode} → {to_mode} ({reason})")

    def log_api_call(self, endpoint: str, response_time_ms: float, status_code: int) -> None:
        """Log API calls"""
        status_emoji = "✅" if 200 <= status_code < 300 else "❌"
        self.logger.debug(
            f"{status_emoji} API {endpoint}: {status_code} " f"({response_time_ms:.1f}ms)"
        )

    def log_cache_event(self, event_type: str, key: str, hit: bool = True) -> None:
        """Log cache events"""
        status = "HIT" if hit else "MISS"
        self.logger.debug(f"💾 Cache {status}: {event_type} - {key[:16]}...")

    def log_rule_load(self, rule_file: str, rule_count: int, load_time_ms: float) -> None:
        """Log rule loading"""
        self.logger.info(
            f"📋 Loaded {rule_count} rules from {rule_file} " f"({load_time_ms:.1f}ms)"
        )

    def log_config_change(self, setting: str, old_value: str, new_value: str) -> None:
        """Log configuration changes"""
        self.logger.info(f"⚙️ Config changed: {setting} = {old_value} → {new_value}")

    def print_session_summary(self) -> None:
        """Print session summary"""
        print("  ╔═══════════════════════════════════════════════════════╗")
        print("  ║                    Aegis                       ║")
        print("  ║                AI Threat Monitor                     ║")
        print("  ╚═══════════════════════════════════════════════════════╝")
        print()
        print("📊 Session Summary:")
        print(f"   • Total Requests: {self.session_stats['requests']}")
        print(f"   • Threats Detected: {self.session_stats['threats']}")
        print(f"   • Threats Blocked: {self.session_stats['blocks']}")

        if self.session_stats["requests"] > 0:
            threat_rate = self.session_stats["threats"] / self.session_stats["requests"] * 100
            print(f"   • Threat Rate: {threat_rate:.1f}%")

        print()
        print("🛡️ Status: Aegis is protecting your AI applications")

    def show_installation_success(self) -> None:
        """Show installation success message"""
        print("  ╔═══════════════════════════════════════════════════════╗")
        print("  ║                    Aegis                       ║")
        print("  ║                AI Threat Monitor                     ║")
        print("  ╚═══════════════════════════════════════════════════════╝")
        print()
        print("🎉 Aegis AI Threat Monitor installed successfully!")
        print()
        print("🚀 Quick Start:")
        print("   aegis test     # Test the system")
        print("   aegis status   # Check status")
        print("   aegis --help   # Show help")
        print()
        print("🛡️ Your AI applications are now protected!")
        print("   🎨 Logo: aegis-logo.png")


# Global logger instance
_global_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """Get the global security logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = SecurityLogger()
    return _global_logger
