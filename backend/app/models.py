from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Date, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(12), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    cnspell: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    market: Mapped[Optional[str]] = mapped_column(String(8))
    list_date: Mapped[Optional[str]] = mapped_column(String(8))


class TradeCal(Base):
    __tablename__ = "trade_cal"

    exchange: Mapped[str] = mapped_column(String(4), primary_key=True)
    cal_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    is_open: Mapped[int] = mapped_column(Integer)
    pretrade_date: Mapped[Optional[str]] = mapped_column(String(8))


class Bar1D(Base):
    __tablename__ = "bar_1d"

    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    vol: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))

    __table_args__ = (
        Index("ix_bar_1d_ts_code_trade_date", "ts_code", "trade_date"),
    )


class Index1D(Base):
    __tablename__ = "index_1d"

    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    pre_close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    change: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    pct_chg: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    vol: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))

    __table_args__ = (
        Index("ix_index_1d_trade_date_ts_code", "trade_date", "ts_code"),
    )


class DailyBasic1D(Base):
    __tablename__ = "daily_basic_1d"

    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    turnover_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    pe: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    pb: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    total_mv: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    circ_mv: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))

    __table_args__ = (
        Index("ix_daily_basic_1d_trade_date_ts_code", "trade_date", "ts_code"),
    )


class Bar1M(Base):
    __tablename__ = "bar_1m"

    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    trade_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    vol: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))

    __table_args__ = (
        Index("ix_bar_1m_ts_code_trade_time", "ts_code", "trade_time"),
    )


class SuspendD(Base):
    __tablename__ = "suspend_d"

    trade_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    suspend_timing: Mapped[Optional[str]] = mapped_column(String(64))
    suspend_type: Mapped[Optional[str]] = mapped_column(String(32))

    __table_args__ = (
        Index("ix_suspend_d_trade_date_ts_code", "trade_date", "ts_code"),
    )
