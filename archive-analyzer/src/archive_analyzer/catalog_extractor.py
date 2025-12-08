"""동적 카탈로그 및 메타데이터 추출 시스템

Issue #55: 폴더 구조와 파일명에서 카탈로그, 제목, 태그를 동적으로 추출

Features:
- 동적 카탈로그 추출 (하드코딩 제거)
- 스마트 제목 생성
- 태그 자동 추출
- 다중 뷰 지원 (브랜드별, 연도별, 지역별, 이벤트별, 플레이어별)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from functools import lru_cache


@dataclass
class ExtractedMetadata:
    """추출된 메타데이터"""

    brand: Optional[str] = None
    year: Optional[int] = None
    location: Optional[str] = None
    event_type: Optional[str] = None
    content_type: Optional[str] = None
    series: Optional[str] = None
    day: Optional[str] = None
    episode: Optional[str] = None
    buy_in: Optional[str] = None
    players: List[str] = field(default_factory=list)
    generated_title: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brand": self.brand,
            "year": self.year,
            "location": self.location,
            "event_type": self.event_type,
            "content_type": self.content_type,
            "series": self.series,
            "day": self.day,
            "episode": self.episode,
            "buy_in": self.buy_in,
            "players": self.players,
            "generated_title": self.generated_title,
            "tags": self.tags,
        }


class DynamicCatalogExtractor:
    """폴더 구조와 파일명에서 메타데이터를 동적으로 추출"""

    # 브랜드 패턴 (우선순위 순)
    BRAND_PATTERNS: List[Tuple[str, str, str]] = [
        (r"WSOP", "WSOP", "World Series of Poker"),
        (r"PAD", "PAD", "Poker After Dark"),
        (r"MPP", "MPP", "Mediterranean Poker Party"),
        (r"GOG|Game\s*of\s*Gold", "GOG", "Game of Gold"),
        (r"GGMillions?|GG\s*Millions?", "GGMillions", "GG Millions"),
        (r"HCL|Hustler", "HCL", "Hustler Casino Live"),
        (r"PokerGo", "PokerGo", "PokerGo"),
    ]

    # 지역 패턴
    LOCATION_PATTERNS: List[Tuple[str, str]] = [
        (r"EUROPE|Europe", "Europe"),
        (r"LAS\s*VEGAS|Las\s*Vegas|LV", "Las Vegas"),
        (r"PARADISE|Paradise", "Paradise"),
        (r"CYPRUS|Cyprus", "Cyprus"),
        (r"LONDON|London", "London"),
        (r"LA(?:\s|$|[^S])", "Los Angeles"),
        (r"ASIA|Asia", "Asia"),
    ]

    # 이벤트 타입 패턴
    EVENT_TYPE_PATTERNS: List[Tuple[str, str]] = [
        (r"MAIN\s*EVENT|Main\s*Event|ME(?:\d|_|\s|$)", "Main Event"),
        (r"FINAL\s*TABLE|Final\s*Table|FT(?:\d|_|\s|$)", "Final Table"),
        (r"BRACELET|Bracelet", "Bracelet Event"),
        (r"CIRCUIT|Circuit", "Circuit Event"),
        (r"HIGH\s*ROLLER|High\s*Roller|HR(?:\d|_|\s|$)", "High Roller"),
        (r"SUPER\s*HIGH\s*ROLLER|SHR", "Super High Roller"),
        (r"MYSTERY\s*BOUNTY", "Mystery Bounty"),
        (r"BOUNTY", "Bounty"),
        (r"HEADS?\s*UP|Heads?\s*Up|HU(?:\d|_|\s|$)", "Heads Up"),
        (r"6[\s-]*MAX|6-?Max", "6-Max"),
        (r"PLO|Pot[\s-]*Limit[\s-]*Omaha", "PLO"),
        (r"NLH|No[\s-]*Limit[\s-]*Hold", "NLH"),
        (r"COLOSSUS", "Colossus"),
        (r"MONSTER\s*STACK", "Monster Stack"),
    ]

    # 콘텐츠 타입 패턴
    CONTENT_TYPE_PATTERNS: List[Tuple[str, str]] = [
        (r"STREAM(?:ING)?", "Stream"),
        (r"SUBCLIP|Sub[\s-]*Clip", "Subclip"),
        (r"HAND[\s_]*(?:CLIP)?[\s_]*\d+|Hand[\s_]*#?\d+", "Hand Clip"),
        (r"CLEAN|Clean", "Clean Version"),
        (r"NO[\s_]*COMMENTARY|No[\s_]*Commentary", "No Commentary"),
        (r"MASTERED|Mastered", "Mastered"),
        (r"RAW|Raw", "Raw"),
        (r"GRAPHICS", "With Graphics"),
    ]

    # 시리즈 패턴 (WSOP 하위)
    SERIES_PATTERNS: List[Tuple[str, str]] = [
        (r"ARCHIVE|Archive|PRE-\d{4}", "Archive"),
        (r"Bracelet\s*Event", "Bracelet Event"),
        (r"Circuit\s*Event", "Circuit Event"),
        (r"Super\s*Circuit", "Super Circuit"),
    ]

    # 바이인 패턴 (명확한 금액 표시만)
    BUY_IN_PATTERN = re.compile(
        r"\$(\d{1,3}(?:,\d{3})*)\s*(?:GTD|NLH|PLO|Buy[\s-]*In|K)?|"
        r"\$(\d+)[Kk]\b|"
        r"(\d+)[Kk]\s*(?:GTD|NLH|PLO|Buy[\s-]*In)"
    )

    # 연도 패턴
    YEAR_PATTERN = re.compile(r"(?:^|[/_\s-])((?:19|20)\d{2})(?:[/_\s-]|$)")

    # Day/Episode 패턴
    DAY_PATTERN = re.compile(
        r"[Dd]ay\s*(\d+[A-D]?)|DAY\s*(\d+[A-D]?)|"
        r"Final\s*(?:Day|Table)|FT"
    )
    EPISODE_PATTERN = re.compile(
        r"[Ee]p(?:isode)?[\s_-]*(\d+)|"
        r"[Ss](\d+)[\s_-]*[Ee][Pp]?(\d+)"  # S12-EP14 형식
    )

    # 플레이어 패턴 (vs 매치 - 카드 표기 제외)
    PLAYER_PATTERN = re.compile(
        r"([A-Z][a-z]{2,})\s+(?:[A-Za-z\d]{2,4}\s+)?vs\.?\s+"
        r"([A-Z][a-z]{2,})"
    )

    # Hand 번호 패턴
    HAND_NUMBER_PATTERN = re.compile(r"Hand[\s_]*#?(\d+)|_Hand_(\d+)")

    def __init__(self):
        """초기화"""
        self._compile_patterns()

    def _compile_patterns(self):
        """정규식 패턴 컴파일"""
        self._brand_patterns = [
            (re.compile(p, re.IGNORECASE), short, full)
            for p, short, full in self.BRAND_PATTERNS
        ]
        self._location_patterns = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in self.LOCATION_PATTERNS
        ]
        self._event_patterns = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in self.EVENT_TYPE_PATTERNS
        ]
        self._content_patterns = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in self.CONTENT_TYPE_PATTERNS
        ]
        self._series_patterns = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in self.SERIES_PATTERNS
        ]

    @lru_cache(maxsize=1024)
    def extract(self, path: str, filename: str) -> ExtractedMetadata:
        """경로와 파일명에서 메타데이터 추출

        Args:
            path: 파일 전체 경로
            filename: 파일명

        Returns:
            추출된 메타데이터
        """
        combined = f"{path} {filename}"
        metadata = ExtractedMetadata()

        # 브랜드 추출
        metadata.brand = self._extract_brand(combined)

        # 연도 추출
        metadata.year = self._extract_year(path)

        # 지역 추출
        metadata.location = self._extract_location(combined)

        # 이벤트 타입 추출
        metadata.event_type = self._extract_event_type(combined)

        # 콘텐츠 타입 추출
        metadata.content_type = self._extract_content_type(combined)

        # 시리즈 추출
        metadata.series = self._extract_series(path)

        # Day/Episode 추출
        metadata.day = self._extract_day(filename)
        metadata.episode = self._extract_episode(filename)

        # 바이인 추출
        metadata.buy_in = self._extract_buy_in(combined)

        # 플레이어 추출
        metadata.players = self._extract_players(filename)

        # 태그 생성
        metadata.tags = self._generate_tags(metadata)

        # 제목 생성
        metadata.generated_title = self._generate_title(metadata, filename)

        return metadata

    def _extract_brand(self, text: str) -> Optional[str]:
        """브랜드 추출"""
        for pattern, short, _ in self._brand_patterns:
            if pattern.search(text):
                return short
        return None

    def _extract_year(self, text: str) -> Optional[int]:
        """연도 추출"""
        matches = self.YEAR_PATTERN.findall(text)
        if matches:
            # 가장 최근 연도 반환
            years = [int(y) for y in matches if 1970 <= int(y) <= 2030]
            return max(years) if years else None
        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """지역 추출"""
        for pattern, name in self._location_patterns:
            if pattern.search(text):
                return name
        return None

    def _extract_event_type(self, text: str) -> Optional[str]:
        """이벤트 타입 추출"""
        for pattern, name in self._event_patterns:
            if pattern.search(text):
                return name
        return None

    def _extract_content_type(self, text: str) -> Optional[str]:
        """콘텐츠 타입 추출"""
        for pattern, name in self._content_patterns:
            if pattern.search(text):
                return name
        return None

    def _extract_series(self, path: str) -> Optional[str]:
        """시리즈 추출"""
        for pattern, name in self._series_patterns:
            if pattern.search(path):
                return name
        return None

    def _extract_day(self, filename: str) -> Optional[str]:
        """Day 추출"""
        match = self.DAY_PATTERN.search(filename)
        if match:
            groups = [g for g in match.groups() if g]
            if groups:
                return f"Day {groups[0]}"
            if "Final" in match.group():
                return "Final Day"
        return None

    def _extract_episode(self, filename: str) -> Optional[str]:
        """Episode 추출"""
        match = self.EPISODE_PATTERN.search(filename)
        if match:
            groups = [g for g in match.groups() if g]
            if len(groups) >= 2:
                # S12-EP14 형식: Season과 Episode
                return f"S{groups[0]} E{groups[1]}"
            elif groups:
                return f"Episode {groups[0]}"
        return None

    def _extract_buy_in(self, text: str) -> Optional[str]:
        """바이인 추출"""
        match = self.BUY_IN_PATTERN.search(text)
        if match:
            groups = [g for g in match.groups() if g]
            if groups:
                amount = groups[0].replace(",", "")
                if len(amount) >= 4:
                    return f"${int(amount):,}"
                elif "K" in text.upper() or int(amount) < 100:
                    return f"${int(amount)}K"
                else:
                    return f"${int(amount):,}"
        return None

    def _extract_players(self, filename: str) -> List[str]:
        """플레이어 추출"""
        players = []
        match = self.PLAYER_PATTERN.search(filename)
        if match:
            players.extend([p.strip() for p in match.groups() if p])
        return list(set(players))

    def _generate_tags(self, metadata: ExtractedMetadata) -> List[str]:
        """태그 생성"""
        tags = []
        if metadata.brand:
            tags.append(metadata.brand)
        if metadata.year:
            tags.append(str(metadata.year))
        if metadata.location:
            tags.append(metadata.location)
        if metadata.event_type:
            tags.append(metadata.event_type)
        if metadata.content_type:
            tags.append(metadata.content_type)
        if metadata.buy_in:
            tags.append(metadata.buy_in)
        tags.extend(metadata.players)
        return tags

    def _generate_title(
        self, metadata: ExtractedMetadata, filename: str
    ) -> str:
        """스마트 제목 생성"""
        parts = []

        # Hand Clip 특수 처리
        hand_match = self.HAND_NUMBER_PATTERN.search(filename)
        if hand_match and metadata.players:
            groups = [g for g in hand_match.groups() if g]
            hand_num = groups[0] if groups else ""
            players_str = " vs ".join(metadata.players)
            return f"Hand #{hand_num}: {players_str}"

        # 브랜드
        if metadata.brand:
            parts.append(metadata.brand)

        # 지역 (브랜드와 다른 경우)
        if metadata.location and metadata.location not in str(parts):
            parts.append(metadata.location)

        # 연도
        if metadata.year:
            parts.append(str(metadata.year))

        # 이벤트 타입
        if metadata.event_type:
            parts.append(metadata.event_type)

        # 바이인
        if metadata.buy_in and metadata.buy_in not in str(parts):
            parts.append(metadata.buy_in)

        # Day
        if metadata.day:
            parts.append(metadata.day)

        # Episode
        if metadata.episode:
            parts.append(metadata.episode)

        # 콘텐츠 타입 (Clean, No Commentary 등)
        if metadata.content_type and metadata.content_type not in [
            "Stream",
            "Subclip",
        ]:
            parts.append(f"({metadata.content_type})")

        if parts:
            return " ".join(parts)

        # 폴백: 파일명 정리
        return self._clean_filename(filename)

    def _clean_filename(self, filename: str) -> str:
        """파일명 정리"""
        # 확장자 제거
        name = re.sub(r"\.[^.]+$", "", filename)
        # 언더스코어/하이픈을 공백으로
        name = re.sub(r"[_-]+", " ", name)
        # 숫자 접두사 제거 (예: 001_, 1218_)
        name = re.sub(r"^\d+\s*", "", name)
        # 연속 공백 제거
        name = re.sub(r"\s+", " ", name).strip()
        return name


class CatalogAggregator:
    """카탈로그 집계 및 다중 뷰 생성"""

    def __init__(self, extractor: DynamicCatalogExtractor):
        self.extractor = extractor

    def aggregate_by_brand(
        self, files: List[Tuple[str, str]]
    ) -> Dict[str, List[ExtractedMetadata]]:
        """브랜드별 집계"""
        result: Dict[str, List[ExtractedMetadata]] = {}
        for path, filename in files:
            metadata = self.extractor.extract(path, filename)
            brand = metadata.brand or "Unknown"
            if brand not in result:
                result[brand] = []
            result[brand].append(metadata)
        return result

    def aggregate_by_year(
        self, files: List[Tuple[str, str]]
    ) -> Dict[int, List[ExtractedMetadata]]:
        """연도별 집계"""
        result: Dict[int, List[ExtractedMetadata]] = {}
        for path, filename in files:
            metadata = self.extractor.extract(path, filename)
            year = metadata.year or 0
            if year not in result:
                result[year] = []
            result[year].append(metadata)
        return result

    def aggregate_by_location(
        self, files: List[Tuple[str, str]]
    ) -> Dict[str, List[ExtractedMetadata]]:
        """지역별 집계"""
        result: Dict[str, List[ExtractedMetadata]] = {}
        for path, filename in files:
            metadata = self.extractor.extract(path, filename)
            location = metadata.location or "Unknown"
            if location not in result:
                result[location] = []
            result[location].append(metadata)
        return result

    def aggregate_by_event_type(
        self, files: List[Tuple[str, str]]
    ) -> Dict[str, List[ExtractedMetadata]]:
        """이벤트 타입별 집계"""
        result: Dict[str, List[ExtractedMetadata]] = {}
        for path, filename in files:
            metadata = self.extractor.extract(path, filename)
            event_type = metadata.event_type or "Other"
            if event_type not in result:
                result[event_type] = []
            result[event_type].append(metadata)
        return result

    def aggregate_by_player(
        self, files: List[Tuple[str, str]]
    ) -> Dict[str, List[ExtractedMetadata]]:
        """플레이어별 집계"""
        result: Dict[str, List[ExtractedMetadata]] = {}
        for path, filename in files:
            metadata = self.extractor.extract(path, filename)
            for player in metadata.players:
                if player not in result:
                    result[player] = []
                result[player].append(metadata)
        return result

    def get_all_tags(
        self, files: List[Tuple[str, str]]
    ) -> Dict[str, int]:
        """모든 태그와 빈도 추출"""
        tag_counts: Dict[str, int] = {}
        for path, filename in files:
            metadata = self.extractor.extract(path, filename)
            for tag in metadata.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return dict(sorted(tag_counts.items(), key=lambda x: -x[1]))


def extract_catalogs_from_db(db_path: str) -> List[str]:
    """DB에서 동적으로 카탈로그 목록 추출

    Args:
        db_path: archive.db 경로

    Returns:
        카탈로그 이름 목록
    """
    import sqlite3
    from pathlib import Path

    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT DISTINCT path FROM files")
        paths = [row[0] for row in cursor.fetchall()]

        catalogs: Set[str] = set()
        for path in paths:
            parts = path.split("/")
            for i, part in enumerate(parts):
                if part == "ARCHIVE" and i + 1 < len(parts):
                    catalog = parts[i + 1]
                    if catalog:
                        catalogs.add(catalog)
                    break

        return sorted(catalogs)
    finally:
        conn.close()
