from enum import Enum, StrEnum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TvGenre(StrEnum):
    ALL = "all"
    ACTION = "action"
    ADVENTURE = "adventure"
    ANIMATION = "animation"
    AWARDS_SHOW = "awards-show"
    CHILDREN = "children"
    COMEDY = "comedy"
    CRIME = "crime"
    DOCUMENTARY = "documentary"
    DRAMA = "drama"
    FAMILY = "family"
    FANTASY = "fantasy"
    FOOD = "food"
    GAME_SHOW = "game-show"
    HISTORY = "history"
    HOME_AND_GARDEN = "home-and-garden"
    HORROR = "horror"
    INDIE = "indie"
    MARTIAL_ARTS = "martial-arts"
    MINI_SERIES = "mini-series"
    MUSICAL = "musical"
    MYSTERY = "mystery"
    NEWS = "news"
    PODCAST = "podcast"
    REALITY = "reality"
    ROMANCE = "romance"
    SCIENCE_FICTION = "science-fiction"
    SOAP = "soap"
    SPORT = "sport"
    SUSPENSE = "suspense"
    TALK_SHOW = "talk-show"
    THRILLER = "thriller"
    TRAVEL = "travel"
    WAR = "war"
    WESTERN = "western"


class MovieGenre(StrEnum):
    ALL = "all"
    ACTION = "action"
    ADVENTURE = "adventure"
    ANIMATION = "animation"
    COMEDY = "comedy"
    CRIME = "crime"
    DOCUMENTARY = "documentary"
    DRAMA = "drama"
    FAMILY = "family"
    FANTASY = "fantasy"
    FOREIGN = "foreign"
    HISTORY = "history"
    HORROR = "horror"
    MUSIC = "music"
    MYSTERY = "mystery"
    ROMANCE = "romance"
    SCIENCE_FICTION = "science-fiction"
    THRILLER = "thriller"
    TV_MOVIE = "tv-movie"
    WAR = "war"
    WESTERN = "western"


class TvType(StrEnum):
    ALL = "all-types"
    TV_SHOWS = "tv-shows"
    DOCUMENTARIES = "documentaries"
    ENTERTAINMENT = "entertainment"
    ANIMATION = "animation-filter"


class Country(StrEnum):
    ALL = "all-countries"
    US = "us"
    KR = "kr"


class YearFilter(StrEnum):
    """Named year filters. Pass a plain int (e.g. 2023) for a specific year."""

    ALL = "all-years"
    TODAY = "today"
    THIS_WEEK = "this-week"
    THIS_MONTH = "this-month"
    THIS_YEAR = "this-year"
    S2010 = "2010s"
    S2000 = "2000s"
    S1990 = "1990s"
    S1980 = "1980s"


class TvNetwork(StrEnum):
    ALL = "all-networks"
    NETFLIX = "netflix"
    DISNEY = "disney"
    PEACOCK = "peacock"
    APPLE = "appletv"
    QUIBI = "quibi"
    CBS = "cbs"
    ABC = "abc"
    FOX = "fox"
    CW = "cw"
    HBO = "hbo"
    SHOWTIME = "showtime"
    USA = "usa"
    SYFY = "syfy"
    TNT = "tnt"
    FX = "fx"
    AMC = "amc"
    ABCFAM = "abcfam"
    SHOWCASE = "showcase"
    STARZ = "starz"
    MTV = "mtv"
    LIFETIME = "lifetime"
    AE = "ae"
    TVLAND = "tvland"


class TvSort(StrEnum):
    VOTES = "votes"
    RANK = "rank"
    POPULAR_TODAY = "popular-today"  # TV only
    POPULAR_THIS_WEEK = "popular-this-week"
    POPULAR_THIS_MONTH = "popular-this-month"
    RELEASE_DATE = "release-date"
    LAST_AIR_DATE = "last-air-date"


class MovieSort(StrEnum):
    RANK = "rank"
    POPULAR_THIS_WEEK = "popular-this-week"
    POPULAR_THIS_MONTH = "popular-this-month"


class TrendingTimeframe(StrEnum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"


class TrendingSize(int, Enum):
    TOP_100 = 100
    TOP_500 = 500


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SimklIds(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # genres endpoint returns "simkl_id"; standard media objects use "simkl"
    simkl: int | None = Field(
        None,
        validation_alias=AliasChoices("simkl", "simkl_id"),
    )
    slug: str | None = None
    imdb: str | None = None
    tmdb: int | None = None
    tvdb: int | None = None
    mal: int | None = None
    anidb: int | None = None
    hulu: str | None = None
    crunchyroll: str | None = None


class SimklRating(BaseModel):
    rating: float | None = None
    votes: int | None = None


class SimklRatings(BaseModel):
    simkl: SimklRating = Field(default_factory=SimklRating)
    imdb: SimklRating | None = None
    mal: SimklRating | None = None


class SimklItem(BaseModel):
    """Base item returned by genres and trending endpoints."""

    title: str
    year: int | None = None
    date: str | None = None
    url: str | None = None
    poster: str | None = None
    rank: int | None = None
    ratings: SimklRatings | None = None
    ids: SimklIds = Field(default_factory=SimklIds)


class SimklMovie(SimklItem):
    """Movie — ids.tmdb and ids.imdb typically populated."""

    pass


class SimklShow(SimklItem):
    """TV show — ids.tvdb and ids.imdb typically populated."""

    pass


class SimklAnime(SimklItem):
    """Anime — ids.mal and ids.anidb typically populated."""

    anime_type: str | None = None  # tv | movie | special | ova | ona | music video


class SimklEpisode(BaseModel):
    """Episode-level item (check-in / history payloads)."""

    watched_at: str | None = None
    ids: SimklIds = Field(default_factory=SimklIds)
