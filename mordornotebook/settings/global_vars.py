from .cred_reader import manage_openrouter_key
from .repo_paths import manage_repo_paths, find_and_select_repos

# Get cached values from jupyter config
OPENROUTER_KEY = manage_openrouter_key()
REPO_PATHS = manage_repo_paths()

__all__ = [
    'OPENROUTER_KEY',
    'REPO_PATHS',
    'manage_openrouter_key',
    'manage_repo_paths',
    'find_and_select_repos'
]
