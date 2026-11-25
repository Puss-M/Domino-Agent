"""Data connectors and their catalog."""

from .base import BaseConnector, CachedResponse, DataSourceError
from .fred import Fred
from .gdelt import GdeltNews
from .market import ASSET_LABELS, DEFAULT_ASSETS, MarketData
from .registry import DATA_SOURCES
from .sec import SecEdgar, html_to_text
from .treasury import TreasuryYields
from .worldbank import WorldBank

__all__ = [
    "ASSET_LABELS",
    "BaseConnector",
    "CachedResponse",
    "DATA_SOURCES",
    "DEFAULT_ASSETS",
    "DataSourceError",
    "Fred",
    "GdeltNews",
    "MarketData",
    "SecEdgar",
    "TreasuryYields",
    "WorldBank",
    "html_to_text",
]
