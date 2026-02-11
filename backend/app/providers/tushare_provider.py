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

    def pro_bar_1m(self, ts_code: str, trade_date: str):
        start = f"{trade_date} 09:25:00"
        end = f"{trade_date} 15:05:00"
        return ts.pro_bar(
            ts_code=ts_code,
            api=self._pro,
            freq="1min",
            start_date=start,
            end_date=end,
            asset="E",
        )
