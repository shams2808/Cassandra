import json
import os
from indexer.config import CACHE_FILE_PATH

# Global cache dictionary mapping: content_hash -> list[float] (embedding vector)
_cache = {}
_loaded = False

def load_cache():
    """
    Loads the persistent embedding cache from disk.
    """
    global _cache, _loaded
    if _loaded:
        return
        
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    else:
        _cache = {}
    _loaded = True

def save_cache():
    """
    Persists the current embedding cache to disk.
    """
    global _cache
    try:
        os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f)
    except Exception:
        pass

def get_cached_embedding(content_hash: str) -> list[float] | None:
    """
    Retrieves the embedding for a given hash from the cache.
    """
    load_cache()
    return _cache.get(content_hash)

def set_cached_embedding(content_hash: str, embedding: list[float]):
    """
    Adds an embedding to the cache. Call save_cache() to commit to disk.
    """
    load_cache()
    _cache[content_hash] = embedding

def clear_cache():
    """
    Clears the memory and persistent cache.
    """
    global _cache
    _cache = {}
    if os.path.exists(CACHE_FILE_PATH):
        try:
            os.remove(CACHE_FILE_PATH)
        except Exception:
            pass
