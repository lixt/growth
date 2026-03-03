from datetime import datetime
from typing import Literal, Optional, Union
from pydantic import BaseModel


class StockSuggest(BaseModel):
    ts_code: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    cnspell: Optional[str] = None


class BarPoint(BaseModel):
    ts_code: str
    time: Union[datetime, str]
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None


class TradeDate(BaseModel):
    date: str


class CalendarDayStatus(BaseModel):
    date: str
    is_open: bool
    expected_stock_count: int
    index_expected_count: int
    daily_stock_count: int
    index_daily_count: int
    index_complete: bool
    suspended_stock_count: int
    completed_stock_count: int
    unresolved_stock_count: int
    completion_rate: float
    has_any_data: bool
    is_data_complete: bool
    action: Literal["none", "pull", "clear"]


class CalendarStatusResponse(BaseModel):
    month: str
    days: list[CalendarDayStatus]


class UnresolvedStockItem(BaseModel):
    ts_code: str
    name: Optional[str] = None


class UnresolvedStocksResponse(BaseModel):
    date: str
    items: list[UnresolvedStockItem]


class IndexSnapshot(BaseModel):
    ts_code: str
    name: str
    trade_date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None


class MarketStockItem(BaseModel):
    ts_code: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    market: Optional[str] = None
    list_date: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    turnover_rate: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    circ_mv: Optional[float] = None


class MarketOverviewResponse(BaseModel):
    date: str
    indices: list[IndexSnapshot]
    page: int
    page_size: int
    total: int
    items: list[MarketStockItem]


class IndexSnapshotResponse(BaseModel):
    date: str
    indices: list[IndexSnapshot]
