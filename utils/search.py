"""
Utilidades para búsqueda y reproducción de música
Usa YouTube Music para búsquedas
"""

import asyncio
import math
from html import unescape
import re
import unicodedata
import time
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen


def _normalize_search_text(text: str) -> str:
    ydl_opts = {
def _normalize_search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _strip_title_annotations(text: str) -> str:
    cleaned_text = text or ""
    cleaned_text = re.sub(r"[\(\[\{][^\)\]\}]{0,80}[\)\]\}]", " ", cleaned_text)
    cleaned_text = re.sub(r"\s+", " ", cleaned_text)
    return cleaned_text.strip()


def _has_noise_annotations(text: str) -> bool:
    normalized_text = _normalize_search_text(text)
    noise_markers = (
        "cover",
        "covers",
        "letra",
        "lyrics",
        "lyric",
        "karaoke",
        "live",
        "en vivo",
        "acoustic",
        "instrumental",
        "speed up",
        "sped up",
        "slowed",
        "reverb",
        "visualizer",
        "visualiser",
        "fanmade",
        "edit",
        "loop",
        "1 hour",
        "hour version",
        "tutorial",
        "amv",
        "topic",
        "concierto",
        "concert",
        "festival",
        "tour",
        "show",
        "live in",
        "live from",
        "grammy",
        "grammys",
        "latin grammy",
        "latin grammys",
        "premios",
        "award",
        "awards",
        "chile",
        "mexico",
        "argentina",
        "colombia",
        "peru",
        "espana",
        "españa",
    )
    return any(marker in normalized_text for marker in noise_markers)


def _query_requests_special_version(text: str) -> bool:
    normalized_text = _normalize_search_text(text)
    requested_markers = (
        "cover",
        "covers",
        "letra",
        "lyrics",
        "lyric",
        "karaoke",
        "live",
        "en vivo",
        "acoustic",
        "instrumental",
        "speed up",
        "sped up",
        "slowed",
        "reverb",
        "visualizer",
        "visualiser",
        "fanmade",
        "edit",
        "loop",
        "1 hour",
        "hour version",
        "tutorial",
        "amv",
        "concierto",
        "concert",
        "festival",
        "tour",
        "show",
        "live in",
        "live from",
        "grammy",
        "grammys",
        "latin grammy",
        "latin grammys",
        "premios",
        "award",
        "awards",
        "chile",
        "mexico",
        "argentina",
        "colombia",
        "peru",
        "espana",
        "españa",
    )
    return any(marker in normalized_text for marker in requested_markers)


def _annotation_noise_penalty(text: str) -> float:
    annotations = re.findall(r"[\(\[\{]([^\)\]\}]{1,80})[\)\]\}]", text or "")
    if not annotations:
        return 0.0

    normalized_annotations = _normalize_search_text(" ".join(annotations))
    if not normalized_annotations:
        return 0.0

    heavy_markers = (
        "cover",
        "covers",
        "letra",
        "lyrics",
        "lyric",
        "karaoke",
        "live",
        "en vivo",
        "concierto",
        "concert",
        "festival",
        "tour",
        "show",
        "live in",
        "live from",
        "grammy",
        "grammys",
        "latin grammy",
        "latin grammys",
        "premios",
        "award",
        "awards",
        "tutorial",
        "acoustic",
        "instrumental",
        "speed up",
        "sped up",
        "slowed",
        "reverb",
        "visualizer",
        "visualiser",
        "fanmade",
        "edit",
        "loop",
        "1 hour",
        "hour version",
        "amv",
    )
    location_markers = (
        "chile",
        "mexico",
        "argentina",
        "colombia",
        "peru",
        "espana",
        "españa",
        "bogota",
        "santiago",
        "lima",
        "monterrey",
        "madrid",
    )

    if any(marker in normalized_annotations for marker in heavy_markers):
        return -18.0

    if any(marker in normalized_annotations for marker in location_markers):
        return -8.0

    return 0.0


def _split_music_query(query: str) -> tuple[str, str]:
    cleaned_query = (query or "").strip()

    normalized_query = _normalize_search_text(cleaned_query)

    for marker in (" by ", " de ", " - ", " | ", ","):
        if marker.strip() in normalized_query:
            parts = re.split(
                r"\s[-|,]\s|\sby\s|\sde\s",
                cleaned_query,
                maxsplit=1,
                flags=re.IGNORECASE,
            )
            if len(parts) >= 2:
                left_part = parts[0].strip(" -|,")
                right_part = parts[1].strip(" -|,")
                if left_part and right_part:
                    return left_part, right_part

    for separator in (" - ", " | ", ",", " by "):
        if separator in cleaned_query:
            left_part, right_part = cleaned_query.split(separator, 1)
            left_part = left_part.strip(" -|,")
            right_part = right_part.strip(" -|,")

            if left_part and right_part:
                return left_part, right_part

    return cleaned_query, ""


def _candidate_music_query_pairs(query: str) -> list[tuple[str, str]]:
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return [("", "")]

    pairs: list[tuple[str, str]] = []
    title_query, artist_query = _split_music_query(cleaned_query)
    pairs.append((title_query, artist_query))

    if artist_query:
        pairs.append((artist_query, title_query))

    if title_query and artist_query:
        title_tokens = title_query.split()
        artist_tokens = artist_query.split()
        if len(title_tokens) >= 1 and len(artist_tokens) >= 1:
            pairs.append(
                (" ".join(title_tokens[: max(1, len(title_tokens) - 1)]), artist_query)
            )
            pairs.append(
                (title_query, " ".join(artist_tokens[: max(1, len(artist_tokens) - 1)]))
            )

    if "," not in cleaned_query and " by " not in cleaned_query:
        tokens = cleaned_query.split()
        if len(tokens) >= 3:
            for split_index in range(1, len(tokens)):
                left_part = " ".join(tokens[:split_index]).strip()
                right_part = " ".join(tokens[split_index:]).strip()

                if left_part and right_part:
                    pairs.append((left_part, right_part))
                    pairs.append((right_part, left_part))

    unique_pairs: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        normalized_pair = (pair[0].strip(), pair[1].strip())
        if normalized_pair not in seen_pairs:
            seen_pairs.add(normalized_pair)
            unique_pairs.append(normalized_pair)

    return unique_pairs


def _build_music_query_variants(query: str) -> list[str]:
    """Genera variantes de búsqueda para mejorar命中率.
    
    Variantes generadas:
    - query original
    - "query audio" (para excluir lyrics/mixes)
    - "query oficial" si no tiene artista
    - "canción - artista" y "artista - canción"
    - "canción by artista" y "artista by canción"
    """
    cleaned = (query or "").strip()
    if not cleaned:
        return []
    
    variants = []
    seen = set()
    
    title, artist = _split_music_query(cleaned)
    normalized_clean = _normalize_search_text(cleaned)
    
    variants.append(cleaned)
    seen.add(normalized_clean)
    
    if "audio" not in normalized_clean and "official" not in normalized_clean:
        variants.append(f"{cleaned} audio")
        seen.add(f"{normalized_clean} audio")
    
    if not artist:
        variants.append(f"{cleaned} official")
        seen.add(f"{normalized_clean} official")
    
    if title and artist:
        combos = [
            f"{title} {artist}",
            f"{artist} {title}",
            f"{title} - {artist}",
            f"{artist} - {title}",
            f"{title} by {artist}",
            f"{artist} by {title}",
            title,
            artist,
        ]
        for combo in combos:
            norm = _normalize_search_text(combo)
            if norm and norm not in seen:
                variants.append(combo)
                seen.add(norm)
    
    return variants[:5]


def _candidate_playlist_search_queries(query: str) -> list[str]:
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return [""]

    tokens = cleaned_query.split()
    candidate_queries = [
        f"site:youtube.com/playlist {cleaned_query}",
        f"site:youtube.com/watch {cleaned_query}",
        cleaned_query,
    ]

    if len(tokens) >= 3:
        first_two = " ".join(tokens[:2]).strip()
        last_two = " ".join(tokens[-2:]).strip()
        after_first_two = " ".join(tokens[2:]).strip()
        before_last_two = " ".join(tokens[:-2]).strip()

        if first_two and after_first_two:
            candidate_queries.append(
                f"{first_two} {after_first_two} {first_two} playlist"
            )
        if last_two and before_last_two:
            candidate_queries.append(
                f"{last_two} {before_last_two} {last_two} playlist"
            )

    if "playlist" not in _normalize_search_text(cleaned_query):
        candidate_queries.append(f"{cleaned_query} playlist")
        candidate_queries.append(f"{cleaned_query} album")
        candidate_queries.append(f"site:youtube.com/playlist {cleaned_query} playlist")

    unique_queries: list[str] = []
    seen_queries: set[str] = set()
    for candidate_query in candidate_queries:
        normalized_query = candidate_query.strip()
        if normalized_query and normalized_query not in seen_queries:
            seen_queries.add(normalized_query)
            unique_queries.append(normalized_query)

        if len(unique_queries) >= 4:
            break

    return unique_queries


def _search_duckduckgo_sync(query: str, limit: int):
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    request = Request(search_url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", "ignore")

    results = []
    for match in re.finditer(
        r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', html
    ):
        href = unescape(match.group(1))
        title = re.sub(r"<.*?>", "", match.group(2))
        results.append({"title": unescape(title), "url": _decode_duckduckgo_url(href)})

        if len(results) >= limit:
            break

    return results


def _decode_duckduckgo_url(url: str) -> str:
    cleaned_url = unescape((url or "").strip())
    if cleaned_url.startswith("//duckduckgo.com/l/?"):
        parsed_url = urlparse(f"https:{cleaned_url}")
        decoded_url = parse_qs(parsed_url.query).get("uddg", [""])[0]
        if decoded_url:
            return unquote(decoded_url)

    return unquote(cleaned_url)


def _normalize_candidate_url(url: str) -> str:
    cleaned_url = (url or "").strip()
    if cleaned_url.startswith("//"):
        cleaned_url = f"https:{cleaned_url}"
    elif not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", cleaned_url):
        cleaned_url = f"https://{cleaned_url}"

    return cleaned_url


def _canonicalize_youtube_playlist_url(url: str) -> str | None:
    try:
        parsed_url = urlparse(_normalize_candidate_url(url))
    except Exception:
        return None

    host = parsed_url.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host not in {
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
        "music.youtube.com",
    }:
        return None

    playlist_id = parse_qs(parsed_url.query).get("list", [""])[0].strip()
    if not playlist_id:
        return None

    return f"https://www.youtube.com/playlist?list={playlist_id}"


def _is_youtube_playlist_url(url: str) -> bool:
    return _canonicalize_youtube_playlist_url(url) is not None


def _score_playlist_result(query: str, entry: dict) -> float:
    query_text = _normalize_search_text(query)
    title_text = _normalize_search_text(entry.get("title", ""))
    url_text = _normalize_search_text(entry.get("url", ""))

    score = 0.0
    if "/playlist" in url_text:
        score += 10.0
    if "youtube.com" in url_text:
        score += 4.0

    query_tokens = [token for token in query_text.split() if len(token) > 1]
    title_tokens = set(title_text.split())
    overlap = sum(1 for token in query_tokens if token in title_tokens)
    score += overlap * 4.0

    if "playlist" in title_text:
        score += 4.0
    if "album" in title_text:
        score += 6.0
    if "official" in title_text:
        score += 3.0
    if "radio" in title_text:
        score -= 8.0
    if "mix" in title_text or "mega mix" in title_text:
        score -= 5.0
    if "generated" in title_text or "auto generated" in title_text:
        score -= 4.0

    if query_text and query_text in title_text:
        score += 8.0

    score -= len(title_text.split()) * 0.1

    return score


async def search_public_youtube_playlist(query: str, limit: int = 5):
    """Buscar una playlist pública de YouTube por texto."""
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return None

    candidate_queries = _candidate_playlist_search_queries(cleaned_query)

    for candidate_query in candidate_queries:
        try:
            result_set = await asyncio.to_thread(
                _search_duckduckgo_sync, candidate_query, limit
            )
        except Exception as exc:
            print(f"[DUCKDUCKGO] Error buscando playlist: {exc}")
            continue

        candidate_playlists = []
        seen_urls: set[str] = set()

        for result in result_set:
            raw_url = result.get("url", "")
            if "music.youtube.com" in raw_url.lower():
                continue

            playlist_url = _canonicalize_youtube_playlist_url(raw_url)
            if playlist_url in seen_urls or playlist_url is None:
                continue

            seen_urls.add(playlist_url)
            candidate_playlists.append(
                {
                    "url": playlist_url,
                    "title": result.get("title", "Playlist"),
                }
            )

        if candidate_playlists:
            return max(
                candidate_playlists,
                key=lambda entry: _score_playlist_result(cleaned_query, entry),
            )

    return None


def _calculate_views_score(views_str: str) -> float:
    """Calcula score basado en views de YouTube Music."""
    if not views_str:
        return 0.0
    
    try:
        views_str = views_str.upper().strip()
        
        multiplier = 1.0
        if "CR" in views_str:
            multiplier = 1_000_000_000
            views_str = views_str.replace("CR", "")
        elif "M" in views_str:
            multiplier = 1_000_000
            views_str = views_str.replace("M", "")
        elif "K" in views_str:
            multiplier = 1_000
            views_str = views_str.replace("K", "")
        
        views_str = views_str.replace(",", "").replace(".", "").strip()
        if views_str:
            views = float(views_str) * multiplier
            return math.log10(views + 1) * 1.5
    except (ValueError, AttributeError):
        pass
    
    return 0.0


def _is_unwanted_content(title: str, uploader: str) -> bool:
    """Determina si el contenido es no deseado (mixes, livestreams, etc)."""
    normalized_title = _normalize_search_text(title)
    normalized_uploader = _normalize_search_text(uploader)
    
    unwanted_patterns = (
        "mix",
        "megamix",
        " Compilation ",
        "livestream",
        "live stream",
        "concierto",
        "concert",
        "festival live",
        "directo",
        "1 hour",
        " hour ",
        "loop",
        "relaxation",
        "sleep",
        "study",
        "lullaby",
        "asleep",
    )
    
    for pattern in unwanted_patterns:
        if pattern.lower() in normalized_title:
            return True
            
    return False


def _score_youtube_result_for_pair(
    title_query: str, artist_query: str, entry: dict
) -> float:
    query_text = _normalize_search_text(f"{title_query} {artist_query}".strip())
    title_query_text = _normalize_search_text(title_query)
    artist_query_text = _normalize_search_text(artist_query)
    raw_title = entry.get("title", "") or ""
    original_title_text = _normalize_search_text(raw_title)
    stripped_title = _strip_title_annotations(raw_title)
    title_text = _normalize_search_text(stripped_title)
    uploader_text = _normalize_search_text(
        entry.get("uploader") or entry.get("channel") or ""
    )
    combined_text = f"{title_text} {uploader_text}".strip()
    query_requests_special = _query_requests_special_version(
        f"{title_query} {artist_query}".strip()
    )

    official_markers = (
        "official",
        "official audio",
        "official video",
        "official music video",
        "provided to youtube",
    )
    cover_markers = (
        "cover",
        "covers",
        "letra",
        "lyrics",
        "lyric",
        "karaoke",
        "live",
        "en vivo",
        "acoustic",
        "instrumental",
        "speed up",
        "sped up",
        "slowed",
        "reverb",
        "visualizer",
        "visualiser",
        "fanmade",
        "edit",
        "loop",
        "1 hour",
        "hour version",
        "tutorial",
        "amv",
        "topic",
    )
    soft_noise_markers = (
        "album",
        "full album",
        "compilation",
        "discography",
        "mixtape",
        "mega mix",
        "mix",
        "radio",
    )

    explicit_noise_requested = any(
        marker in query_text
        for marker in (
            "cover",
            "lyrics",
            "lyric",
            "live",
            "acoustic",
            "karaoke",
            "instrumental",
            "sped up",
            "slowed",
            "reverb",
            "visualizer",
            "visualiser",
            "fanmade",
            "edit",
            "loop",
            "1 hour",
            "hour version",
        )
    )

    if not combined_text:
        return float("-inf")

    score = 0.0
    query_tokens = [token for token in query_text.split() if len(token) > 1]
    title_query_tokens = [token for token in title_query_text.split() if len(token) > 1]
    artist_query_tokens = [
        token for token in artist_query_text.split() if len(token) > 1
    ]
    combined_tokens = set(combined_text.split())
    title_words = title_text.split()
    title_tokens = set(title_words)
    uploader_tokens = set(uploader_text.split())

    overlap = sum(1 for token in query_tokens if token in combined_tokens)
    score += overlap * 6.0

    title_overlap = sum(1 for token in title_query_tokens if token in title_tokens)
    artist_title_overlap = sum(
        1 for token in artist_query_tokens if token in title_tokens
    )
    artist_uploader_overlap = sum(
        1 for token in artist_query_tokens if token in uploader_tokens
    )
    title_uploader_overlap = sum(
        1 for token in title_query_tokens if token in uploader_tokens
    )

    score += title_overlap * 8.0
    score += title_uploader_overlap * 4.0

    if artist_query_tokens:
        score += artist_title_overlap * 8.0
        score += artist_uploader_overlap * 14.0

        if artist_title_overlap == 0 and artist_uploader_overlap == 0:
            score -= 12.0

    if title_query_text and title_query_text in title_text:
        score += 10.0
    elif title_query_text and title_query_text in combined_text:
        score += 5.0

    if title_query_text and title_text == title_query_text:
        score += 20.0
    elif title_query_text and title_text.startswith(f"{title_query_text} "):
        score += 8.0

    if artist_query_text and (
        artist_query_text in uploader_text or artist_query_text in title_text
    ):
        score += 8.0

    if not artist_query_text and query_text and query_text in title_text:
        score += 6.0
    elif not artist_query_text and query_text and query_text in combined_text:
        score += 3.0

    if (
        artist_query_text
        and query_text
        and query_text in title_text
        and artist_uploader_overlap == 0
    ):
        score -= 10.0

    if len(query_tokens) >= 2:
        leading_phrase = " ".join(query_tokens[: min(3, len(query_tokens))])
        if leading_phrase in title_text:
            score += 4.0

    if _has_noise_annotations(raw_title):
        score -= 18.0

    score += _annotation_noise_penalty(raw_title)

    if original_title_text != title_text:
        score += 2.0

    if not query_requests_special and original_title_text == title_text:
        score += 6.0

    if query_requests_special and _has_noise_annotations(raw_title):
        score += 4.0

    for marker in official_markers:
        if marker in title_text or marker in uploader_text:
            score += 16.0

    for marker in cover_markers:
        if marker in title_text or marker in uploader_text:
            if query_requests_special:
                score -= 2.0
            else:
                score -= 24.0 if not explicit_noise_requested else 4.0

    for marker in soft_noise_markers:
        if marker in title_text or marker in uploader_text:
            score -= 8.0

    if artist_query_text and (
        artist_query_text in title_text or artist_query_text in uploader_text
    ):
        score += 12.0

    if title_query_text and (
        title_query_text in title_text or title_query_text in combined_text
    ):
        score += 6.0

    if title_query_text and artist_query_text:
        title_artist_pattern = f"{title_query_text} {artist_query_text}"
        artist_title_pattern = f"{artist_query_text} {title_query_text}"
        if (
            title_artist_pattern in combined_text
            or artist_title_pattern in combined_text
        ):
            score += 8.0

        raw_normalized = _normalize_search_text(raw_title)
        if raw_normalized.startswith(title_artist_pattern) or raw_normalized.startswith(
            artist_title_pattern
        ):
            score += 16.0

        if raw_normalized.startswith(
            f"{artist_query_text} - {title_query_text}"
        ) or raw_normalized.startswith(f"{title_query_text} - {artist_query_text}"):
            score += 20.0

        if (
            raw_normalized == title_artist_pattern
            or raw_normalized == artist_title_pattern
        ):
            score += 10.0

        if artist_query_text in uploader_text:
            score += 12.0

        if title_query_text in title_text and artist_query_text in uploader_text:
            score += 14.0

    if query_requests_special:
        special_markers = (
            "live",
            "en vivo",
            "concert",
            "concierto",
            "acoustic",
            "instrumental",
            "karaoke",
            "lyrics",
            "lyric",
            "tutorial",
            "cover",
            "sped up",
            "slowed",
            "reverb",
            "visualizer",
            "visualiser",
            "fanmade",
            "edit",
            "loop",
            "1 hour",
            "hour version",
            "grammy",
            "latin grammy",
            "festival",
            "tour",
            "show",
        )
        if any(
            marker in title_text or marker in uploader_text
            for marker in special_markers
        ):
            score += 18.0

        if artist_query_text and artist_query_text in uploader_text:
            score += 8.0

    duration = entry.get("duration") or 0
    if duration:
        if duration < 45:
            score -= 10.0
        elif 120 <= duration <= 300:
            score += 8.0
        elif 300 < duration <= 420:
            score += 3.0
    
    score -= len(title_text.split()) * 0.15

    views = entry.get("views", "") or ""
    if views:
        score += _calculate_views_score(views)
        
    if not artist_query_text:
        extra_noise_markers = (
            "animacion",
            "animación",
            "amv",
            "visualizer",
            "visualiser",
            "fanmade",
            "edit",
            "speed up",
            "sped up",
            "slowed",
            "reverb",
            "loop",
            "1 hour",
            "hour version",
        )
        for marker in extra_noise_markers:
            if marker in title_text or marker in uploader_text:
                score -= 10.0

        if len(query_tokens) == 1 and title_words and title_words[0] == query_tokens[0]:
            if len(title_words) > 1:
                second_word = title_words[1]
                if second_word in {"audio", "oficial", "official", "video"}:
                    score += 10.0
                else:
                    score -= 8.0

        if len(query_tokens) == 1:
            song_segment = (
                raw_title.split(" - ", 1)[1] if " - " in raw_title else raw_title
            )
            normalized_song_segment = _normalize_search_text(song_segment)
            if query_text and query_text in normalized_song_segment:
                score += 12.0
            elif query_text and query_text in title_text:
                score -= 6.0

            if len(title_words) >= 6:
                score -= 6.0

    return score


def _score_youtube_result(query: str, entry: dict) -> float:
    return max(
        _score_youtube_result_for_pair(title_query, artist_query, entry)
        for title_query, artist_query in _candidate_music_query_pairs(query)
    )


def _score_youtube_result_for_best_match(query: str, entry: dict) -> float:
    return _score_youtube_result(query, entry)


_YOUTUBE_CANDIDATE_CACHE: dict[tuple[str, int], tuple[float, list[dict]]] = {}
_YOUTUBE_VIDEO_CACHE: dict[str, tuple[float, dict]] = {}


async def search_youtube_candidates(query: str, limit: int = 5):
    """Buscar candidatos ordenados para sugerencias y selección manual.
    
    Usa YouTube Music como fuente para búsquedas de música.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []

    cache_key = (cleaned_query.lower(), limit)
    cached = _YOUTUBE_CANDIDATE_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < 30:
        return cached[1]

    candidate_videos = []
    seen_titles = set()
    seen_ids = set()

    # YouTube Music (fuente para música)
    try:
        print(f"[SEARCH] YouTube Music: {cleaned_query}")
        ytm_results = await search_youtube_music(cleaned_query, limit=limit * 3)
        
        for video in ytm_results:
            video_id = video.get("id")
            title = video.get("title", "")
            uploader = video.get("uploader", "")
            
            if not video_id:
                continue
            
            normalized_title = _normalize_search_text(title)
            if normalized_title in seen_titles:
                continue
            
            if _is_unwanted_content(title, uploader):
                continue
            
            seen_titles.add(normalized_title)
            seen_ids.add(video_id)
            
            scored_video = dict(video)
            scored_video["source"] = "ytmusic"
            scored_video["score"] = _score_youtube_result_for_best_match(
                cleaned_query, scored_video
            )
            candidate_videos.append(scored_video)
            _YOUTUBE_VIDEO_CACHE[video_id] = (now, scored_video)
        print(f"[SEARCH] YTM resultados: {len(ytm_results)}")
    except Exception as e:
        print(f"[SEARCH] Error en YouTube Music: {e}")

    if not candidate_videos:
        _YOUTUBE_CANDIDATE_CACHE[cache_key] = (now, [])
        return []

    candidate_videos.sort(
        key=lambda entry: entry.get("score", float("-inf")), reverse=True
    )
    result = candidate_videos[:limit]
    _YOUTUBE_CANDIDATE_CACHE[cache_key] = (now, result)
    return result


def resolve_youtube_candidate(token: str) -> dict | None:
    cleaned_token = (token or "").strip()
    if not cleaned_token:
        return None

    cached = _YOUTUBE_VIDEO_CACHE.get(cleaned_token)
    if not cached:
        return None

    cached_at, candidate = cached
    if time.monotonic() - cached_at >= 30:
        _YOUTUBE_VIDEO_CACHE.pop(cleaned_token, None)
        return None

    return dict(candidate)


async def search_youtube_best_match(query: str, limit: int = 8):
    """
    Buscar en YouTube y devolver el resultado más probable como pista original.

    Penaliza resultados tipo cover/letra/lyrics y favorece coincidencias de autor
    cuando el texto de búsqueda ya incluye nombre de canción + artista.
    """
    candidate_videos = await search_youtube_candidates(query, limit=limit)

    if not candidate_videos:
        return None

    return candidate_videos[0]


def is_youtube_url(text: str) -> bool:
    """Verificar si el texto es una URL de YouTube válida"""
    try:
        parsed_url = urlparse(_normalize_candidate_url(text))
    except Exception:
        return False

    host = parsed_url.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    return host in {
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
        "music.youtube.com",
    }


_YOUTUBE_MUSIC_CACHE = {}


async def search_youtube_music(query: str, limit: int = 5):
    """Buscar canciones en YouTube Music usando la API de YouTube Music.

    Args:
        query: Término de búsqueda
        limit: Número máximo de resultados

    Returns:
        Lista de diccionarios con información de las canciones
    """
    from YouTubeMusic import Search as YTM_Search

    cache_key = (query.lower(), limit)
    cached = _YOUTUBE_MUSIC_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < 60:
        return cached[1]

    try:
        print(f"[YTM] Buscando: {query}")
        
        videos = []
        processed_titles = set()
        
        for variant in _build_music_query_variants(query):
            if not variant:
                continue
                
            try:
                results = await YTM_Search(variant, limit=limit)
            except Exception as e:
                print(f"[YTM] Error en búsqueda '{variant}': {e}")
                continue
                
            if not results or not results.get("main_results"):
                continue
                
            for entry in results.get("main_results", []):
                if not entry:
                    continue
                    
                video_id = entry.get("video_id") or entry.get("id")
                if not video_id:
                    continue
                
                title = entry.get("title", "")
                if not title:
                    continue
                    
                normalized_title = _normalize_search_text(title)
                if normalized_title in processed_titles:
                    continue
                processed_titles.add(normalized_title)
                
                thumbnails = entry.get("thumbnails", [])
                thumbnail = thumbnails[0].get("url") if thumbnails else None

                duration_str = entry.get("duration", "")
                duration = 0
                if duration_str:
                    parts = duration_str.split(":")
                    if len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                
                views_str = entry.get("views", "")
                
                videos.append(
                    {
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "title": title,
                        "duration": duration,
                        "id": video_id,
                        "thumbnail": thumbnail,
                        "uploader": entry.get("channel"),
                        "channel": entry.get("channel"),
                        "views": views_str,
                    }
                )
        
        _YOUTUBE_MUSIC_CACHE[cache_key] = (now, videos)
        return videos

    except Exception as e:
        print(f"[YTM] Error buscando: {e}")
        return []
