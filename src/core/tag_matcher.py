import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple


HANGUL_BASE = 0xAC00
HANGUL_END = 0xD7A3
HANGUL_INITIALS = (
    "\u3131", "\u3132", "\u3134", "\u3137", "\u3138", "\u3139",
    "\u3141", "\u3142", "\u3143", "\u3145", "\u3146", "\u3147",
    "\u3148", "\u3149", "\u314A", "\u314B", "\u314C", "\u314D",
    "\u314E",
)
HANGUL_INITIAL_SET = set(HANGUL_INITIALS)


@dataclass(frozen=True)
class IndexedTag:
    display: str
    normalized: str
    words: Tuple[str, ...]
    acronym: str
    hangul_initials: str
    is_favorite: bool = False


def normalize_search_text(text: str) -> str:
    value = (text or "").strip().lower()
    value = value.lstrip("-").strip()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value


def compact_search_text(text: str) -> str:
    value = normalize_search_text(text)
    return re.sub(r"[^0-9a-zA-Z\u3131-\u314E\uAC00-\uD7A3]+", "", value)


def is_hangul_syllable(char: str) -> bool:
    return bool(char) and HANGUL_BASE <= ord(char) <= HANGUL_END


def is_hangul_initial(char: str) -> bool:
    return char in HANGUL_INITIAL_SET


def hangul_initial(char: str) -> str:
    if is_hangul_syllable(char):
        index = (ord(char) - HANGUL_BASE) // 588
        return HANGUL_INITIALS[index]
    if is_hangul_initial(char):
        return char
    return ""


def build_hangul_initials(text: str) -> str:
    return "".join(hangul_initial(char) for char in text or "")


def _is_word_char(char: str) -> bool:
    return char.isalnum() or is_hangul_syllable(char) or is_hangul_initial(char)


def split_tag_words(tag: str) -> List[str]:
    words: List[str] = []
    current: List[str] = []

    for char in (tag or "").lower():
        if _is_word_char(char):
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []

    if current:
        words.append("".join(current))

    return words


def build_acronym(tag: str) -> str:
    return "".join(word[0] for word in split_tag_words(tag) if word)


def index_tag(tag: str, favorite_tags: Optional[Set[str]] = None) -> Optional[IndexedTag]:
    display = (tag or "").strip()
    if not display:
        return None

    normalized = normalize_search_text(display)
    favorite_lookup = favorite_tags or set()
    words = tuple(split_tag_words(display))

    return IndexedTag(
        display=display,
        normalized=normalized,
        words=words,
        acronym="".join(word[0] for word in words if word),
        hangul_initials=build_hangul_initials(display),
        is_favorite=normalized in favorite_lookup or display.lower() in favorite_lookup,
    )


def score_indexed_tag(query: str, indexed: IndexedTag) -> Optional[int]:
    query_norm = normalize_search_text(query)
    query_compact = compact_search_text(query)
    query_initials = build_hangul_initials(query)

    if not query_norm and not query_initials:
        return None

    tag_norm = indexed.normalized
    tag_space = tag_norm.replace("_", " ")

    if query_norm == tag_norm:
        return 0
    if tag_norm.startswith(query_norm):
        return 10
    if any(word == query_norm for word in indexed.words):
        return 20
    if any(word.startswith(query_norm) for word in indexed.words):
        return 30
    if len(query_compact) >= 2 and indexed.acronym.startswith(query_compact):
        return 40
    if query_initials and indexed.hangul_initials.startswith(query_initials):
        return 50
    if query_norm in tag_norm or query_norm in tag_space:
        return 60
    if len(query_compact) >= 2 and query_compact in indexed.acronym:
        return 70
    if query_initials and query_initials in indexed.hangul_initials:
        return 80

    return None


class TagSearchIndex:
    def __init__(self, tags: Optional[Iterable[str]] = None, favorite_tags: Optional[Iterable[str]] = None):
        self._favorite_tags = self._normalize_favorites(favorite_tags or [])
        self._indexed_tags: List[IndexedTag] = []
        self.set_tags(tags or [])

    def set_tags(self, tags: Iterable[str], favorite_tags: Optional[Iterable[str]] = None):
        if favorite_tags is not None:
            self._favorite_tags = self._normalize_favorites(favorite_tags)

        indexed_tags: List[IndexedTag] = []
        seen = set()
        for tag in tags:
            indexed = index_tag(tag, self._favorite_tags)
            if not indexed:
                continue

            key = indexed.normalized
            if key in seen:
                continue

            seen.add(key)
            indexed_tags.append(indexed)

        self._indexed_tags = indexed_tags

    def search(self, query: str, limit: int = 40) -> List[str]:
        matches: List[Tuple[int, int, int, str, str]] = []
        for indexed in self._indexed_tags:
            score = score_indexed_tag(query, indexed)
            if score is None:
                continue

            favorite_rank = 0 if indexed.is_favorite else 1
            matches.append((
                score,
                favorite_rank,
                len(indexed.display),
                indexed.display.lower(),
                indexed.display,
            ))

        matches.sort()
        return [match[-1] for match in matches[:limit]]

    @staticmethod
    def _normalize_favorites(favorite_tags: Iterable[str]) -> Set[str]:
        normalized = set()
        for tag in favorite_tags:
            if not tag:
                continue
            normalized.add(normalize_search_text(str(tag)))
            normalized.add(str(tag).strip().lower())
        return normalized


def find_tag_matches(
    query: str,
    tags: Sequence[str],
    limit: int = 40,
    favorite_tags: Optional[Iterable[str]] = None,
) -> List[str]:
    return TagSearchIndex(tags, favorite_tags=favorite_tags).search(query, limit=limit)
