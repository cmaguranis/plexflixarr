import logging
import re
from pathlib import Path

from src.clients.plex_client import PlexClient  # noqa: F401
from src.config import Settings

logger = logging.getLogger(__name__)

# label → (collection name, template name)
_STREAMING_META: dict[str, tuple[str, str]] = {
    "Discover_Netflix": ("Trending on Netflix", "discovery_row"),
    "Discover_AppleTV": ("Trending on Apple TV+", "discovery_row"),
    "Discover_Disney": ("Trending on Disney+", "discovery_row"),
    "Discover_Hulu": ("Trending on Hulu", "discovery_row"),
    "Discover_Crunchyroll": ("Trending on Crunchyroll", "discovery_row"),
    "Discover_Max": ("Trending on Max", "discovery_row"),
    "Discover_AMC": ("Trending on AMC", "discovery_row"),
    "Discover_AdultSwim": ("Trending on Adult Swim", "discovery_row"),
}

_GENRE_META: dict[str, tuple[str, str]] = {
    "Discover_Action": ("Popular Action", "discovery_genre_row"),
    "Discover_Comedy": ("Popular Comedy", "discovery_genre_row"),
    "Discover_Drama": ("Popular Drama", "discovery_genre_row"),
    "Discover_Horror": ("Popular Horror", "discovery_genre_row"),
    "Discover_SciFi": ("Popular Sci-Fi", "discovery_genre_row"),
    "Discover_Romance": ("Popular Romance", "discovery_genre_row"),
    "Discover_Documentary": ("Popular Documentary", "discovery_genre_row"),
    # Discover_Animation intentionally excluded — handled by the dedicated
    # "Anime & Animation" row in discovery_ui.yml
}

# Anchors used for in-place rewriting of discovery_ui.yml
_STREAMING_MARKER = "  # ── Streaming providers"
_END_RE = re.compile(r"\n\noverlays:")


def run(config: Settings | None = None) -> None:
    config = config or Settings()
    ui_path = config.KOMETA_CONFIG_PATH / "discovery_ui.yml"

    plex = PlexClient(config)
    counts = plex.fetch_label_counts(
        real_movie_libs=config.REAL_MOVIES_LIBS,
        real_show_libs=config.REAL_SHOWS_LIBS,
    )

    streaming_ordered = _sort_by_count(counts, _STREAMING_META)
    genre_ordered = _sort_by_count(counts, _GENRE_META)

    streaming_yaml = _render_section(streaming_ordered, start_prefix=10, top_n=3, rest_start=20)
    genre_yaml = _render_section(genre_ordered, start_prefix=13, top_n=3, rest_start=25)

    _rewrite(ui_path, streaming_yaml, genre_yaml)
    logger.info(
        "Updated discovery_ui.yml — streaming: %s | genres: %s",
        [m[0] for _, m in streaming_ordered],
        [m[0] for _, m in genre_ordered],
    )


def _sort_by_count(
    counts: dict[str, int],
    meta: dict[str, tuple[str, str]],
) -> list[tuple[str, tuple[str, str]]]:
    known = sorted(
        [(lbl, m) for lbl, m in meta.items() if counts.get(lbl, 0) > 0],
        key=lambda x: -counts[x[0]],
    )
    unknown = [(lbl, m) for lbl, m in meta.items() if counts.get(lbl, 0) == 0]
    return known + unknown


def _render_section(
    ordered: list[tuple[str, tuple[str, str]]],
    start_prefix: int,
    top_n: int,
    rest_start: int,
) -> str:
    lines = []
    for i, (label, (name, template)) in enumerate(ordered):
        prefix = start_prefix + i if i < top_n else rest_start + (i - top_n)
        lines.append(f"  {name}:\n    template: {{name: {template}, label_name: {label}, sort_prefix: {prefix:02d}}}\n")
    return "\n".join(lines)


def _rewrite(path: Path, streaming_yaml: str, genre_yaml: str) -> None:
    content = path.read_text()

    start_idx = content.index(_STREAMING_MARKER)
    end_match = _END_RE.search(content, start_idx)
    if not end_match:
        raise ValueError("Could not find 'overlays:' anchor in discovery_ui.yml")

    new_block = (
        "  # ── Streaming providers (auto-generated — do not edit) ─────────────────────\n"
        + streaming_yaml
        + "\n\n  # ── By genre (auto-generated — do not edit) ──────────────────────────────────\n"
        + genre_yaml
        + "\n"
    )

    path.write_text(content[:start_idx] + new_block + content[end_match.start() :])
