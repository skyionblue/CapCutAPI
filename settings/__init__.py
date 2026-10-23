"""
Configuration package entry point: re-exports all configuration.
"""

# Import everything from `local`, which already pulls in the env and base configuration
from .local import *

__all__ = [
    "IS_CAPCUT_ENV",
    "API_KEYS",
    "MODEL_CONFIG",
    "PURCHASE_LINKS",
    "LICENSE_CONFIG"
]

# Helper returning the platform information
def get_platform_info():
    """
    Platform information, used by Script_file.dumps(); CapCut requires a platform block.

    Returns:
        dict: the platform information
    """
    return {
        "app_id": 359289,
        "app_source": "cc",
        "app_version": "6.5.0",
        "device_id": "c4ca4238a0b923820dcc509a6f75849b",
        "hard_disk_id": "307563e0192a94465c0e927fbc482942",
        "mac_address": "c3371f2d4fb02791c067ce44d8fb4ed5",
        "os": "mac",
        "os_version": "15.5"
    }
