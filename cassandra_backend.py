import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add project root to python path
sys.path.append(str(Path(__file__).resolve().parent))

from indexer.retrieval import retrieve_context

app = FastAPI(title="Cassandra Standalone PR Reviewer Backend")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables from .env if present
def load_env():
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()

def get_api_key():
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    return gemini_key, openai_key

def call_gemini(prompt: str, api_key: str) -> dict:
    """
    Calls Gemini 2.5 Flash using raw HTTP with structured JSON output schema.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json"
    }
    
    # Structured JSON schema definition for Gemini
    schema = {
        "type": "OBJECT",
        "properties": {
            "summary": {
                "type": "OBJECT",
                "properties": {
                    "Core Changes": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" }
                    },
                    "Architectural Impact": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" }
                    },
                    "Testing & Verification": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" }
                    }
                },
                "required": ["Core Changes", "Architectural Impact", "Testing & Verification"]
            },
            "comments": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "file": { "type": "STRING" },
                        "line": { "type": "INTEGER" },
                        "severity": { "type": "STRING", "enum": ["info", "warning", "error"] },
                        "text": { "type": "STRING" }
                    },
                    "required": ["file", "line", "severity", "text"]
                }
            }
        },
        "required": ["summary", "comments"]
    }
    
    payload = {
        "contents": [
            {
                "parts": [
                    { "text": prompt }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema
        }
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
            # Extract text from candidate parts
            text_response = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_response)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"Gemini API call failed: {e.code} - {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Gemini connection error: {e}")

def call_openai(prompt: str, api_key: str) -> dict:
    """
    Fallback calls OpenAI gpt-4o-mini using structured JSON schema.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    schema = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "object",
                "properties": {
                    "Core Changes": {
                        "type": "array",
                        "items": { "type": "string" }
                    },
                    "Architectural Impact": {
                        "type": "array",
                        "items": { "type": "string" }
                    },
                    "Testing & Verification": {
                        "type": "array",
                        "items": { "type": "string" }
                    }
                },
                "required": ["Core Changes", "Architectural Impact", "Testing & Verification"],
                "additionalProperties": False
            },
            "comments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": { "type": "string" },
                        "line": { "type": "number" },
                        "severity": { "type": "string", "enum": ["info", "warning", "error"] },
                        "text": { "type": "string" }
                    },
                    "required": ["file", "line", "severity", "text"]
                }
            }
        },
        "required": ["summary", "comments"],
        "additionalProperties": False
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            { "role": "user", "content": prompt }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "pr_review",
                "schema": schema,
                "strict": True
            }
        }
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
            text_response = res_data["choices"][0]["message"]["content"]
            return json.loads(text_response)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"OpenAI API call failed: {e.code} - {err_msg}")
    except Exception as e:
        raise RuntimeError(f"OpenAI connection error: {e}")

