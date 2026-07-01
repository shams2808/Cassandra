import unittest
from pathlib import Path
from indexer.chunker import chunk_file, Chunk

class TestChunker(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = Path(__file__).parent / "fixtures"
        self.repo_path = Path(__file__).parent.parent

    def test_python_chunker(self):
        py_fixture = self.fixtures_dir / "sample.py"
        chunks = chunk_file("test-repo", str(py_fixture), str(self.repo_path))
        
        function_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        file_chunks = [c for c in chunks if c.chunk_type == "file"]
        
        self.assertEqual(len(file_chunks), 1)
        self.assertTrue(len(function_chunks) >= 4)
        self.assertTrue(len(class_chunks) >= 2)
        
        calc_sum_chunk = next(c for c in function_chunks if c.function_name == "calculate_sum")
        self.assertEqual(calc_sum_chunk.start_line, 1)
        self.assertEqual(calc_sum_chunk.end_line, 6)
        
        db_connector_chunk = next(c for c in class_chunks if c.code_text.startswith("class DatabaseConnector"))
        self.assertEqual(db_connector_chunk.start_line, 8)
        
    def test_javascript_chunker(self):
        js_fixture = self.fixtures_dir / "sample.js"
        chunks = chunk_file("test-repo", str(js_fixture), str(self.repo_path))
        
        function_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        file_chunks = [c for c in chunks if c.chunk_type == "file"]
        
        self.assertEqual(len(file_chunks), 1)
        
        fetch_chunk = next(c for c in function_chunks if c.function_name == "fetchUserData")
        self.assertEqual(fetch_chunk.start_line, 1)
        self.assertTrue("fetchUserData" in fetch_chunk.code_text)
        
        verify_chunk = next(c for c in function_chunks if c.function_name == "verifyUser")
        self.assertEqual(verify_chunk.start_line, 24)
        
        manager_chunk = next(c for c in class_chunks if c.code_text.startswith("class UserManager"))
        self.assertEqual(manager_chunk.start_line, 19)
        
    def test_swift_chunker(self):
        swift_fixture = self.fixtures_dir / "sample.swift"
        chunks = chunk_file("test-repo", str(swift_fixture), str(self.repo_path))
        
        function_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        file_chunks = [c for c in chunks if c.chunk_type == "file"]
        
        self.assertEqual(len(file_chunks), 1)
        
        download_chunk = next(c for c in function_chunks if c.function_name == "downloadFile")
        self.assertEqual(download_chunk.start_line, 3)
        
        monitor_chunk = next(c for c in class_chunks if "NetworkMonitor" in c.code_text)
        self.assertTrue("NetworkMonitor" in monitor_chunk.code_text)

if __name__ == "__main__":
    unittest.main()
