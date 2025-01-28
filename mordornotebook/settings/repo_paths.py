from pathlib import Path
import jupyter_core.paths as paths
import os
import re
def find_and_select_repos(start_path=None):
    """Find git repos and let user select them with simple text input."""
    if start_path is None:
        # Try common locations
        possible_paths = [
            Path.home() / "Documents" / "GitHub",
            Path.home() / "OneDrive" / "Documents" / "GitHub",
        ]

        for path in possible_paths:
            if path.exists():
                start_path = path
                break
    else:
        start_path = Path(start_path)

    print(f"Searching in: {start_path}\n")

    # Find repositories
    repos = []
    for item in start_path.rglob("*"):
        if item.name == ".git" and item.is_dir():
            repos.append(item.parent.name)

    if not repos:
        print("No repositories found.")
        return []

    # Print available repos
    print("Available repositories:")
    for i, repo in enumerate(sorted(repos), 1):
        print(f"{i}. {repo}")

    print("\nEnter repository names or numbers to select, separated by commas:")
    selection = input().strip()

    # Handle both number and name inputs
    selected = []
    for item in selection.split(','):
        item = item.strip()
        if item.isdigit() and 0 < int(item) <= len(repos):
            selected.append(repos[int(item)-1])
        elif item in repos:
            selected.append(item)

    print("\nSelected repositories:")
    for repo in selected:
        print(f"- {repo}")

    return [str(start_path / repo) for repo in selected]

def manage_repo_paths(new_paths=None):
    """
    Initialize or update repository paths in Jupyter config.
    If new_paths is None, will just display current paths.
    """
    config_dir = paths.jupyter_config_dir()
    config_path = os.path.join(config_dir, "jupyter_notebook_config.py")

    # Initialize config if it doesn't exist
    if not os.path.exists(config_path):
        os.makedirs(config_dir, exist_ok=True)
        open(config_path, 'a').close()

    # Read existing config
    with open(config_path, 'r') as file:
        content = file.read()

    # Check for existing repo paths
    repo_match = re.search(r"c\.RepoPathList\s=\s\[(.*?)\]", content, re.DOTALL)
    existing_paths = []
    if repo_match:
        # Extract paths from existing config
        paths_str = repo_match.group(1)
        existing_paths = [path.strip().strip("'\"") for path in paths_str.split(',') if path.strip()]
        print("Current repository paths:")
        for path in existing_paths:
            print(f"- {path}")

    if new_paths is not None:
        # Combine existing and new paths, remove duplicates while preserving order
        combined_paths = []
        seen = set()
        for path in existing_paths + new_paths:
            if path not in seen:
                combined_paths.append(path)
                seen.add(path)

        # Format the new config entry
        paths_str = ",\n    ".join(f"'{path}'" for path in combined_paths)
        new_config = f"\n# Repository paths configuration\nc.RepoPathList = [\n    {paths_str}\n]\n"

        if repo_match:
            # Update existing config
            content = content.replace(repo_match.group(0), new_config.strip())
        else:
            # Append to config
            content += new_config

        # Write updated config
        with open(config_path, 'w') as file:
            file.write(content)

        print("\nUpdated repository paths:")
        for path in combined_paths:
            print(f"- {path}")

    return existing_paths
# Example usage:
"""
# To see current paths:
current_paths = manage_repo_paths()
# To add new paths:
selected_repos = find_and_select_repos()  # From previous code
manage_repo_paths(selected_repos)
"""