"""Wiki 资产模块"""

from server.core.wiki.ingest import ingest_laws
from server.core.wiki.store import get_page, search_pages, upsert_page

__all__ = ["ingest_laws", "get_page", "search_pages", "upsert_page"]
