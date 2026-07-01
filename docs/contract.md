# API Contract: Cassandra & Delphi Integration

This document defines the shared contract between Track A (Cassandra: Extension & Retrieval) and Track B (Delphi: Backend API & LLM).

## Review API Endpoint

### POST `/review`

Sent by the Chrome Extension to the Delphi backend when a PR review is requested.

#### Request Schema
```json
{
  "repo_id": "string",
  "pr_title": "string",
  "pr_description": "string",
  "diff": [
    {
      "file": "string",
      "patch": "unified diff string",
      "status": "added|modified|removed|renamed"
    }
  ]
}
```

#### Response Schema
```json
{
  "summary": "string",
  "comments": [
    {
      "file": "string",
      "line": 42,
      "severity": "info|warning|error",
      "text": "string"
    }
  ]
}
```

---

## Context Retrieval Interface

Implemented by Track A (Cassandra) and called by Track B (Delphi) during the review generation process.

### Python Signature

```python
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
    pass
```
