#!/usr/bin/env python3
"""CSV 익스포트 스크립트

pokervod.db의 데이터를 CSV로 익스포트합니다.
Issue #13 - 로컬 환경 데이터 추가 로직

사용법:
    # 단일 테이블 익스포트
    python scripts/export_csv.py --table hands --output hands_export.csv

    # 전체 테이블 익스포트
    python scripts/export_csv.py --all --output-dir data/exports/

    # 조건부 익스포트
    python scripts/export_csv.py --table hands --where "highlight_score >= 2"

    # JSON 필드 펼치기
    python scripts/export_csv.py --table hands --expand-json
"""

import argparse
import csv
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = DATA_DIR / "exports"

# 통합 DB 경로
POKERVOD_DB = Path("D:/AI/claude01/shared-data/pokervod.db")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# 익스포트 가능한 테이블 목록
EXPORTABLE_TABLES = [
    "hands",
    "files",
    "players",
    "contents",
    "series",
    "catalogs",
    "subcatalogs",
    "tournaments",
    "events",
    "tags",
]

# JSON 컬럼 (펼치기 대상)
JSON_COLUMNS = {
    "hands": ["players", "tags", "cards_shown"],
}


def get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    """테이블 컬럼 목록 조회"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def format_value(value: Any, expand_json: bool = False) -> str:
    """값 포맷팅"""
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, str):
        # JSON 문자열 감지 및 정리
        if value.startswith("[") or value.startswith("{"):
            try:
                parsed = json.loads(value)
                if expand_json:
                    if isinstance(parsed, list):
                        return ",".join(str(x) for x in parsed)
                return json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

    return str(value)


def export_table(
    conn: sqlite3.Connection,
    table: str,
    output_path: Path,
    where_clause: Optional[str] = None,
    expand_json: bool = False,
    limit: Optional[int] = None,
) -> int:
    """단일 테이블 익스포트"""
    cursor = conn.cursor()

    # 컬럼 조회
    columns = get_table_columns(conn, table)
    if not columns:
        logger.error(f"Table not found or empty: {table}")
        return 0

    # SQL 생성
    sql = f"SELECT {','.join(columns)} FROM {table}"

    if where_clause:
        sql += f" WHERE {where_clause}"

    sql += " ORDER BY id"

    if limit:
        sql += f" LIMIT {limit}"

    logger.info(f"Executing: {sql}")

    try:
        cursor.execute(sql)
    except sqlite3.OperationalError as e:
        logger.error(f"SQL error: {e}")
        return 0

    # CSV 쓰기
    output_path.parent.mkdir(parents=True, exist_ok=True)

    row_count = 0
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)

        for row in cursor:
            formatted_row = [
                format_value(value, expand_json and col in JSON_COLUMNS.get(table, []))
                for col, value in zip(columns, row)
            ]
            writer.writerow(formatted_row)
            row_count += 1

    logger.info(f"Exported {row_count} rows to {output_path}")
    return row_count


def export_all(
    conn: sqlite3.Connection,
    output_dir: Path,
    expand_json: bool = False,
) -> Dict[str, int]:
    """모든 테이블 익스포트"""
    results = {}
    output_dir.mkdir(parents=True, exist_ok=True)

    for table in EXPORTABLE_TABLES:
        output_path = output_dir / f"{table}.csv"
        try:
            count = export_table(conn, table, output_path, expand_json=expand_json)
            results[table] = count
        except Exception as e:
            logger.error(f"Failed to export {table}: {e}")
            results[table] = -1

    return results


def get_table_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    """테이블별 레코드 수 조회"""
    stats = {}
    cursor = conn.cursor()

    for table in EXPORTABLE_TABLES:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats[table] = -1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="CSV 익스포트 스크립트 - pokervod.db 데이터를 CSV로 익스포트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/export_csv.py --table hands --output hands.csv
  python scripts/export_csv.py --table hands --where "highlight_score >= 2"
  python scripts/export_csv.py --all --output-dir data/exports/
  python scripts/export_csv.py --stats
        """,
    )

    parser.add_argument("--table", "-t", choices=EXPORTABLE_TABLES, help="익스포트할 테이블")
    parser.add_argument("--output", "-o", type=Path, help="출력 CSV 파일 경로")
    parser.add_argument("--output-dir", type=Path, default=EXPORTS_DIR, help="전체 익스포트 시 출력 디렉토리")
    parser.add_argument("--all", "-a", action="store_true", help="모든 테이블 익스포트")
    parser.add_argument("--where", "-w", help="WHERE 조건절 (예: 'highlight_score >= 2')")
    parser.add_argument("--expand-json", action="store_true", help="JSON 필드를 쉼표 구분 문자열로 변환")
    parser.add_argument("--limit", "-l", type=int, help="최대 행 수")
    parser.add_argument("--db", type=Path, default=POKERVOD_DB, help=f"DB 경로 (기본: {POKERVOD_DB})")
    parser.add_argument("--stats", "-s", action="store_true", help="테이블별 레코드 수 출력")

    args = parser.parse_args()

    # DB 연결
    if not args.db.exists():
        logger.error(f"Database not found: {args.db}")
        sys.exit(1)

    conn = sqlite3.connect(str(args.db))

    try:
        if args.stats:
            # 통계 출력
            stats = get_table_stats(conn)
            print("\n=== Table Statistics ===")
            print(f"{'Table':<20} {'Records':>10}")
            print("-" * 32)
            for table, count in stats.items():
                status = str(count) if count >= 0 else "N/A"
                print(f"{table:<20} {status:>10}")
            print("-" * 32)
            total = sum(c for c in stats.values() if c >= 0)
            print(f"{'Total':<20} {total:>10}")
            return

        if args.all:
            # 전체 익스포트
            results = export_all(conn, args.output_dir, args.expand_json)

            print("\n=== Export Summary ===")
            print(f"{'Table':<20} {'Rows':>10}")
            print("-" * 32)
            for table, count in results.items():
                status = str(count) if count >= 0 else "FAILED"
                print(f"{table:<20} {status:>10}")

            total = sum(c for c in results.values() if c >= 0)
            print("-" * 32)
            print(f"{'Total':<20} {total:>10}")
            print(f"\nExported to: {args.output_dir}")
        else:
            # 단일 테이블 익스포트
            if not args.table:
                parser.error("--table이 필요하거나 --all을 사용하세요")

            output_path = args.output or (EXPORTS_DIR / f"{args.table}_{datetime.now():%Y%m%d_%H%M%S}.csv")
            count = export_table(
                conn,
                args.table,
                output_path,
                where_clause=args.where,
                expand_json=args.expand_json,
                limit=args.limit,
            )

            print(f"\nExported {count} rows from '{args.table}' to {output_path}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