@app.post("/review")
async def generate_pr_review(request: Request):
    payload = await request.json()
    repo_id = payload.get("repo_id")
    pr_title = payload.get("pr_title", "")
    pr_description = payload.get("pr_description", "")
    diff_files = payload.get("diff", [])
    
    print(f"Generating review for repo: {repo_id}, PR: {pr_title}")
    
    # 1. Fetch relevant code context for each file in the diff
    retrieved_contexts = []
    for diff_file in diff_files:
        filename = diff_file.get("file", "")
        patch = diff_file.get("patch", "")
        
        # Only search context if we have a real code modification patch
        if patch and "COLLAPSED" not in patch and "EMPTY" not in patch:
            try:
                context_results = retrieve_context(patch, repo_id, top_k=2)
                for res in context_results:
                    retrieved_contexts.append(
                        f"File Reference: {res['file']}\n"
                        f"Function Name: {res['function_name']}\n"
                        f"Relationship: {res['relation']}\n"
                        f"Code Content:\n{res['code']}\n"
                        f"-----------------------"
                    )
            except Exception as e:
                print(f"Warning: Context retrieval bypassed due to error: {e}")
                
    context_str = "\n".join(retrieved_contexts)
    
    # 2. Build the diff changes context
    diff_str_list = []
    for diff_file in diff_files:
        diff_str_list.append(
            f"File: {diff_file.get('file')}\n"
            f"Status: {diff_file.get('status')}\n"
            f"Diff Patch:\n{diff_file.get('patch')}\n"
            f"======================="
        )
    diffs_str = "\n".join(diff_str_list)
    
    # 3. Construct Prompt
    prompt = f"""You are a senior code reviewer. Review the following Pull Request changes and generate constructive, highly accurate comments and a summary.
You have access to related files and call sites from the repository as reference context to ground your review and avoid hallucinating code patterns.

PR Title: {pr_title}
PR Description: {pr_description}

--- PULL REQUEST DIFF CHANGES ---
{diffs_str}

--- RETRIEVED codebase REFERENCE CONTEXT ---
{context_str}

--- INSTRUCTIONS FOR SUMMARY ---
1. Provide a detailed, highly informative summary of the changes using markdown hierarchical lists.
2. Do NOT write standard paragraphs. Organize all information into a structured, easily readable nested list.
3. The format MUST be strictly:
   * **Core Changes**:
     1. [Detailed change point 1 with code references]
     2. [Detailed change point 2 with code references]
   * **Architectural Impact**:
     1. [Detailed explanation of runtime impact or behaviour change]
   * **Testing & Verification**:
     1. [Detailed explanation of test coverage, unit tests added, or verification validation]
4. You MUST indent the numbered items by exactly 2 spaces (e.g. "  1. ") under their respective bullet header, so they nest correctly.

--- INSTRUCTIONS FOR COMMENTS ---
1. Review the diff changes thoroughly. Flag bugs, security risks, performance bottlenecks, or edge cases.
2. If the code is correct, look for constructive optimizations, micro-improvements, documentation clarity, or naming suggestions so you can provide helpful inline feedback.
3. For each comment, identify the correct file path (must match one of the files in the diff) and the correct line number in the new file (corresponding to lines starting with "+" or context lines " " in the diff patch).
4. Assign a severity level: "info", "warning", or "error".
5. Reference the retrieved context explicitly when relevant.
6. Return your response strictly in the JSON format matching the schema.
"""

    # 4. Get API Keys
    gemini_key, openai_key = get_api_key()
    
    if not gemini_key and not openai_key:
        # Fallback to mock response if no API keys are present
        print("Warning: No API keys found. Returning mock review response.")
        return {
            "summary": {
                "Core Changes": [
                    "No API keys found in `.env`. Please add `GEMINI_API_KEY` or `OPENAI_API_KEY` to enable real reviews."
                ],
                "Architectural Impact": [
                    "Standalone review was bypassed due to missing credentials."
                ],
                "Testing & Verification": [
                    "Run indexing CLI to check database states."
                ]
            },
            "comments": [
                {
                    "file": diff_files[0].get("file") if diff_files else "sample.py",
                    "line": 1,
                    "severity": "info",
                    "text": "[Cassandra Mock] Add an API key to generate a real review."
                }
            ]
        }
        
    try:
        if gemini_key:
            print("Invoking Gemini 2.5 Flash review generator...")
            response_json = call_gemini(prompt, gemini_key)
        else:
            print("Invoking OpenAI GPT-4o-Mini review generator...")
            response_json = call_openai(prompt, openai_key)
            
        print("LLM Response JSON:")
        print(json.dumps(response_json, indent=2))
        return response_json
    except Exception as e:
        print(f"LLM completed with error: {e}")
        # Graceful fallback response
        return {
            "summary": {
                "Core Changes": [
                    "Review generation was interrupted."
                ],
                "Architectural Impact": [
                    f"LLM Error encountered: {str(e)}"
                ],
                "Testing & Verification": [
                    "Verify your API keys, network connection, or quota limits."
                ]
            },
            "comments": [
                {
                    "file": diff_files[0].get("file") if diff_files else "sample.py",
                    "line": 1,
                    "severity": "error",
                    "text": f"LLM error: {str(e)}"
                }
            ]
        }

if __name__ == "__main__":
    import uvicorn
    print("Starting Standalone Cassandra Review Backend on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
