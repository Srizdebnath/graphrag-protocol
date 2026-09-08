#!/usr/bin/env python3
"""Test connection to TigerGraph Cloud Savanna workspace.

Usage:
    python scripts/test_connection.py
    python scripts/test_connection.py --host <workspace-url> --secret <secret>
"""

import argparse
import os
import sys
from pathlib import Path

DOTENV_PATH = Path(__file__).parent.parent / ".env"


def load_dotenv(path: Path = DOTENV_PATH):
    if not path.exists():
        print(f"[!] No {path} found — using environment variables or CLI args")
        return
    print(f"[+] Loading env from {path}")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main():
    parser = argparse.ArgumentParser(description="Test TigerGraph Savanna connection")
    parser.add_argument("--host", help="Workspace URL, e.g. a2a51931...i.tgcloud.io")
    parser.add_argument("--secret", help="GSQL secret")
    parser.add_argument("--graph", default="GraphragProtocol", help="Graph name")
    args = parser.parse_args()

    load_dotenv()

    host = args.host or os.getenv("TIGERGRAPH_HOST")
    secret = args.secret or os.getenv("TIGERGRAPH_GSQL_SECRET")
    graph = args.graph or os.getenv("TIGERGRAPH_GRAPH_NAME", "GraphragProtocol")

    if not host:
        print("[x] Missing workspace URL. Pass --host or set TIGERGRAPH_HOST in .env")
        print("    Find it by opening Query Editor and checking the browser URL / Network tab.")
        sys.exit(1)
    if not secret:
        print("[x] Missing GSQL secret. Pass --secret or set TIGERGRAPH_GSQL_SECRET in .env")
        sys.exit(1)

    print(f"[+] Connecting to {host} ...")

    try:
        from pyTigerGraph import TigerGraphConnection

        conn = TigerGraphConnection(
            host=host,
            graphname=graph,
            gsqlSecret=secret,
            tgCloud=True,
        )
        print(f"[+] Connected to graph '{graph}'")
        print(f"[+] Version: {conn.getVersion()}")
        print("[+] Edge types:", conn.getEdgeTypes())
        print("[+] Vertex types:", conn.getVertexTypes())
        print("[+] OK — connection works!")
    except ImportError:
        print("[x] pyTigerGraph not installed. Run: pip install pyTigerGraph")
        sys.exit(1)
    except Exception as e:
        print(f"[x] Connection failed: {e}")
        print()
        print("If the hostname is wrong, try these variants:")
        print("  - <workspace-id-without-dashes>.i.tgcloud.io")
        print("  - <workspace-id>.us-west-2.aws.cloud.tigergraph.com")
        sys.exit(1)


if __name__ == "__main__":
    main()