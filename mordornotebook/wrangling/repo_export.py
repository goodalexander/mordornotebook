import os
from pathlib import Path

def create_file_tree(start_path: str) -> str:
    """Create a formatted file tree string."""
    exclude_patterns = {
        '.git', '__pycache__', 'node_modules', 'venv', '.pytest_cache',
        '.vs', '.idea', '.vscode', 'build', 'dist', '*.pyc', '*.pyo',
        '*.pyd', '*.so', '*.dll', '*.dylib', '.DS_Store', 'thumbs.db',
        '.coverage', '.mypy_cache', '.hypothesis', '.tox', '.eggs'
    }
    
    tree_lines = []
    start_path = Path(start_path)
    
    for path in sorted(start_path.rglob('*')):
        # Skip excluded patterns
        if any(pat in str(path) for pat in exclude_patterns):
            continue
            
        rel_path = path.relative_to(start_path)
        depth = len(rel_path.parts) - 1
        
        if path.is_dir():
            prefix = '│   ' * depth + '├── ' if depth > 0 else ''
            tree_lines.append(f'{prefix}{path.name}/')
        else:
            if path.suffix in ['.py', '.md', '.txt', '.json', '.yaml', '.yml', '.js', '.html', '.css']:
                prefix = '│   ' * depth + '├── '
                tree_lines.append(f'{prefix}{path.name}')
    
    return '\n'.join(tree_lines)

def read_file_contents(file_path: str) -> str:
    """Read and return file contents, return empty string if failed."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return ''

def export_repository_to_string(repo_path: str) -> str:
    """
    Export a repository's contents to a structured string format.
    
    Args:
        repo_path: Path to the repository directory
    
    Returns:
        Formatted string containing the repository export
    """
    # Start building the output
    repo_name = os.path.basename(repo_path)
    output = [
        '=' * 80,
        f'{repo_name.upper()} REPOSITORY STARTS HERE',
        '=' * 80,
        '',
        'FILE TREE:',
        '==========',
        create_file_tree(repo_path),
        '',
        'FILE CONTENTS:',
        '=============',
        ''
    ]

    # Add file contents
    valid_extensions = {'.py', '.md', '.txt', '.json', '.yaml', '.yml', '.js', '.html', '.css'}
    
    for root, _, files in os.walk(repo_path):
        for file in sorted(files):
            if file.startswith('.') or not os.path.splitext(file)[1].lower() in valid_extensions:
                continue
                
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path)
            
            content = read_file_contents(file_path)
            if content:
                output.extend([
                    '=' * 80,
                    f'<<NEW FILE STARTS HERE -- {rel_path}>>',
                    '=' * 80,
                    '',
                    content,
                    ''
                ])

    return '\n'.join(output)

def export_multiple_repositories(repo_paths: list) -> str:
    """
    Export multiple repositories to a single string.
    
    Args:
        repo_paths: List of repository paths to export
    
    Returns:
        Combined string of all repository exports
    """
    output = ["MULTIPLE REPOSITORY EXPORT\n"]
    
    for repo_path in repo_paths:
        if os.path.exists(repo_path):
            output.append(export_repository_to_string(repo_path))
    
    return '\n'.join(output)

""" 
if __name__ == "__main__":
    # Example usage
    repositories = [
        'C:/Users/goodalexander/OneDrive/Documents/GitHub/narg',
        'C:/Users/goodalexander/OneDrive/Documents/GitHub/agti'
    ]
    
    # Get repository contents as string
    output_string = export_multiple_repositories(repositories)
    print(output_string)  # Or use the string as needed
""" 