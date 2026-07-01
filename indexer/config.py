import os
from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Data directory for persistency (under .cassandra_data in the project root)
DATA_DIR = BASE_DIR / ".cassandra_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Chroma Vector Store settings
CHROMA_PERSIST_DIR = str(DATA_DIR / "chroma")

# Embedding cache settings
CACHE_FILE_PATH = str(DATA_DIR / "embedding_cache.json")

# File walking settings
SUPPORTED_EXTENSIONS = {".js", ".ts", ".tsx", ".py", ".swift"}
MAX_FILE_SIZE_BYTES = 100 * 1024  # 100 KB

# Embedding settings
EMBEDDING_PROVIDER = "openai"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
BATCH_SIZE = 100

# Exclude list for manual walk fallback
EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "lockfiles",
    "__pycache__",
    "venv",
    ".venv",
    ".cassandra_data",
}
