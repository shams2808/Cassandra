import unittest
from unittest.mock import patch
import os
import shutil
from pathlib import Path

# Add project root to python path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from indexer.reindex import run_reindex
from indexer.retrieval import retrieve_context
from indexer.cache import clear_cache

def mock_embed_text(texts: list[str]) -> list[list[float]]:
    """
    Returns a deterministic mock vector of dimension 1536 based on MD5 of the text.
    Allows testing similarity search offline.
    """
    results = []
    for t in texts:
        import hashlib
        h = hashlib.md5(t.encode('utf-8')).digest()
        vec = []
        for i in range(1536):
            vec.append(float(h[i % len(h)]) / 255.0)
        results.append(vec)
    return results

class TestRetrieval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures_dir = Path(__file__).parent / "fixtures"
        cls.repo_id = "test-retrieval-repo"
        
        # Clear any existing cache/db from previous runs
        clear_cache()
        
        # Index fixtures directory using mocked embeddings
        with patch("indexer.reindex.embed_text", side_effect=mock_embed_text):
            run_reindex(str(cls.fixtures_dir), cls.repo_id)

    def test_similarity_retrieval(self):
        # We query for a diff chunk that has calculate_sum
        diff_chunk = """
-def calculate_sum(x: int, y: int) -> int:
+def calculate_sum(x: int, y: int, z: int = 0) -> int:
     # This is a sample decorated function
     result = x + y
     return result
"""
        with patch("indexer.retrieval.embed_text", side_effect=mock_embed_text):
            results = retrieve_context(diff_chunk, self.repo_id, top_k=3)
            
        # Verify we got results
        self.assertTrue(len(results) > 0)
        
        # We expect similar chunks from sample.py to show up
        similar_matches = [r for r in results if r["relation"] == "similar"]
        self.assertTrue(any("sample.py" in r["file"] for r in similar_matches))

    def test_caller_lookup(self):
        # A diff chunk modifying calculate_sum
        diff_chunk = """
-def calculate_sum(x: int, y: int) -> int:
+def calculate_sum(x: int, y: int) -> int:
"""
        with patch("indexer.retrieval.embed_text", side_effect=mock_embed_text):
            results = retrieve_context(diff_chunk, self.repo_id, top_k=2)
            
        # Check if caller lookup found process_data inside sample.py
        caller_matches = [r for r in results if r["relation"] == "caller"]
        
        self.assertTrue(len(caller_matches) >= 1)
        self.assertTrue(any("sample.py" in r["file"] for r in caller_matches))
        # The caller code should contain calculate_sum
        self.assertTrue(any("calculate_sum" in r["code"] for r in caller_matches))

    def test_reindex_cache_hits(self):
        # We index the repository (first time was already done in setUpClass)
        # So running it again now should result in 100% cache hits!
        call_count = 0
        def counting_mock_embed(texts):
            nonlocal call_count
            call_count += len(texts)
            return mock_embed_text(texts)
            
        with patch("indexer.reindex.embed_text", side_effect=counting_mock_embed):
            run_reindex(str(self.fixtures_dir), self.repo_id)
            
        # Since all chunks are in the cache, no calls to embed_text should occur
        self.assertEqual(call_count, 0)

if __name__ == "__main__":
    unittest.main()
