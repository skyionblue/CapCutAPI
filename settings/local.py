"""
Local configuration module: loads configuration from the local config file.
"""

import os
import json

# Path to the configuration file
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

# Defaults
IS_CAPCUT_ENV = True

# Default domain
DRAFT_DOMAIN = "https://www.install-ai-guider.top"

# Default preview route
PREVIEW_ROUTER = "/draft/downloader"

# Whether to upload the draft archive
IS_UPLOAD_DRAFT = False

# Port
PORT = 9000

OSS_CONFIG = []
MP4_OSS_CONFIG = []

# Draft store: drafts are written here after every edit so a restart cannot lose them
DRAFT_STORE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "drafts_store")

# Load the local configuration file if present
if os.path.exists(CONFIG_FILE_PATH):
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            local_config = json.load(f)

            # CapCut International mode
            if "is_capcut_env" in local_config:
                IS_CAPCUT_ENV = local_config["is_capcut_env"]

            # Domain
            if "draft_domain" in local_config:
                DRAFT_DOMAIN = local_config["draft_domain"]

            # Port
            if "port" in local_config:
                PORT = local_config["port"]

            # Preview route
            if "preview_router" in local_config:
                PREVIEW_ROUTER = local_config["preview_router"]

            # Whether to upload the draft archive
            if "is_upload_draft" in local_config:
                IS_UPLOAD_DRAFT = local_config["is_upload_draft"]

            # Object storage for draft archives
            if "oss_config" in local_config:
                OSS_CONFIG = local_config["oss_config"]

            # Draft store directory
            if "draft_store_dir" in local_config:
                DRAFT_STORE_DIR = os.path.expanduser(local_config["draft_store_dir"])

            # Object storage for exported videos
            if "mp4_oss_config" in local_config:
                MP4_OSS_CONFIG = local_config["mp4_oss_config"]

    except (json.JSONDecodeError, IOError):
        # Configuration failed to load; fall back to the defaults
        pass
