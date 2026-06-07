import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple
from urllib.parse import quote_plus


SUPPORTED_TAG_BATCH_SOURCES = ("danbooru", "gelbooru", "rule34")

SOURCE_LABELS = {
    "danbooru": "Danbooru",
    "gelbooru": "Gelbooru",
    "rule34": "Rule34",
    "rule34video": "Rule34Video",
}


@dataclass(frozen=True)
class TagBatchQuery:
    positive_tags: Sequence[str]
    negative_tags: Sequence[str]
    artist_tags: Sequence[str]
    character_tags: Sequence[str]
    general_tags: Sequence[str]


def normalize_tag(tag: str) -> str:
    """Normalizes user-entered tag text into booru-style tag tokens."""
    token = (tag or "").strip().strip(",")
    token = re.sub(r"\s+", "_", token)
    token = token.strip("_")
    return token


def parse_tag_text(text: str) -> List[str]:
    tags = []
    for raw_tag in re.split(r"[\n,]+", text or ""):
        tag = normalize_tag(raw_tag)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def build_site_query_tags(query: TagBatchQuery) -> List[str]:
    tags = []

    for group in (
        query.positive_tags,
        query.artist_tags,
        query.character_tags,
        query.general_tags,
    ):
        for tag in group:
            normalized = normalize_tag(tag)
            if normalized and normalized not in tags:
                tags.append(normalized)

    for tag in query.negative_tags:
        normalized = normalize_tag(tag.lstrip("-"))
        negative = f"-{normalized}" if normalized else ""
        if negative and negative not in tags:
            tags.append(negative)

    return tags


def build_site_url(source: str, tags: Iterable[str]) -> str:
    source = source.lower()
    encoded_tags = quote_plus(" ".join(tags))

    if source == "danbooru":
        return f"https://danbooru.donmai.us/posts?tags={encoded_tags}"
    if source == "gelbooru":
        return f"https://gelbooru.com/index.php?page=post&s=list&tags={encoded_tags}"
    if source == "rule34":
        return f"https://rule34.xxx/index.php?page=post&s=list&tags={encoded_tags}"

    raise ValueError(f"Unsupported tag batch source: {source}")


def build_tag_batch_urls(
    sources: Sequence[str],
    query: TagBatchQuery,
) -> List[Tuple[str, str]]:
    tags = build_site_query_tags(query)
    if not tags:
        return []

    urls: List[Tuple[str, str]] = []
    for source in sources:
        normalized_source = source.lower()
        if normalized_source not in SUPPORTED_TAG_BATCH_SOURCES:
            continue
        urls.append((normalized_source, build_site_url(normalized_source, tags)))
    return urls


def build_query_from_text(
    positive_text: str,
    negative_text: str,
    artist_text: str,
    character_text: str,
    general_text: str,
) -> TagBatchQuery:
    return TagBatchQuery(
        positive_tags=parse_tag_text(positive_text),
        negative_tags=parse_tag_text(negative_text),
        artist_tags=parse_tag_text(artist_text),
        character_tags=parse_tag_text(character_text),
        general_tags=parse_tag_text(general_text),
    )


def describe_sources(urls: Sequence[Tuple[str, str]]) -> Dict[str, str]:
    return {SOURCE_LABELS.get(source, source): url for source, url in urls}
