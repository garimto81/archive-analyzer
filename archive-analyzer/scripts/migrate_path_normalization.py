#!/usr/bin/env python3
r"""NAS 경로 정규화 마이그레이션 스크립트

Issue #52: archive.db의 경로를 백슬래시로 통일

기존 경로:
  \\10.10.100.122\docker/GGPNAs/ARCHIVE/... (슬래시 혼용)

정규화 후:
  \\10.10.100.122\docker\GGPNAs\ARCHIVE\... (백슬래시 통일)

Usage:
    python scripts/migrate_path_normalization.py --dry-run  # 시뮬레이션
    python scripts/migrate_path_normalization.py --execute  # 실제 실행
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from archive_analyzer.utils.path import normalize_unc_path


def count_mixed_paths(cursor: sqlite3.Cursor) -> dict:
    """백슬래시 포함 경로 수 카운트 (슬래시로 통일해야 함)"""
    cursor.execute(
        r"""
        SELECT COUNT(*) FROM files
        WHERE path LIKE '%\%'
    """
    )
    backslash_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM files")
    total_count = cursor.fetchone()[0]

    return {
        "total": total_count,
        "needs_migration": backslash_count,
        "clean": total_count - backslash_count,
    }


def migrate_paths(db_path: str, dry_run: bool = True) -> dict:
    """경로 정규화 마이그레이션

    Args:
        db_path: archive.db 경로
        dry_run: True면 실제 변경 없이 시뮬레이션

    Returns:
        마이그레이션 결과 통계
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 마이그레이션 전 통계
    before_stats = count_mixed_paths(cursor)
    print(f"[Before] Total: {before_stats['total']}, Needs migration: {before_stats['needs_migration']}")

    if before_stats["needs_migration"] == 0:
        print("No paths need migration. All paths are already normalized.")
        conn.close()
        return {"migrated": 0, "skipped": before_stats["total"]}

    # 백슬래시 포함 경로 조회
    cursor.execute(
        r"""
        SELECT id, path, parent_folder FROM files
        WHERE path LIKE '%\%'
    """
    )
    rows = cursor.fetchall()

    migrated = 0
    errors = []

    for row in rows:
        file_id, old_path, old_parent = row

        # 경로 정규화
        new_path = normalize_unc_path(old_path)
        new_parent = normalize_unc_path(old_parent) if old_parent else None

        if new_path == old_path:
            continue

        if dry_run:
            # 첫 5개만 출력 (유니코드 인코딩 문제 방지)
            if migrated < 5:
                try:
                    print(f"[DRY-RUN] {old_path}")
                    print(f"       -> {new_path}")
                except UnicodeEncodeError:
                    print(f"[DRY-RUN] (path contains special chars)")
            migrated += 1
        else:
            try:
                cursor.execute(
                    """
                    UPDATE files SET path = ?, parent_folder = ?
                    WHERE id = ?
                """,
                    (new_path, new_parent, file_id),
                )
                migrated += 1
            except Exception as e:
                errors.append(f"{old_path}: {e}")

    # 커밋
    if not dry_run and migrated > 0:
        conn.commit()
        print(f"[Committed] {migrated} paths migrated")

    # 마이그레이션 후 통계
    if not dry_run:
        after_stats = count_mixed_paths(cursor)
        print(f"[After] Total: {after_stats['total']}, Needs migration: {after_stats['needs_migration']}")

    conn.close()

    return {
        "migrated": migrated,
        "errors": errors,
        "before": before_stats,
    }


def main():
    parser = argparse.ArgumentParser(description="NAS 경로 정규화 마이그레이션")
    parser.add_argument(
        "--db-path",
        default="data/output/archive.db",
        help="archive.db 경로",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="시뮬레이션 모드 (실제 변경 없음)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="실제 마이그레이션 실행",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Error: --dry-run 또는 --execute 옵션을 지정하세요.")
        sys.exit(1)

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: DB 파일을 찾을 수 없습니다: {db_path}")
        sys.exit(1)

    print(f"=== NAS 경로 정규화 마이그레이션 ===")
    print(f"DB: {db_path}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    print()

    result = migrate_paths(str(db_path), dry_run=args.dry_run)

    print()
    print(f"=== 결과 ===")
    print(f"Migrated: {result['migrated']}")
    if result.get("errors"):
        print(f"Errors: {len(result['errors'])}")
        for err in result["errors"][:5]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
