# Cassandra: PR Review App

Cassandra is a context‑aware Pull Request review tool that walks a repository, chunks files at function/class/file boundaries, generates text embeddings using **Gemini API**, indexes them in a persistent Chroma DB, and retrieves relevant code context (similar code and caller sites) when evaluating PR diffs.

It includes a Manifest V3 Chrome extension that parses diffs from GitHub PR pages, posts them to a local review backend, and renders summary evaluations and line‑by‑line comments directly in the GitHub UI.

---

## Workspace Setup

> [!IMPORTANT]
> **Active Workspace Recommendation**: Set the project root folder `C:/Users/shami/.gemini/antigravity/scratch/cassandra` as your active workspace in your IDE (VS Code, etc.) for correct relative paths and script execution.

### 1. Install Dependencies
Ensure you have Python 3.8+ installed. Install the required libraries:
```bash
pip install chromadb fastapi uvicorn
```

### 2. Configure Environment
Copy the example environment file and add your Gemini API key:
```bash
cp .env.example .env
```
Inside `.env`, populate:
```env
GEMINI_API_KEY=your-gemini-api-key-here
```

---

## Part 1: Repo Indexer & Retrieval

### Running the CLI Indexer
The CLI wipes out any previous indices for the given repository ID and indexes the codebase from scratch (using a content‑hash caching mechanism to skip re‑embedding unchanged functions):
```bash
python indexer/reindex.py --repo-path <path-to-your-local-repo> --repo-id <unique-repo-id>
```
On completion, it prints a summary of files indexed, chunks created, cache hits, and new embeddings generated.

### Using Context Retrieval
Backend services import `retrieve_context` to fetch similarity matches and callers:
```python
from indexer.retrieval import retrieve_context

results = retrieve_context(
    diff_chunk="def calculate_sum(x: int, y: int): ...",
    repo_id="my-repo",
    top_k=5
)
```
Returns a list of matching code snippets with scores and relation types.

### Running Tests
```bash
python -m unittest tests/test_chunker.py
python -m unittest tests/test_retrieval.py
```

---

## Part 2: Chrome Extension

### 1. Load the Extension in Chrome
1. Open `chrome://extensions/`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `extension` folder inside this project directory.

### 2. Run the Review Server
We provide a local review server (stub) for end‑to‑end testing:
```bash
python cassandra_backend.py
```
This runs on `http://localhost:8000`.

### 3. Review a PR
1. Navigate to a GitHub PR files tab.
2. The **Cassandra Reviewer** panel appears in the bottom‑right.
3. Click **Run Cassandra Review** to send diffs to the local server and display AI‑generated feedback.

The UI adapts to both light and dark GitHub themes.

---

## License
MIT License


Cassandra is a context-aware Pull Request review tool that walks a repository, chunks files at function/class/file boundaries, generates text embeddings using OpenAI, indices them in a persistent Chroma DB, and retrieves relevant code context (similar code and caller sites) when evaluating PR diffs. 

It is paired with a Manifest V3 Chrome Extension that parses diffs from GitHub PR pages, posts them to a Delphi review backend (Track B), and renders summary evaluations and line-by-line comments natively in the GitHub UI.

---

## Workspace Setup

> [!IMPORTANT]
> **Active Workspace Recommendation**: We recommend setting the project root folder [C:/Users/shami/.gemini/antigravity/scratch/cassandra](file:///C:/Users/shami/.gemini/antigravity/scratch/cassandra) as your active workspace in your IDE (VS Code, etc.). This ensures configuration files, relative paths, and script executions work correctly.

### 1. Install Dependencies
Ensure you have Python 3.8+ installed. Install the required libraries:
```bash
pip install chromadb fastapi uvicorn
```

### 2. Configure Environment
Copy the example environment file and add your OpenAI API key:
```bash
cp .env.example .env
```
Inside `.env`, populate:
```env
OPENAI_API_KEY=your-openai-api-key-here
```

---

## Part 1: Repo Indexer & Retrieval

### Running the CLI Indexer
The CLI wipes out any previous indices for the given repository ID and indexes the codebase from scratch (using a content-hash caching mechanism to skip re-embedding unchanged functions):
```bash
python indexer/reindex.py --repo-path <path-to-your-local-repo> --repo-id <unique-repo-id>
```
On completion, it prints a summary:
```text
Starting reindex for repo_id 'my-repo' at path 'C:\code\my-repo'...
Found 12 files matching configured extensions.
Generated 84 code chunks.
Cache check: 64 hits, 20 new chunks to embed.
Calling embedding API for 20 chunks...
Successfully retrieved and cached new embeddings.
Writing vectors and metadata to Chroma DB...
Indexing completed successfully!

--- Indexing Summary ---
Repository Path:          C:\code\my-repo
Repository ID:            my-repo
Total Files Indexed:      12
Total Chunks Stored:     84
Cache Hit Count:          64
New Embeddings Generated: 20
------------------------
```

### Using context retrieval
Other backend services (like the Delphi LLM generation backend) import `retrieve_context` to fetch similarity matches and callers:
```python
from indexer.retrieval import retrieve_context

results = retrieve_context(
    diff_chunk="def calculate_sum(x: int, y: int): ...",
    repo_id="my-repo",
    top_k=5
)

# Returns:
# [
#   { "file": "src/math.py", "function_name": "calculate_sum", "code": "def calculate_sum...", "score": 0.05, "relation": "similar" },
#   { "file": "src/main.py", "function_name": "process_data", "code": "def process_data...", "score": 0.0, "relation": "caller" }
# ]
```

### Running Tests
To verify chunk boundaries and retrieval matches (which runs offline using mocked deterministic embeddings):
```bash
python -m unittest tests/test_chunker.py
python -m unittest tests/test_retrieval.py
```

---

## Part 2: Chrome Extension

The Chrome extension scrapes the GitHub PR page, sends diffs to the review backend, and overlays reviews inline.

### 1. Load the extension in Chrome
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** in the top-left corner.
4. Select the `extension` folder inside this project directory (`C:\Users\shami\.gemini\antigravity\scratch\cassandra\extension`).

### 2. Run the Mock review server (Stub)
We have provided a stub Delphi backend server to verify the extension end-to-end:
```bash
python delphi_stub.py
```
This runs a local server on `http://localhost:8000`.

### 3. Review a PR
1. Navigate to any GitHub PR changes tab (e.g., `https://github.com/owner/repo/pull/123/files`).
2. You will see a floating translucent **Cassandra Reviewer** panel on the bottom-right.
3. Click **Run Cassandra Review**.
4. The extension will extract the diffs, send them to `http://localhost:8000/review` via a background script relay, display the summary evaluation inside the panel, and render line-by-line warnings and information alerts directly inside GitHub's diff tables.
5. The UI adapts seamlessly to both light and dark GitHub themes.
