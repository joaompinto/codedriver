from rich.console import Console
import os
from typing import List, Tuple
from pathlib import Path
import fnmatch

console = Console()

# Claude API media types mapping
CLAUDE_MEDIA_TYPES = {
    # Source code files
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".java": "text/x-java",
    ".cpp": "text/x-c++src",
    ".h": "text/x-c++hdr",
    ".cs": "text/x-csharp",
    ".go": "text/x-go",
    
    # Configuration files
    ".json": "application/json",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".toml": "application/toml",
    
    # Documentation files
    ".md": "text/markdown",
    ".rst": "text/x-rst",
    ".txt": "text/plain",
    
    # Default type for unknown extensions
    "": "text/plain"
}

KNOWN_EXTENSIONS = {
    # Source code files
    ".py": "Python source",
    ".js": "JavaScript source", 
    ".ts": "TypeScript source",
    ".java": "Java source",
    ".cpp": "C++ source",
    ".h": "C/C++ header",
    ".cs": "C# source",
    ".go": "Go source",
    
    # Configuration files
    ".cfg": "Python config",
    ".toml": "TOML config",
    ".yaml": "YAML config",
    ".yml": "YAML config",
    ".json": "JSON config",
    ".gitignore": "Git ignore file",  # Special case: full filename as extension
    
    # Documentation files
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text file",
    
    # Package files
    ".in": "Package manifest"
}

# Add known files without extensions
SPECIAL_FILES = {
    'LICENSE',
    'README.md',
    'CHANGELOG.md',
    'MANIFEST.in',
    'requirements.txt',
    'requirements-dev.txt',
    'pyproject.toml',
    'setup.cfg',
    'ruff.toml'
}

def get_file_content(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

def get_relative_path(filepath: str) -> str:
    """Convert absolute path to relative path from working directory"""
    try:
        return os.path.relpath(filepath)
    except ValueError:
        return filepath

# Add new constant for ignored directories
IGNORED_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}

FILE_HANDLERS = {
    ".py": lambda x: x,  # Python files are read as-is
    ".js": lambda x: x,  # JavaScript files are read as-is
    ".ts": lambda x: x,  # TypeScript files are read as-is
    ".java": lambda x: x,  # Java files are read as-is
    ".cpp": lambda x: x,  # C++ files are read as-is
    ".h": lambda x: x,    # Header files are read as-is
    ".cs": lambda x: x,   # C# files are read as-is
    ".go": lambda x: x,   # Go files are read as-is
    ".md": lambda x: x,   # Markdown files are read as-is
    ".txt": lambda x: x,  # Text files are read as-is
    ".json": lambda x: x, # JSON files are read as-is
    ".yaml": lambda x: x, # YAML files are read as-is
    ".yml": lambda x: x,  # YAML files are read as-is
    ".toml": lambda x: x, # TOML files are read as-is
}

def _load_gitignore() -> set[str]:
    """Load .gitignore patterns into a set"""
    ignore_patterns = set()
    gitignore_path = Path('.gitignore')
    
    if not gitignore_path.exists():
        return ignore_patterns
        
    with open(gitignore_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Convert pattern to work with fnmatch
                if line.endswith('/'):
                    line = line + '*'
                ignore_patterns.add(line)
                
    return ignore_patterns

def _is_ignored(path: str, ignore_patterns: set[str]) -> bool:
    """Check if path matches any gitignore pattern"""
    path = str(Path(path))  # Normalize path
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False

def collect_files(progress) -> Tuple[List[str], List[Tuple[str, str]], List[str]]:
    """Collect all code files with progress indicator"""
    task = progress.add_task("Scanning files...", total=None)
    files_content = []
    unhandled_files = []
    
    # Load gitignore patterns
    ignore_patterns = _load_gitignore()
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS 
                  and not _is_ignored(os.path.join(root, d), ignore_patterns)]
        
        for file in files:
            if file.startswith('.') and file != '.gitignore':  # Only allow .gitignore
                continue
                
            path = os.path.join(root, file)
            if _is_ignored(path, ignore_patterns):
                continue
                
            # Special handling for .gitignore
            if file == '.gitignore':
                content = get_file_content(path)
                files_content.append(f"File: {path}\n\n{content}\n")
                continue
                
            ext = os.path.splitext(file)[1].lower()
            
            # Check both extension and special filenames
            if ext in KNOWN_EXTENSIONS or file in SPECIAL_FILES:
                content = get_file_content(path)
                media_type = CLAUDE_MEDIA_TYPES.get(ext, "text/plain")
                files_content.append(f"File: {path}\nMedia-Type: {media_type}\n\n{content}\n")
            else:
                unhandled_files.append(path)
    
    progress.update(task, visible=False)
    
    # Only report unhandled files
    if unhandled_files:
        console.print("\n[red]Unhandled files (cannot process):[/red]")
        for f in unhandled_files:
            console.print(f"  • {f}")
            
    return files_content, [], unhandled_files

def generate_files_summary(files_content: list) -> str:
    """Generate a summary of files being processed"""
    summary = "Files being processed:\n\n"
    for file_content in files_content:
        # Extract filename and count lines
        filename = file_content.split('\n')[0].replace('File: ', '')
        rel_path = get_relative_path(filename)
        code_lines = len(file_content.split('\n')) - 3
        summary += f"📄 {rel_path} ({code_lines} lines)\n"
    return summary