#!/usr/bin/env python3
"""Create one encrypted off-platform backup for the configured hosted tenant."""
from __future__ import annotations

import json
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.hosted_backup_service import (  # noqa: E402
    HostedBackupConfig,
    create_hosted_backup,
)


def main() -> int:
    result = create_hosted_backup(HostedBackupConfig.from_env())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
