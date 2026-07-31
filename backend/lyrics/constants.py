"""Central lyrics input and structure constraints."""

SUPPORTED_LANGUAGES = frozenset({"ko", "en"})
SUPPORTED_SECTION_TYPES = frozenset(
    {
        "intro",
        "verse",
        "pre_chorus",
        "chorus",
        "post_chorus",
        "bridge",
        "outro",
        "final_chorus",
    }
)
DEFAULT_STRUCTURE = (
    "verse",
    "pre_chorus",
    "chorus",
    "verse",
    "chorus",
    "bridge",
    "final_chorus",
    "outro",
)
KPOP_STRUCTURE = (
    "intro",
    "verse",
    "pre_chorus",
    "chorus",
    "post_chorus",
    "verse",
    "pre_chorus",
    "chorus",
    "bridge",
    "final_chorus",
)
KPOP_PRESET_GENRES = frozenset(
    {"kpop_dance", "kpop_easy_listening", "kpop_performance"}
)
MAX_TOPIC_LENGTH = 500
MAX_KEYWORDS = 10
MAX_KEYWORD_LENGTH = 50
MAX_STRUCTURE_ITEMS = 20
MAX_INSTRUCTIONS_LENGTH = 1_000
MAX_RAW_LYRICS_LENGTH = 20_000
MAX_LINE_LENGTH = 120
MIN_TARGET_DURATION_SECONDS = 10
MAX_TARGET_DURATION_SECONDS = 600
