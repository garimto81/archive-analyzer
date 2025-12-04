#!/usr/bin/env python3
"""CSV 임포트 스크립트

로컬 CSV 파일을 pokervod.db로 임포트합니다.
Issue #13 - 로컬 환경 데이터 추가 로직

사용법:
    # 단일 파일 임포트
    python scripts/import_csv.py --file hands.csv --table hands

    # 전체 임포트 (data/imports/ 폴더 내 모든 CSV)
    python scripts/import_csv.py --all

    # Dry-run (변경 없이 검증만)
    python scripts/import_csv.py --file hands.csv --dry-run

    # 에러 리포트 생성
    python scripts/import_csv.py --file hands.csv --report errors.txt
"""

import argparse
import csv
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
IMPORTS_DIR = DATA_DIR / "imports"
TEMPLATES_DIR = DATA_DIR / "templates"

# 통합 DB 경로
POKERVOD_DB = Path("D:/AI/claude01/shared-data/pokervod.db")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class ImportStats:
    """임포트 통계"""
    total_rows: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: List[str] = field(default_factory=list)
    skipped_details: List[str] = field(default_factory=list)


@dataclass
class ColumnSpec:
    """컬럼 명세"""
    name: str
    db_type: str
    required: bool = False
    validator: Optional[Callable[[Any], bool]] = None
    transformer: Optional[Callable[[Any], Any]] = None


# 테이블별 스키마 정의
TABLE_SCHEMAS: Dict[str, List[ColumnSpec]] = {
    "hands": [
        ColumnSpec("id", "INTEGER", required=True),
        ColumnSpec("file_id", "TEXT", required=True),
        ColumnSpec("start_sec", "REAL", required=True,
                   validator=lambda x: x is None or float(x) >= 0),
        ColumnSpec("end_sec", "REAL", required=True,
                   validator=lambda x: x is None or float(x) >= 0),
        ColumnSpec("highlight_score", "REAL",
                   validator=lambda x: x is None or x == "" or 1 <= float(x) <= 3),
        ColumnSpec("players", "JSON",
                   transformer=lambda x: json.dumps(json.loads(x)) if x else "[]"),
        ColumnSpec("tags", "JSON",
                   transformer=lambda x: json.dumps(x.split(",")) if x else "[]"),
        ColumnSpec("winner", "TEXT"),
        ColumnSpec("pot_size_bb", "REAL"),
        ColumnSpec("is_all_in", "BOOLEAN",
                   transformer=lambda x: 1 if str(x).lower() in ("true", "1", "yes") else 0),
        ColumnSpec("is_showdown", "BOOLEAN",
                   transformer=lambda x: 1 if str(x).lower() in ("true", "1", "yes") else 0),
        ColumnSpec("board", "TEXT"),
        ColumnSpec("display_title", "TEXT"),
    ],
    "contents": [
        ColumnSpec("id", "INTEGER", required=True),
        ColumnSpec("series_id", "INTEGER", required=True),
        ColumnSpec("file_id", "INTEGER"),
        ColumnSpec("title", "TEXT", required=True),
        ColumnSpec("episode_num", "INTEGER"),
        ColumnSpec("air_date", "TEXT",
                   validator=lambda x: x is None or x == "" or _validate_date(x)),
        ColumnSpec("duration_sec", "INTEGER"),
        ColumnSpec("description", "TEXT"),
        ColumnSpec("display_title", "TEXT"),
    ],
    "players": [
        ColumnSpec("id", "INTEGER", required=True),
        ColumnSpec("name", "TEXT", required=True),
        ColumnSpec("display_name", "TEXT"),
        ColumnSpec("name_kr", "TEXT"),
        ColumnSpec("country", "TEXT"),
        ColumnSpec("total_hands", "INTEGER", transformer=lambda x: int(x) if x else 0),
        ColumnSpec("total_wins", "INTEGER", transformer=lambda x: int(x) if x else 0),
        ColumnSpec("career_earnings", "INTEGER"),
        ColumnSpec("wsop_bracelets", "INTEGER"),
    ],
    "files": [
        ColumnSpec("id", "INTEGER", required=True),
        ColumnSpec("event_id", "TEXT"),
        ColumnSpec("nas_path", "TEXT", required=True),
        ColumnSpec("filename", "TEXT", required=True),
        ColumnSpec("size_bytes", "INTEGER"),
        ColumnSpec("duration_sec", "REAL"),
        ColumnSpec("resolution", "TEXT"),
        ColumnSpec("codec", "TEXT"),
        ColumnSpec("fps", "REAL"),
        ColumnSpec("bitrate_kbps", "INTEGER"),
        ColumnSpec("display_title", "TEXT"),
    ],
}

