from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass
class ParsedEpisode:
    episode: Optional[int] = None
    episode_range: Optional[Tuple[int, int]] = None
    is_batch: bool = False

    @property
    def episodes(self) -> List[int]:
        if self.episode is not None:
            return [self.episode]
        if self.episode_range is not None:
            return list(range(self.episode_range[0], self.episode_range[1] + 1))
        return []

    def contains(self, ep: int) -> bool:
        if self.episode is not None:
            return self.episode == ep
        if self.episode_range is not None:
            return self.episode_range[0] <= ep <= self.episode_range[1]
        return False

    def sort_key(self) -> Tuple[int, int]:
        if self.episode is not None:
            return (self.episode, self.episode)
        if self.episode_range is not None:
            return (self.episode_range[0], self.episode_range[1])
        return (999999, 999999)


EPISODE_PATTERNS = [
    (re.compile(r'\b(?:E|EP|Ep\.?|Episode)\s*(\d{1,4})\b', re.I), 'single'),
    (re.compile(r'\b(\d{1,4})(?:v[0-9])?\s*(?:\s|_|\-|\.)(?:END|Fin|Final)\b', re.I), 'single'),
    (re.compile(r'\bS\d{1,2}E(\d{1,4})\b', re.I), 'single'),
    (re.compile(r'\[(\d{1,4})\]'), 'single'),
    (re.compile(r'\b(\d{1,4})\s*-\s*(\d{1,4})\b'), 'range'),
    (re.compile(r'\b(?:Eps?\.?|Episodes?)\s*(\d{1,4})\s*-\s*(\d{1,4})\b', re.I), 'range'),
    (re.compile(r'\b(\d{1,4})\s*~\s*(\d{1,4})\b'), 'range'),
    (re.compile(r'\bComplete\s*(?:Season)?\b', re.I), 'complete'),
    (re.compile(r'\bBatch\b', re.I), 'complete'),
]

SEASON_PATTERNS = [
    re.compile(r'\bS(\d{1,2})\b', re.I),
    re.compile(r'\bSeason\s*(\d{1,2})\b', re.I),
    re.compile(r'\b(\d)(?:st|nd|rd|th)\s*Season\b', re.I),
    re.compile(r'\bS(\d{1,2})E\d{1,4}\b', re.I),
    re.compile(r'\bPart\s*(\d{1,2})\b', re.I),
    re.compile(r'\bCour\s*(\d{1,2})\b', re.I),
]

SEASON_WORD_MAP = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
    '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5,
    'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
}


def parse_episode(title: str, total_episodes: Optional[int] = None) -> ParsedEpisode:
    result = ParsedEpisode()

    for pattern, ptype in EPISODE_PATTERNS:
        match = pattern.search(title)
        if match:
            if ptype == 'single':
                result.episode = int(match.group(1))
                return result
            elif ptype == 'range':
                start, end = int(match.group(1)), int(match.group(2))
                if start <= end:
                    result.episode_range = (start, end)
                    result.is_batch = True
                    return result
            elif ptype == 'complete':
                result.is_batch = True
                if total_episodes:
                    result.episode_range = (1, total_episodes)
                return result

    numbers = re.findall(r'\b(\d{1,4})\b', title)
    for num_str in numbers:
        num = int(num_str)
        if 1 <= num <= 1000:
            if num > 100 and num < 1000:
                continue
            result.episode = num
            return result

    return result


def parse_season(title: str) -> Optional[int]:
    for pattern in SEASON_PATTERNS:
        match = pattern.search(title)
        if match:
            return int(match.group(1))

    for word, season_num in SEASON_WORD_MAP.items():
        pattern = re.compile(rf'\b{word}\s*season\b', re.I)
        if pattern.search(title):
            return season_num

    if re.search(r'\b(?:Season\s*)?2\b', title) and not re.search(r'S02E\d', title):
        if re.search(r'\b2nd\s*(?:Season|Cour|Part)\b', title, flags=re.I):
            return 2

    return None


def normalize_episode_number(value: Optional[str | int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    cleaned = re.sub(r'[^0-9]', '', str(value))
    return int(cleaned) if cleaned else None


def episode_sort_key(episode: Optional[str | int]) -> Tuple[int, int]:
    normalized = normalize_episode_number(episode)
    if normalized is None:
        return (999999, 0)
    parsed = parse_episode(str(episode)) if isinstance(episode, str) else None
    if parsed and parsed.episode_range:
        return (parsed.episode_range[0], parsed.episode_range[1])
    return (normalized, normalized)


def compare_episodes(ep1: Optional[str | int], ep2: Optional[str | int]) -> bool:
    n1 = normalize_episode_number(ep1)
    n2 = normalize_episode_number(ep2)
    return n1 is not None and n2 is not None and n1 == n2
