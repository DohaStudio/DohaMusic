"""Workspace additive migration 전용 안전 CLI."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from backend.db.workspace_preflight import (
    PreflightError,
    collect_inventory,
    create_verified_backup,
    mask_path,
    planned_backup_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Workspace DB migration 전 read-only inventory와 명시적 backup 도구"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="DB를 read-only로 점검")
    inventory.add_argument("--database", type=Path, required=True)
    inventory.add_argument("--confirm-read-approved", action="store_true")

    plan = subparsers.add_parser("plan-backup", help="DB를 열지 않고 backup 경로 계획")
    plan.add_argument("--database", type=Path, required=True)
    plan.add_argument("--backup-root", type=Path, required=True)

    backup = subparsers.add_parser("backup", help="명시적 확인 뒤 backup 생성·검증")
    backup.add_argument("--database", type=Path, required=True)
    backup.add_argument("--backup-root", type=Path, required=True)
    backup.add_argument("--confirm-read-approved", action="store_true")
    backup.add_argument("--confirm-writers-stopped", action="store_true")
    backup.add_argument("--confirm-create-backup", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inventory":
            result = collect_inventory(args.database, read_approved=args.confirm_read_approved)
        elif args.command == "plan-backup":
            result = {
                "database": mask_path(args.database),
                "planned_backup": mask_path(planned_backup_path(args.database, args.backup_root)),
                "database_opened": False,
                "files_created": False,
            }
        else:
            result = create_verified_backup(
                args.database,
                args.backup_root,
                confirmed=args.confirm_create_backup,
                read_approved=args.confirm_read_approved,
                writers_stopped=args.confirm_writers_stopped,
            )
    except PreflightError as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False))
        return 2
    except (OSError, sqlite3.Error):
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "error": "파일 또는 SQLite 작업이 실패했습니다. 상세 경로는 출력하지 않습니다.",
                },
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