# 외래키 검증 규칙
FK_CONSTRAINTS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "hands": {
        "file_id": ("files", "id"),
    },
    "contents": {
        "series_id": ("series", "id"),
        "file_id": ("files", "id"),
    },
}


def _validate_date(value: str) -> bool:
    """날짜 형식 검증 (YYYY-MM-DD)"""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def get_existing_ids(conn: sqlite3.Connection, table: str, id_column: str = "id") -> Set:
    """테이블의 기존 ID 목록 조회"""
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT {id_column} FROM {table}")
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def validate_foreign_key(conn: sqlite3.Connection, table: str, column: str, value: Any) -> bool:
    """외래키 참조 무결성 검증"""
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT 1 FROM {table} WHERE {column} = ? LIMIT 1", (value,))
        return cursor.fetchone() is not None
    except sqlite3.OperationalError:
        return False


def parse_csv_row(
    row: Dict[str, str],
    schema: List[ColumnSpec],
    row_num: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """CSV 행 파싱 및 검증"""
    result = {}

    for spec in schema:
        value = row.get(spec.name, "").strip()

        # 필수 필드 검증
        if spec.required and not value:
            return None, f"Row {row_num}: Missing required field '{spec.name}'"

        # 빈 값 처리 (JSON 타입은 빈 배열로)
        if not value:
            if spec.db_type == "JSON":
                result[spec.name] = "[]"
            else:
                result[spec.name] = None
            continue

        # 타입 변환
        try:
            if spec.db_type == "INTEGER":
                value = int(value)
            elif spec.db_type == "REAL":
                value = float(value)
            elif spec.db_type == "BOOLEAN":
                if spec.transformer:
                    value = spec.transformer(value)
                else:
                    value = 1 if str(value).lower() in ("true", "1", "yes") else 0
            elif spec.db_type == "JSON":
                if spec.transformer:
                    value = spec.transformer(value)
        except (ValueError, json.JSONDecodeError) as e:
            return None, f"Row {row_num}: Invalid {spec.db_type} for '{spec.name}': {value} ({e})"

        # 변환기 적용 (JSON/BOOLEAN 외)
        if spec.transformer and spec.db_type not in ("BOOLEAN", "JSON"):
            try:
                value = spec.transformer(value)
            except Exception as e:
                return None, f"Row {row_num}: Transform error for '{spec.name}': {e}"

        # 유효성 검증
        if spec.validator and not spec.validator(value):
            return None, f"Row {row_num}: Validation failed for '{spec.name}': {value}"

        result[spec.name] = value

    return result, None


def import_csv_file(
    csv_path: Path,
    table: str,
    conn: sqlite3.Connection,
    dry_run: bool = False,
    skip_duplicates: bool = True,
) -> ImportStats:
    """단일 CSV 파일 임포트"""
    stats = ImportStats()
    schema = TABLE_SCHEMAS.get(table)

    if not schema:
        logger.error(f"Unknown table: {table}")
        stats.error_details.append(f"Unknown table: {table}")
        return stats

    # 기존 ID 조회
    existing_ids = get_existing_ids(conn, table)
    logger.info(f"Existing {table} records: {len(existing_ids)}")

    # FK 제약조건 캐시
    fk_rules = FK_CONSTRAINTS.get(table, {})
    fk_cache: Dict[str, Set] = {}
    for fk_column, (ref_table, ref_column) in fk_rules.items():
        fk_cache[fk_column] = get_existing_ids(conn, ref_table, ref_column)

    # CSV 파싱
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    stats.total_rows = len(rows)
    logger.info(f"Total rows in CSV: {stats.total_rows}")

    # 컬럼 목록 (스키마에 정의된 것만)
    schema_columns = {spec.name for spec in schema}

    cursor = conn.cursor()

    for row_num, row in enumerate(rows, start=2):  # 헤더가 1행
        # 파싱 및 검증
        parsed, error = parse_csv_row(row, schema, row_num)

        if error:
            stats.errors += 1
            stats.error_details.append(error)
            continue

        # 중복 검사
        record_id = parsed.get("id")
        if record_id in existing_ids:
            if skip_duplicates:
                stats.skipped += 1
                stats.skipped_details.append(f"Row {row_num}: id {record_id} already exists")
                continue

        # FK 검증
        fk_error = False
        for fk_column, (ref_table, ref_column) in fk_rules.items():
            fk_value = parsed.get(fk_column)
            if fk_value is not None and fk_value not in fk_cache[fk_column]:
                stats.errors += 1
                stats.error_details.append(
                    f"Row {row_num}: Invalid {fk_column} '{fk_value}' - not found in {ref_table}.{ref_column}"
                )
                fk_error = True
                break

        if fk_error:
            continue

        # 실제 삽입 (dry-run이 아닌 경우)
        if not dry_run:
            # 스키마에 정의된 컬럼만 사용
            columns = [k for k in parsed.keys() if k in schema_columns and parsed[k] is not None]
            values = [parsed[k] for k in columns]
            placeholders = ",".join(["?" for _ in columns])

            sql = f"INSERT OR IGNORE INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

            try:
                cursor.execute(sql, values)
                if cursor.rowcount > 0:
                    stats.imported += 1
                    existing_ids.add(record_id)
                else:
                    stats.skipped += 1
                    stats.skipped_details.append(f"Row {row_num}: INSERT ignored (possible duplicate)")
            except sqlite3.Error as e:
                stats.errors += 1
                stats.error_details.append(f"Row {row_num}: SQLite error - {e}")
        else:
            stats.imported += 1  # dry-run에서는 검증 통과 = 임포트 가능

    if not dry_run:
        conn.commit()

    return stats


def print_report(stats: ImportStats, table: str, csv_path: Path, dry_run: bool = False):
    """임포트 리포트 출력"""
    mode = "(DRY-RUN)" if dry_run else ""
    print(f"\n{'=' * 50}")
    print(f"=== Import Report {mode} ===")
    print(f"{'=' * 50}")
    print(f"File: {csv_path.name}")
    print(f"Table: {table}")
    print(f"Total rows: {stats.total_rows}")
    print(f"{'Would import' if dry_run else 'Imported'}: {stats.imported}")
    print(f"Skipped: {stats.skipped}")
    print(f"Errors: {stats.errors}")

    if stats.error_details:
        print(f"\nErrors ({len(stats.error_details)}):")
        for err in stats.error_details[:10]:  # 최대 10개
            print(f"  {err}")
        if len(stats.error_details) > 10:
            print(f"  ... and {len(stats.error_details) - 10} more")

    if stats.skipped_details:
        print(f"\nSkipped ({len(stats.skipped_details)}):")
        for skip in stats.skipped_details[:5]:  # 최대 5개
            print(f"  {skip}")
        if len(stats.skipped_details) > 5:
            print(f"  ... and {len(stats.skipped_details) - 5} more")

    print(f"{'=' * 50}\n")


def save_report(stats: ImportStats, table: str, csv_path: Path, report_path: Path):
    """리포트를 파일로 저장"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Import Report - {datetime.now().isoformat()}\n")
        f.write(f"{'=' * 50}\n")
        f.write(f"File: {csv_path.name}\n")
        f.write(f"Table: {table}\n")
        f.write(f"Total rows: {stats.total_rows}\n")
        f.write(f"Imported: {stats.imported}\n")
        f.write(f"Skipped: {stats.skipped}\n")
        f.write(f"Errors: {stats.errors}\n\n")

        if stats.error_details:
            f.write(f"Errors:\n")
            for err in stats.error_details:
                f.write(f"  {err}\n")
            f.write("\n")

        if stats.skipped_details:
            f.write(f"Skipped (duplicates):\n")
            for skip in stats.skipped_details:
                f.write(f"  {skip}\n")

    logger.info(f"Report saved to: {report_path}")


def import_all(conn: sqlite3.Connection, dry_run: bool = False) -> Dict[str, ImportStats]:
    """data/imports/ 폴더의 모든 CSV 임포트"""
    results = {}

    if not IMPORTS_DIR.exists():
        logger.warning(f"Imports directory not found: {IMPORTS_DIR}")
        return results

    # 테이블 순서 (FK 의존성 고려)
    import_order = ["files", "players", "contents", "hands"]

    for table in import_order:
        csv_path = IMPORTS_DIR / f"{table}.csv"
        if csv_path.exists():
            logger.info(f"Importing {csv_path.name}...")
            stats = import_csv_file(csv_path, table, conn, dry_run)
            results[table] = stats
            print_report(stats, table, csv_path, dry_run)

    return results


def create_templates():
    """CSV 템플릿 생성"""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    for table, schema in TABLE_SCHEMAS.items():
        template_path = TEMPLATES_DIR / f"{table}_template.csv"
        headers = [spec.name for spec in schema]

        with open(template_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

        logger.info(f"Created template: {template_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CSV 임포트 스크립트 - 로컬 데이터를 pokervod.db로 임포트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/import_csv.py --file data/imports/hands.csv --table hands
  python scripts/import_csv.py --all --dry-run
  python scripts/import_csv.py --file hands.csv --table hands --report errors.txt
  python scripts/import_csv.py --create-templates
        """,
    )

    parser.add_argument("--file", "-f", type=Path, help="임포트할 CSV 파일 경로")
    parser.add_argument("--table", "-t", choices=TABLE_SCHEMAS.keys(), help="대상 테이블")
    parser.add_argument("--all", "-a", action="store_true", help="data/imports/ 폴더 전체 임포트")
    parser.add_argument("--dry-run", "-n", action="store_true", help="검증만 수행 (DB 변경 없음)")
    parser.add_argument("--report", "-r", type=Path, help="에러 리포트 저장 경로")
    parser.add_argument("--db", type=Path, default=POKERVOD_DB, help=f"DB 경로 (기본: {POKERVOD_DB})")
    parser.add_argument("--create-templates", action="store_true", help="CSV 템플릿 생성")

    args = parser.parse_args()

    # 템플릿 생성
    if args.create_templates:
        create_templates()
        return

    # 인자 검증
    if not args.all and (not args.file or not args.table):
        parser.error("--file과 --table이 필요하거나 --all을 사용하세요")

    # DB 연결
    if not args.db.exists():
        logger.error(f"Database not found: {args.db}")
        sys.exit(1)

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row

    try:
        if args.all:
            # 전체 임포트
            results = import_all(conn, args.dry_run)

            # 요약
            print("\n=== Summary ===")
            total_imported = sum(s.imported for s in results.values())
            total_errors = sum(s.errors for s in results.values())
            print(f"Total imported: {total_imported}")
            print(f"Total errors: {total_errors}")
        else:
            # 단일 파일 임포트
            if not args.file.exists():
                # data/imports/ 에서 찾기
                alt_path = IMPORTS_DIR / args.file.name
                if alt_path.exists():
                    args.file = alt_path
                else:
                    logger.error(f"File not found: {args.file}")
                    sys.exit(1)

            stats = import_csv_file(args.file, args.table, conn, args.dry_run)
            print_report(stats, args.table, args.file, args.dry_run)

            # 리포트 저장
            if args.report:
                save_report(stats, args.table, args.file, args.report)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
