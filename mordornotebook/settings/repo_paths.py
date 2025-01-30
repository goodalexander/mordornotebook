import jupyter_core.paths as paths
from pathlib import Path
import os
import re

def normalize_path(path_str):
    """Convert Windows paths to Linux style and normalize"""
    return str(Path(path_str).resolve()).replace('\\', '/')

def update_jupyter_config(variable_name, value):
    """Update or add a variable to jupyter config"""
    config_dir = paths.jupyter_config_dir()
    config_path = os.path.join(config_dir, "jupyter_notebook_config.py")
    
    # Create config if it doesn't exist
    if not os.path.exists(config_path):
        os.makedirs(config_dir, exist_ok=True)
        open(config_path, 'a').close()
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Check if variable exists
    var_pattern = f"c\.{variable_name}\s*="
    var_match = re.search(var_pattern, content, re.MULTILINE)
    
    if isinstance(value, list):
        # Format list values
        value_str = "[\n    " + ",\n    ".join(f"'{v}'" for v in value) + "\n]"
    else:
        # Format string value
        value_str = f"'{value}'"
    
    new_line = f"c.{variable_name} = {value_str}\n"
    
    if var_match:
        # Replace existing variable
        content = re.sub(f"{var_pattern}.*?(?=\n|$)", new_line.strip(), content, flags=re.MULTILINE | re.DOTALL)
    else:
        # Add new variable
        content += f"\n# {variable_name} configuration\n{new_line}"
    
    with open(config_path, 'w') as f:
        f.write(content)

def github_update_jupyter_config():
    """Interactive function to update GitHub directory and referenced repos"""
    config_dir = paths.jupyter_config_dir()
    config_path = os.path.join(config_dir, "jupyter_notebook_config.py")
    
    # Check for existing configuration
    existing_github_dir = None
    existing_repos = []
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            content = f.read()
            
        dir_match = re.search(r"c\.GITHUB_DIRECTORY\s*=\s*'([^']*)'", content)
        if dir_match:
            existing_github_dir = dir_match.group(1)
            
        repos_match = re.search(r"c\.REFERENCED_REPOS\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if repos_match:
            existing_repos = [repo.strip().strip("'\"") for repo in repos_match.group(1).split(',') if repo.strip()]
    
    if existing_github_dir and existing_repos:
        print("\nExisting configuration found:")
        print(f"GitHub directory: {existing_github_dir}")
        print("Referenced repositories:")
        for repo in existing_repos:
            print(f"- {repo}")
            
        print("\nWould you like to keep the existing configuration (1) or re-enter (0)?")
        choice = input().strip()
        
        if choice == "1":
            print("Keeping existing configuration.")
            return
    
    # If no existing config or user chose to re-enter
    print("\nPlease enter your GitHub directory path:")
    github_dir = input().strip()
    
    # 2. Normalize path
    github_dir = normalize_path(github_dir)
    
    # 3 & 4. Cache GITHUB_DIRECTORY to jupyter config
    update_jupyter_config('GITHUB_DIRECTORY', github_dir)
    print(f"\nGitHub directory saved: {github_dir}")
    
    # 6. Display available repos
    github_path = Path(github_dir)
    repos = []
    if github_path.exists():
        for item in github_path.iterdir():
            if item.is_dir() and (item / '.git').exists():
                repos.append(item.name)
    
    if not repos:
        print("No repositories found in the specified directory.")
        return
    
    # Display repos with numbers
    print("\nAvailable repositories:")
    for i, repo in enumerate(sorted(repos), 1):
        print(f"{i}. {repo}")
    
    # 7. Prompt for repo selection
    print("\nEnter repository numbers or names to select (comma-separated):")
    selection = input().strip()
    
    selected = []
    for item in selection.split(','):
        item = item.strip()
        if item.isdigit() and 0 < int(item) <= len(repos):
            selected.append(repos[int(item)-1])
        elif item in repos:
            selected.append(item)
    
    # 8. Save REFERENCED_REPOS
    update_jupyter_config('REFERENCED_REPOS', selected)
    print("\nSelected repositories saved:")
    for repo in selected:
        print(f"- {repo}")

def get_full_repo_paths():
    """Get full paths for referenced repositories"""
    config_dir = paths.jupyter_config_dir()
    config_path = os.path.join(config_dir, "jupyter_notebook_config.py")
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Get GITHUB_DIRECTORY
    dir_match = re.search(r"c\.GITHUB_DIRECTORY\s*=\s*'([^']*)'", content)
    if not dir_match:
        raise ValueError("GITHUB_DIRECTORY not found in jupyter config")
    
    github_dir = dir_match.group(1)
    
    # Get REFERENCED_REPOS
    repos_match = re.search(r"c\.REFERENCED_REPOS\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if not repos_match:
        raise ValueError("REFERENCED_REPOS not found in jupyter config")
    
    repos = [repo.strip().strip("'\"") for repo in repos_match.group(1).split(',') if repo.strip()]
    
    # Return full paths in Linux style
    return [normalize_path(os.path.join(github_dir, repo)) for repo in repos]

# Example usage for IPython notebook:
"""
# Run the interactive configuration
github_update_jupyter_config()

# Get the full paths
full_paths = get_full_repo_paths()
print("\nFull repository paths:")
for path in full_paths:
    print(path)
"""
