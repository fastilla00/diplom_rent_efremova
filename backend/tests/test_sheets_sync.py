# Тесты логики синхронизации (без Google API и БД)
import pytest
from decimal import Decimal

from app.services.sheets_sync import (
    _norm_key,
    ACT_COLUMNS,
    _parse_decimal,
)
from app.services.dashboard_service import _months_in_period


class TestNormKey:
    """Заголовки листа «Акты»: опечатка Cумма с латинской C должна находиться как выручка."""

    def test_cyrillic_summa_maps_to_revenue(self):
        assert _norm_key("Сумма отгрузки") in ACT_COLUMNS
        assert ACT_COLUMNS[_norm_key("Сумма отгрузки")] == "revenue"

    def test_latin_c_summa_maps_to_revenue(self):
        # Таблица Income для университета: заголовок "Cумма отгрузки" (латинская C)
        key = _norm_key("Cумма отгрузки")
        assert key in ACT_COLUMNS, f"norm_key={key!r} not in ACT_COLUMNS"
        assert ACT_COLUMNS[key] == "revenue"

    def test_shipment_date_header(self):
        assert _norm_key("Дата отгрузки") in ACT_COLUMNS
        assert ACT_COLUMNS[_norm_key("Дата отгрузки")] == "shipment_date"


class TestParseDecimal:
    def test_russian_number_format(self):
        assert _parse_decimal("4 931 725,00") == Decimal("4931725.00")
        assert _parse_decimal("30 000,00") == Decimal("30000.00")

    def test_api_returns_float(self):
        assert _parse_decimal(4931725.0) == Decimal("4931725")


class TestMonthsInPeriod:
    def test_feb_2025_to_feb_2026_includes_feb_2026(self):
        from datetime import date
        start = date(2025, 2, 28)
        end = date(2026, 2, 28)
        months = _months_in_period(start, end)
        assert (2026, 2) in months
        assert len(months) == 13
