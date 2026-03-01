from typing import Optional

import tushare as ts

from app.settings import settings


class TushareProvider:
    def __init__(self):
        self._pro = ts.pro_api(settings.TUSHARE_TOKEN)

    def stock_basic(self):
        return self._pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,cnspell,market,list_date")

    def trade_cal(self, start_date=None, end_date=None):
        return self._pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date)

    def daily(self, trade_date: str):
        return self._pro.daily(trade_date=trade_date)

    def suspend_d(
        self,
        trade_date: Optional[str] = None,
        suspend_type: Optional[str] = "S",
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        params = {}
        if ts_code:
            params["ts_code"] = ts_code
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if suspend_type:
            params["suspend_type"] = suspend_type
        return self._pro.query("suspend_d", **params)
