from .cred_reader import manage_openrouter_key
from .repo_paths import get_full_repo_paths, github_update_jupyter_config

github_update_jupyter_config()
OPENROUTER_KEY = manage_openrouter_key()
REPO_PATHS = get_full_repo_paths()

__all__ = [
    'OPENROUTER_KEY',
    'REPO_PATHS',
    'manage_openrouter_key',
    'get_full_repo_paths',
    'github_update_jupyter_config'
]
