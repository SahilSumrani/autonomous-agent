from packages.shared_types.prospecting import ProspectingSourceType
from services.api.app.agents.prospecting.sources.base import (
    ProspectingSource,
    UnsupportedSourceException,
)
from services.api.app.agents.prospecting.sources.instagram import InstagramSource
from services.api.app.agents.prospecting.sources.linkedin import LinkedInSource
from services.api.app.agents.prospecting.sources.reddit import RedditSource
from services.api.app.agents.prospecting.sources.threads import ThreadsSource
from services.api.app.agents.prospecting.sources.website import WebsiteSource
from services.api.app.agents.prospecting.sources.web_search import WebSearchSource


def get_source_adapter(source_type: str | ProspectingSourceType) -> ProspectingSource:
    """Resolve the appropriate platform source adapter. Raises if no dedicated adapter exists."""
    st = source_type.value if hasattr(source_type, "value") else str(source_type).upper()
    if st == ProspectingSourceType.INSTAGRAM.value:
        return InstagramSource()
    elif st == ProspectingSourceType.REDDIT.value:
        return RedditSource()
    elif st == ProspectingSourceType.THREADS.value:
        return ThreadsSource()
    elif st == ProspectingSourceType.WEBSITE.value:
        return WebsiteSource()
    elif st == ProspectingSourceType.WEB_SEARCH.value:
        return WebSearchSource()
    elif st == ProspectingSourceType.LINKEDIN.value:
        return LinkedInSource()
    else:
        raise UnsupportedSourceException(
            f"Prospecting source '{st}' does not have a dedicated adapter implemented. Generic fallback is disabled."
        )
