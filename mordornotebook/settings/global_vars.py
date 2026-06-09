"""Deprecated import-time global configuration.

This module has side effects on import and is retained only for old notebooks.
New Mordor Notebook code should use explicit config loading.
"""

import warnings

warnings.warn(
    "mordornotebook.settings.global_vars is deprecated and has import-time "
    "side effects; use explicit Mordor config loading in new code.",
    DeprecationWarning,
    stacklevel=2,
)

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
