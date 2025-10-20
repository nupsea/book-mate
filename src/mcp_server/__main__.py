"""
MCP Server entry point with strict stdout protection.
This module ensures that stdout is reserved exclusively for JSON-RPC messages.
"""

import sys
import os
import logging

# CRITICAL: Set environment variables BEFORE any imports
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"

# Configure root logger to stderr BEFORE any other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)

# Suppress noisy third-party loggers - set to ERROR not WARNING
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# Now safe to import the server
from src.mcp_server.book_tools import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
