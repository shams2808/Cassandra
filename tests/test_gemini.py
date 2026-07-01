import os
import json
import urllib.request
import urllib.error
from pathlib import Path

# Load env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in .env")
    exit(1)

test_configs = [
    # (API version, Model name)
    ("v1", "gemini-1.5-flash"),
    ("v1beta", "gemini-1.5-flash-latest"),
    ("v1", "gemini-1.5-pro"),
    ("v1beta", "gemini-2.5-flash"),
]

print("Testing Gemini API configurations...")

for version, model in test_configs:
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": "Hello, answer in one word."}]}]
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
            answer = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"[SUCCESS] Version: {version}, Model: {model} -> Answer: '{answer}'")
            # We found a working combination!
    except urllib.error.HTTPError as e:
        print(f"[FAILED] Version: {version}, Model: {model} -> HTTP Error {e.code}: {e.reason}")
    except Exception as e:
        print(f"[FAILED] Version: {version}, Model: {model} -> Exception: {e}")
