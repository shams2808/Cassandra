import re
import hashlib
import chromadb
from indexer.config import CHROMA_PERSIST_DIR
from indexer.chunker import Chunk

_client = None

def get_client():
    """
    Returns a singleton instance of the persistent Chroma client.
    """
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client

def _get_collection_name(repo_id: str) -> str:
    """
    Cleans and slugifies the repo_id to ensure it conforms to Chroma collection name rules.
    - Length: 3-63 characters
    - Alphanumeric, underscores, or hyphens only.
    - No consecutive periods.
    - Must start and end with an alphanumeric character.
    """
    clean = re.sub(r'[^a-zA-Z0-9_-]', '-', repo_id)
    clean = re.sub(r'^[^a-zA-Z0-9]+', '', clean)
    clean = re.sub(r'[^a-zA-Z0-9]+$', '', clean)
    
    # If the slugified string is too short or too long, use a hashed fallback
    if len(clean) < 3 or len(clean) > 63:
        h = hashlib.md5(repo_id.encode('utf-8')).hexdigest()
        return f"repo-{h}"
    return clean

def delete_collection(repo_id: str):
    """
    Deletes the collection associated with repo_id.
    """
    client = get_client()
    name = _get_collection_name(repo_id)
    try:
        client.delete_collection(name)
    except Exception:
        # Collection might not exist, which is fine
        pass

def add_chunks(repo_id: str, chunks: list[Chunk], embeddings: list[list[float]]):
    """
    Adds chunks and their corresponding embeddings to the collection for repo_id.
    """
    if not chunks:
        return
        
    client = get_client()
    name = _get_collection_name(repo_id)
    collection = client.get_or_create_collection(name)
    
    ids = []
    documents = []
    metadatas = []
    
    for idx, chunk in enumerate(chunks):
        # Create a unique, deterministic ID for each chunk
        chunk_id = f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}:{chunk.chunk_type}"
        ids.append(chunk_id)
        documents.append(chunk.code_text)
        metadatas.append({
            "file_path": chunk.file_path,
            "function_name": chunk.function_name or "",
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language,
            "chunk_type": chunk.chunk_type,
            "content_hash": chunk.content_hash
        })
        
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

def query(repo_id: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """
    Queries the collection associated with repo_id for the nearest neighbors.
    Returns results in the contract shape with similarity scores.
    """
    client = get_client()
    name = _get_collection_name(repo_id)
    try:
        collection = client.get_collection(name)
    except Exception:
        return []
        
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    query_results = []
    if not results or not results.get("documents") or len(results["documents"]) == 0:
        return []
        
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0] if "distances" in results else [0.0] * len(documents)
    
    for i in range(len(documents)):
        meta = metadatas[i]
        query_results.append({
            "file": meta.get("file_path", ""),
            "function_name": meta.get("function_name", ""),
            "code": documents[i],
            "score": float(distances[i]),
            "relation": "similar"
        })
        
    return query_results

def get_all_chunks(repo_id: str) -> list[dict]:
    """
    Retrieves all chunk documents and metadata stored in the collection.
    Useful for caller lookup.
    """
    client = get_client()
    name = _get_collection_name(repo_id)
    try:
        collection = client.get_collection(name)
    except Exception:
        return []
        
    res = collection.get(include=["documents", "metadatas"])
    
    chunks_list = []
    if not res or not res.get("documents"):
        return []
        
    documents = res["documents"]
    metadatas = res["metadatas"]
    
    for i in range(len(documents)):
        meta = metadatas[i]
        chunks_list.append({
            "file": meta.get("file_path", ""),
            "function_name": meta.get("function_name", ""),
            "code": documents[i],
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "language": meta.get("language", ""),
            "chunk_type": meta.get("chunk_type", ""),
            "content_hash": meta.get("content_hash", "")
        })
        
    return chunks_list
