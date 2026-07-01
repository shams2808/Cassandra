import re
import sys
from pathlib import Path

# Add project root to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from indexer.embedder import clean_for_embedding, embed_text
from indexer.vector_store import query, get_all_chunks

def extract_function_name(diff_chunk: str) -> str | None:
    """
    Extracts the name of the function/method being changed from a diff chunk.
    Scans modified lines first, then context lines, using patterns for Python, JS/TS, and Swift.
    """
    lines = diff_chunk.splitlines()
    
    patterns = [
        # Python: def foo(...)
        re.compile(r'def\s+([a-zA-Z0-9_]+)'),
        # JS/TS: function foo(...)
        re.compile(r'function\s*\*?\s*([a-zA-Z0-9_$]+)'),
        # JS/TS Arrow: const foo = (...) =>
        re.compile(r'(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>'),
        # Swift: func foo(...)
        re.compile(r'func\s+([a-zA-Z0-9_]+)'),
        # JS/TS Class Method: myMethod(...) {
        re.compile(r'^[ \t]*(?:async\s+)?(?:get\s+|set\s+)?\*?\s*([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*\{?', re.M)
    ]
    
    ignored_keywords = {"if", "for", "while", "switch", "catch", "function", "def", "func", "class", "struct", "let", "const", "var"}

    # 1. Prioritize modified lines (additions/deletions)
    for line in lines:
        if line.startswith('+') or line.startswith('-'):
            stripped = line[1:].strip()
            for pat in patterns:
                m = pat.search(stripped)
                if m:
                    name = m.group(1)
                    if name not in ignored_keywords:
                        return name
                        
    # 2. Fallback to any line in the chunk
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('+') or stripped.startswith('-'):
            stripped = stripped[1:].strip()
        for pat in patterns:
            m = pat.search(stripped)
            if m:
                name = m.group(1)
                if name not in ignored_keywords:
                    return name
                    
    return None

def retrieve_context(diff_chunk: str, repo_id: str, top_k: int = 5) -> list[dict]:
    """
    Retrieves relevant code context (similar code and caller sites) for a given diff chunk.
    
    Args:
        diff_chunk (str): The code diff/chunk to search context for.
        repo_id (str): The identifier of the repository.
        top_k (int): Number of similar context chunks to return. Default is 5.
        
    Returns:
        list[dict]: A list of dictionary objects of the form:
            [
              {
                "file": "string",
                "function_name": "string",
                "code": "string",
                "score": 0.85,
                "relation": "similar"|"caller"
              }
            ]
    """
    # 1. Clean and embed diff_chunk
    cleaned_diff = clean_for_embedding(diff_chunk)
    if not cleaned_diff:
        return []
        
    # Get embedding vector
    embeddings = embed_text([cleaned_diff])
    if not embeddings:
        return []
    query_embedding = embeddings[0]
    
    # 2. Query similarity from vector store
    similar_results = query(repo_id, query_embedding, top_k=top_k)
    
    # 3. Caller-lookup pass
    caller_results = []
    changed_func_name = extract_function_name(diff_chunk)
    
    if changed_func_name:
        # Scan indexed chunks for call sites
        all_indexed_chunks = get_all_chunks(repo_id)
        
        # Word boundary match regex for the function name
        call_site_pattern = re.compile(r'\b' + re.escape(changed_func_name) + r'\b')
        
        for indexed_chunk in all_indexed_chunks:
            # Skip if this chunk is the function definition itself
            # We check if function_name matches and it's a function type chunk
            if indexed_chunk["function_name"] == changed_func_name and indexed_chunk["chunk_type"] == "function":
                continue
                
            # If the indexed chunk references the function name in its code
            if call_site_pattern.search(indexed_chunk["code"]):
                caller_results.append({
                    "file": indexed_chunk["file"],
                    "function_name": indexed_chunk["function_name"],
                    "code": indexed_chunk["code"],
                    "score": 0.0,
                    "relation": "caller"
                })
                
    # 4. Merge similarity results and caller results (deduplicating caller against similarity)
    # Deduplicate by (file, start_line, end_line) or simply (file, code)
    seen = set()
    merged_results = []
    
    # Add similarity results first
    for res in similar_results:
        # Unique identifier for the chunk
        chunk_key = (res["file"], res["code"].strip())
        seen.add(chunk_key)
        merged_results.append(res)
        
    # Add caller results if they aren't already included
    for res in caller_results:
        chunk_key = (res["file"], res["code"].strip())
        if chunk_key not in seen:
            seen.add(chunk_key)
            merged_results.append(res)
            
    return merged_results
