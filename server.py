#!/usr/bin/env python3
# Arranca el servidor MCP para StarUML (JSON-RPC 2.0 por stdio, sin dependencias).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from staruml_mcp.servidor import main  # noqa: E402

if __name__ == '__main__':
    main()
