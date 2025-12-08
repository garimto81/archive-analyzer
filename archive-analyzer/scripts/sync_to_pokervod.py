#!/usr/bin/env python
"""pokervod.db 동기화 스크립트

archive.db 데이터를 pokervod.db로 동기화합니다.

사용법:
    python scripts/sync_to_pokervod.py [--dry-run] [--stats]
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from archive_analyzer.sync import SyncService, SyncConfig


def main():
    parser = argparse.ArgumentParser(description="pokervod.db 동기화")
    parser.add_argument(
        "--archive-db",
        type=str,
        default="data/output/archive.db",
        help="archive.db 경로",
    )
    parser.add_argument(
        "--pokervod-db",
        type=str,
        default="d:/AI/claude01/qwen_hand_analysis/data/pokervod.db",
        help="pokervod.db 경로",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 쓰기 없이 시뮬레이션",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="동기화 통계만 조회",
    )
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="파일만 동기화 (카탈로그 건너뜀)",
    )
    parser.add_argument(
        "--catalogs-only",
        action="store_true",
        help="카탈로그만 동기화 (파일 건너뜀)",
    )
    parser.add_argument(
        "--hls-only",
        action="store_true",
        help="HLS 호환 파일만 동기화 (mp4, mov, ts 등)",
    )

    args = parser.parse_args()

    # 설정
    config = SyncConfig(
        archive_db=args.archive_db,
        pokervod_db=args.pokervod_db,
        hls_only=args.hls_only,
    )

    # 서비스 초기화
    try:
        service = SyncService(config)
    except FileNotFoundError as e:
        print(f"오류: {e}")
        sys.exit(1)

    # 통계 조회 모드
    if args.stats:
        print("\n=== 동기화 통계 ===")
        stats = service.get_sync_stats()
        print(f"\narchive.db:")
        print(f"  비디오 파일: {stats['archive_video_count']}개")
        print(f"  미디어 정보: {stats['archive_media_info_count']}개")
        print(f"\npokervod.db:")
        print(f"  파일: {stats['pokervod_file_count']}개")
        print(f"  카탈로그: {stats['pokervod_catalog_count']}개")
        print(f"  서브카탈로그: {stats['pokervod_subcatalog_count']}개")
        return

    # 동기화 실행
    if args.dry_run:
        print("\n[DRY-RUN 모드] 실제 쓰기 없이 시뮬레이션합니다.\n")

    if args.catalogs_only:
        print("카탈로그 동기화 중...")
        result = service.sync_catalogs(args.dry_run)
        print(f"\n=== 카탈로그 동기화 결과 ===")
        print(f"  삽입: {result.inserted}개")
        print(f"  업데이트: {result.updated}개")
        if result.errors:
            print(f"  오류: {len(result.errors)}개")
    elif args.files_only:
        print("파일 동기화 중...")
        result = service.sync_files(args.dry_run)
        print(f"\n=== 파일 동기화 결과 ===")
        print(f"  삽입: {result.inserted}개")
        print(f"  업데이트: {result.updated}개")
        if result.errors:
            print(f"  오류: {len(result.errors)}개")
            for error in result.errors[:10]:
                print(f"    - {error}")
            if len(result.errors) > 10:
                print(f"    ... 외 {len(result.errors) - 10}개")
    else:
        print("전체 동기화 중...")
        results = service.run_full_sync(args.dry_run)

        print(f"\n=== 동기화 결과 ===")
        for name, result in results.items():
            print(f"\n{name}:")
            print(f"  삽입: {result.inserted}개")
            print(f"  업데이트: {result.updated}개")
            if result.errors:
                print(f"  오류: {len(result.errors)}개")

    if args.dry_run:
        print("\n[DRY-RUN 완료] 실제 변경 없음")
    else:
        print("\n동기화 완료!")


if __name__ == "__main__":
    main()
