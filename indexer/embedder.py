import os
import re
import json
import urllib.request
import urllib.error
from indexer.config import EMBEDDING_MODEL, BATCH_SIZE

def clean_for_embedding(code_text: str) -> str:
    """
    Cleans code text for embedding by stripping comments and collapsing excessive blank lines.
    This exact function must be used at both index time and query time.
    """
    lines = code_text.splitlines()
    cleaned_lines = []
    
    in_block_comment = False
    
    for line in lines:
        stripped = line.strip()
        
        # JS/TS/Swift block comment handling
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
                parts = stripped.split("*/", 1)
                if len(parts) > 1 and parts[1].strip():
                    stripped = parts[1].strip()
                else:
                    continue
            else:
                continue
        
        if "/*" in stripped and "*/" not in stripped:
            in_block_comment = True
            parts = stripped.split("/*", 1)
            stripped = parts[0].strip()
            if not stripped:
                continue
                
        # Line comments
        if stripped.startswith("#"):
            continue
        if stripped.startswith("//"):
            continue
            
        cleaned_lines.append(line)
        
    text = "\n".join(cleaned_lines)
    # Collapse multiple blank lines
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

def embed_batch_openai(texts: list[str]) -> list[list[float]]:
    """
    Calls OpenAI's embedding API for a single batch of texts.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
        
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "input": texts,
        "model": EMBEDDING_MODEL
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            # Ensure the embeddings are sorted by index to preserve input order
            embeddings = [item["embedding"] for item in sorted(res_data["data"], key=lambda x: x["index"])]
            return embeddings
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"OpenAI API call failed: {e.code} - {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Failed to communicate with OpenAI: {e}")

def embed_text(texts: list[str]) -> list[list[float]]:
    """
    Batches texts and gets embeddings for all of them.
    Provider-agnostic function.
    """
    if not texts:
        return []
        
    all_embeddings = []
    
    # Process in batches
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        batch_embeddings = embed_batch_openai(batch)
        all_embeddings.extend(batch_embeddings)
        
    return all_embeddings
