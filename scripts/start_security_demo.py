"""Start the source backend with explicit server-side model configuration."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--max-model-calls", type=int, default=200)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    if args.key_file:
        if not args.key_file.is_file():
            parser.error("Model key file does not exist")
        os.environ["AEGIS_DEEPSEEK_API_KEY_FILE"] = str(args.key_file.resolve())
        os.environ.pop("AEGIS_DEEPSEEK_API_KEY", None)
    os.environ["AEGIS_AGENT_MAX_CALLS"] = str(max(1, args.max_model_calls))
    os.environ["AEGIS_BENCHMARK_REPORT"] = str(root / "reports/external-benchmarks/external_benchmark_results.json")
    import uvicorn
    from aegis.app.server.app import create_app
    uvicorn.run(create_app(host="127.0.0.1", port=args.port), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
