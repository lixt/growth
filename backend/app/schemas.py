from datetime import datetime
from typing import Optional, Union
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
