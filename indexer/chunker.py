import os
import re
import bisect
import hashlib
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from indexer.config import SUPPORTED_EXTENSIONS, MAX_FILE_SIZE_BYTES, EXCLUDE_DIRS
from indexer.embedder import clean_for_embedding

@dataclass
class Chunk:
    repo_id: str
    file_path: str
    function_name: str
    start_line: int
    end_line: int
    code_text: str
    language: str
    chunk_type: str  # "function" | "class" | "file"
    content_hash: str

    def to_dict(self):
        return asdict(self)

def compute_content_hash(code_text: str) -> str:
    cleaned = clean_for_embedding(code_text)
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()

def get_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".py":
        return "python"
    elif ext in {".js", ".ts", ".tsx"}:
        return "javascript"
    elif ext == ".swift":
        return "swift"
    return "unknown"

def parse_comments_and_strings(code: str, language: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    Finds comments and string literal ranges to avoid scanning them for definitions.
    """
    comment_ranges = []
    string_ranges = []
    
    in_single_quote = False
    in_double_quote = False
    in_template_lit = False
    in_line_comment = False
    in_block_comment = False
    
    single_quote_start = -1
    double_quote_start = -1
    template_lit_start = -1
    line_comment_start = -1
    block_comment_start = -1
    
    i = 0
    code_len = len(code)
    
    while i < code_len:
        char = code[i]
        next_char = code[i+1] if i + 1 < code_len else ""
        
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                comment_ranges.append((line_comment_start, i))
            i += 1
            continue
            
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                comment_ranges.append((block_comment_start, i + 2))
                i += 2
            else:
                i += 1
            continue
            
        if in_single_quote:
            if char == "\\":
                i += 2
            elif char == "'":
                in_single_quote = False
                string_ranges.append((single_quote_start, i + 1))
                i += 1
            else:
                i += 1
            continue
            
        if in_double_quote:
            if char == "\\":
                i += 2
            elif char == '"':
                in_double_quote = False
                string_ranges.append((double_quote_start, i + 1))
                i += 1
            else:
                i += 1
            continue
            
        if in_template_lit:
            if char == "\\":
                i += 2
            elif char == "`":
                in_template_lit = False
                string_ranges.append((template_lit_start, i + 1))
                i += 1
            else:
                i += 1
            continue
            
        # Comments detection
        if char == "/" and next_char == "/":
            in_line_comment = True
            line_comment_start = i
            i += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            block_comment_start = i
            i += 2
            continue
        # Python comments
        if char == "#" and language == "python":
            in_line_comment = True
            line_comment_start = i
            i += 1
            continue
            
        # String literals
        if char == "'":
            in_single_quote = True
            single_quote_start = i
            i += 1
            continue
        if char == '"':
            in_double_quote = True
            double_quote_start = i
            i += 1
            continue
        if char == "`" and language == "javascript":
            in_template_lit = True
            template_lit_start = i
            i += 1
            continue
            
        i += 1
        
    if in_line_comment:
        comment_ranges.append((line_comment_start, code_len))
    if in_block_comment:
        comment_ranges.append((block_comment_start, code_len))
    if in_single_quote:
        string_ranges.append((single_quote_start, code_len))
    if in_double_quote:
        string_ranges.append((double_quote_start, code_len))
    if in_template_lit:
        string_ranges.append((template_lit_start, code_len))
        
    return comment_ranges, string_ranges

def is_in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= pos < end:
            return True
    return False

def find_matching_brace(code: str, start_index: int, language: str) -> int:
    """
    Scans forward from start_index (where '{' is located) to find the matching '}'.
    """
    in_single_quote = False
    in_double_quote = False
    in_template_lit = False
    in_line_comment = False
    in_block_comment = False
    brace_depth = 1
    
    i = start_index + 1
    code_len = len(code)
    
    while i < code_len:
        char = code[i]
        next_char = code[i+1] if i + 1 < code_len else ""
        
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue
            
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue
            
        if in_single_quote:
            if char == "\\":
                i += 2
            elif char == "'":
                in_single_quote = False
                i += 1
            else:
                i += 1
            continue
            
        if in_double_quote:
            if char == "\\":
                i += 2
            elif char == '"':
                in_double_quote = False
                i += 1
            else:
                i += 1
            continue
            
        if in_template_lit:
            if char == "\\":
                i += 2
            elif char == "`":
                in_template_lit = False
                i += 1
            else:
                i += 1
            continue
            
        # Comments
        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue
            
        # Strings
        if char == "'":
            in_single_quote = True
            i += 1
            continue
        if char == '"':
            in_double_quote = True
            i += 1
            continue
        if char == "`" and language == "javascript":
            in_template_lit = True
            i += 1
            continue
            
        # Braces
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
            if brace_depth == 0:
                return i
        i += 1
        
    return -1

def chunk_python(repo_id: str, file_path: str, code: str) -> list[Chunk]:
    chunks = []
    lines = code.splitlines(keepends=True)
    num_lines = len(lines)
    
    # Simple line-by-line comment and string scanner
    comment_ranges, string_ranges = parse_comments_and_strings(code, "python")
    
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line))
        
    def get_indentation(s: str) -> int:
        count = 0
        for char in s:
            if char == " ":
                count += 1
            elif char == "\t":
                count += 4
            else:
                break
        return count

    i = 0
    decorators = []
    
    while i < num_lines:
        line = lines[i]
        stripped = line.strip()
        pos = line_starts[i]
        
        # Skip if line is inside a string (like a multiline docstring) or a comment
        if is_in_ranges(pos, string_ranges) or is_in_ranges(pos, comment_ranges):
            i += 1
            continue
            
        if not stripped:
            i += 1
            continue
            
        if stripped.startswith("#"):
            i += 1
            continue
            
        if stripped.startswith("@"):
            decorators.append(i)
            i += 1
            continue
            
        is_def = stripped.startswith("def ")
        is_class = stripped.startswith("class ")
        
        if is_def or is_class:
            start_line_idx = decorators[0] if decorators else i
            indent_level = get_indentation(line)
            
            name_match = re.search(r'(?:def|class)\s+([a-zA-Z0-9_]+)', stripped)
            name = name_match.group(1) if name_match else "unknown"
            
            end_line_idx = i
            j = i + 1
            while j < num_lines:
                j_line = lines[j]
                j_stripped = j_line.strip()
                if not j_stripped or j_stripped.startswith("#"):
                    j += 1
                    continue
                # If indentation goes below or equal to starting indentation
                j_indent = get_indentation(j_line)
                if j_indent <= indent_level:
                    break
                end_line_idx = j
                j += 1
            
            chunk_code = "".join(lines[start_line_idx:end_line_idx + 1])
            chunk_type = "function" if is_def else "class"
            
            chunks.append(Chunk(
                repo_id=repo_id,
                file_path=file_path,
                function_name=name if is_def else "",
                start_line=start_line_idx + 1,
                end_line=end_line_idx + 1,
                code_text=chunk_code,
                language="python",
                chunk_type=chunk_type,
                content_hash=compute_content_hash(chunk_code)
            ))
            
            decorators = []
            i += 1
        else:
            decorators = []
            i += 1
            
    return chunks

def chunk_brace_language(repo_id: str, file_path: str, code: str, language: str) -> list[Chunk]:
    chunks = []
    
    line_starts = [0]
    for line in code.splitlines(keepends=True):
        line_starts.append(line_starts[-1] + len(line))
        
    def get_line_num(pos):
        return bisect.bisect_right(line_starts, pos)

    comment_ranges, string_ranges = parse_comments_and_strings(code, language)

    # Patterns to detect chunk starts
    if language == "javascript":
        patterns = [
            # Function declaration: function foo(...)
            (re.compile(r'(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([a-zA-Z0-9_$]+)\s*\('), "function"),
            # Arrow function: const foo = (...) =>
            (re.compile(r'(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>'), "function"),
            # Class declaration: class Foo
            (re.compile(r'(?:export\s+)?(?:default\s+)?class\s+([a-zA-Z0-9_$]+)'), "class"),
            # Method declaration in class: foo(...) {
            (re.compile(r'^[ \t]*(?:async\s+)?(?:get\s+|set\s+)?\*?\s*([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*\{', re.M), "function")
        ]
    elif language == "swift":
        patterns = [
            # Swift function
            (re.compile(r'(?:private|fileprivate|internal|public|open)?\s*(?:async\s+)?func\s+([a-zA-Z0-9_]+)'), "function"),
            # Swift class/struct/enum
            (re.compile(r'(?:private|fileprivate|internal|public|open)?\s*(?:class|struct|enum)\s+([a-zA-Z0-9_]+)'), "class")
        ]
    else:
        return []

    matches = []
    for pattern, chunk_type in patterns:
        for match in pattern.finditer(code):
            start_pos = match.start()
            # Ignore if this regex match falls within a comment or a string literal
            if is_in_ranges(start_pos, comment_ranges) or is_in_ranges(start_pos, string_ranges):
                continue
            matches.append((start_pos, match.end(), match.group(1), chunk_type))
            
    matches.sort(key=lambda x: x[0])
    
    for start_pos, end_pos, name, chunk_type in matches:
        next_brace = code.find("{", start_pos)
        next_semi = code.find(";", start_pos)
        
        if next_brace == -1:
            continue
        if next_semi != -1 and next_semi < next_brace:
            continue
            
        matching_brace_idx = find_matching_brace(code, next_brace, language)
        if matching_brace_idx == -1:
            continue
            
        start_line = get_line_num(start_pos)
        end_line = get_line_num(matching_brace_idx)
        
        chunk_code = code[start_pos:matching_brace_idx + 1]
        
        chunks.append(Chunk(
            repo_id=repo_id,
            file_path=file_path,
            function_name=name if chunk_type == "function" else "",
            start_line=start_line,
            end_line=end_line,
            code_text=chunk_code,
            language=language,
            chunk_type=chunk_type,
            content_hash=compute_content_hash(chunk_code)
        ))
        
    return chunks

def get_repo_files(repo_path: str) -> list[str]:
    repo_dir = Path(repo_path).resolve()
    
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(repo_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        files = []
        for f in res.stdout.splitlines():
            full_path = repo_dir / f
            if full_path.exists() and full_path.suffix in SUPPORTED_EXTENSIONS:
                if full_path.stat().st_size <= MAX_FILE_SIZE_BYTES:
                    files.append(str(full_path))
        return files
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
        
    files = []
    for root, dirs, filenames in os.walk(str(repo_dir)):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for filename in filenames:
            ext = Path(filename).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                full_path = Path(root) / filename
                if full_path.stat().st_size <= MAX_FILE_SIZE_BYTES:
                    files.append(str(full_path))
    return files

def chunk_file(repo_id: str, file_path: str, repo_path: str) -> list[Chunk]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception:
        return []
        
    rel_path = str(Path(file_path).relative_to(Path(repo_path)))
    language = get_language(file_path)
    
    chunks = []
    
    if language == "python":
        chunks.extend(chunk_python(repo_id, rel_path, code))
    elif language in {"javascript", "swift"}:
        chunks.extend(chunk_brace_language(repo_id, rel_path, code, language))
        
    if code.strip():
        num_lines = len(code.splitlines())
        chunks.append(Chunk(
            repo_id=repo_id,
            file_path=rel_path,
            function_name="",
            start_line=1,
            end_line=max(1, num_lines),
            code_text=code,
            language=language,
            chunk_type="file",
            content_hash=compute_content_hash(code)
        ))
        
    # TODO: Migrate to tree-sitter based parsing in v2 if brace/indentation heuristics
    # show parsing inaccuracies in production environments.
    
    return chunks
