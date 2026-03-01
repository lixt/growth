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
    daily_stock_count: int
    suspended_stock_count: int
    completed_stock_count: int
    unresolved_stock_count: int
    completion_rate: float
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
