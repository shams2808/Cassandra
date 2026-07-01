import argparse
import sys
import os
from pathlib import Path

# Add project root to python path to support indexer imports when running from elsewhere
sys.path.append(str(Path(__file__).resolve().parent.parent))

from indexer.chunker import get_repo_files, chunk_file
from indexer.embedder import embed_text
from indexer.cache import get_cached_embedding, set_cached_embedding, save_cache, load_cache
from indexer.vector_store import delete_collection, add_chunks

def run_reindex(repo_path: str, repo_id: str):
    """
    Deletes existing collection, chunks files, embeds new chunks (using cache),
    and indexes everything into the vector store.
    """
    repo_path_obj = Path(repo_path).resolve()
    if not repo_path_obj.exists():
        print(f"Error: Repository path '{repo_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Starting reindex for repo_id '{repo_id}' at path '{repo_path}'...")
    
    # 1. Clean existing vector store collection for this repo_id
    delete_collection(repo_id)
    
    # 2. Walk and find all supported files
    files = get_repo_files(str(repo_path_obj))
    file_count = len(files)
    print(f"Found {file_count} files matching configured extensions.")
    
    # 3. Chunk each file
    all_chunks = []
    for file_path in files:
        chunks = chunk_file(repo_id, file_path, str(repo_path_obj))
        all_chunks.extend(chunks)
        
    chunk_count = len(all_chunks)
    print(f"Generated {chunk_count} code chunks.")
    
    if chunk_count == 0:
        print("No chunks generated. Indexing finished.")
        return
        
    # 4. Determine which chunks need embeddings vs cache hits
    load_cache()
    
    chunks_to_embed = []
    new_embedding_indices = []
    
    # Pre-allocate embeddings list
    embeddings = [None] * chunk_count
    cache_hits = 0
    new_embeddings = 0
    
    for idx, chunk in enumerate(all_chunks):
        cached = get_cached_embedding(chunk.content_hash)
        if cached is not None:
            embeddings[idx] = cached
            cache_hits += 1
        else:
            chunks_to_embed.append(chunk)
            new_embedding_indices.append(idx)
            new_embeddings += 1
            
    print(f"Cache check: {cache_hits} hits, {new_embeddings} new chunks to embed.")
    
    # 5. Fetch new embeddings if needed
    if new_embeddings > 0:
        # Extract code text for new chunks
        # Use clean_for_embedding to get the text to actually embed
        # Wait, the embedder's clean_for_embedding is already run inside compute_content_hash,
        # but let's make sure we embed the CLEANED text!
        # The prompt says: "Clean and embed diff_chunk using the exact same clean_for_embedding + embed_text pipeline as indexing. Clean before embedding."
        # This implies we pass the cleaned code texts to embed_text!
        from indexer.embedder import clean_for_embedding
        texts_to_embed = [clean_for_embedding(c.code_text) for c in chunks_to_embed]
        
        print(f"Calling embedding API for {new_embeddings} chunks...")
        try:
            new_vectors = embed_text(texts_to_embed)
            
            # Map new vectors back to the main embeddings array and save to cache
            for idx, vec in zip(new_embedding_indices, new_vectors):
                embeddings[idx] = vec
                set_cached_embedding(all_chunks[idx].content_hash, vec)
                
            save_cache()
            print("Successfully retrieved and cached new embeddings.")
        except Exception as e:
            print(f"Fatal error during embedding: {e}", file=sys.stderr)
            sys.exit(1)
            
    # 6. Add all chunks and their vectors to vector store
    print("Writing vectors and metadata to Chroma DB...")
    try:
        add_chunks(repo_id, all_chunks, embeddings)
        print("Indexing completed successfully!")
    except Exception as e:
        print(f"Fatal error writing to vector store: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Print summary statistics
    print("\n--- Indexing Summary ---")
    print(f"Repository Path:          {repo_path}")
    print(f"Repository ID:            {repo_id}")
    print(f"Total Files Indexed:      {file_count}")
    print(f"Total Chunks Stored:     {chunk_count}")
    print(f"Cache Hit Count:          {cache_hits}")
    print(f"New Embeddings Generated: {new_embeddings}")
    print("------------------------\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cassandra Repository Indexer CLI")
    parser.add_argument("--repo-path", required=True, help="Path to local repository to index")
    parser.add_argument("--repo-id", required=True, help="Unique identifier for this repository")
    
    args = parser.parse_args()
    run_reindex(args.repo_path, args.repo_id)
