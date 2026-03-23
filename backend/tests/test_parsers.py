"""
Tests — Parsers
Unit tests for XML/HTML parsing logic, price/date extraction, data normalization.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from app.parsers.eis_parser import EISParser
from app.parsers.rts_parser import RTSParser
from app.parsers.corporate_parser import RosneftParser, GazpromParser
from app.parsers.subcontract_parser import VsemPodryadParser


# ============================================================
# EIS Parser — XML parsing
# ============================================================

class TestEISParser:
    """Test EIS XML parsing and field extraction."""

    def setup_method(self):
        self.parser = EISParser(None)

    def test_parse_date_iso(self):
        assert self.parser._parse_date("2026-03-15T10:00:00") == datetime(2026, 3, 15, 10, 0)

    def test_parse_date_iso_tz(self):
        result = self.parser._parse_date("2026-03-15T10:00:00+03:00")
        assert result is not None
        assert result.year == 2026

    def test_parse_date_ru(self):
        result = self.parser._parse_date("15.03.2026")
        assert result == datetime(2026, 3, 15)

    def test_parse_date_short(self):
        result = self.parser._parse_date("2026-03-15")
        assert result == datetime(2026, 3, 15)

    def test_parse_date_none(self):
        assert self.parser._parse_date(None) is None
        assert self.parser._parse_date("") is None
        assert self.parser._parse_date("invalid") is None

    def test_map_purchase_type_auction(self):
        assert self.parser._map_purchase_type("EF") == "auction"
        assert self.parser._map_purchase_type("ЭА_EF_44") == "auction"

    def test_map_purchase_type_quotation(self):
        assert self.parser._map_purchase_type("ZK") == "quotation"

    def test_map_purchase_type_contest(self):
        assert self.parser._map_purchase_type("OK") == "contest"

    def test_map_purchase_type_single(self):
        assert self.parser._map_purchase_type("EP") == "single_source"

    def test_map_purchase_type_unknown(self):
        assert self.parser._map_purchase_type("XYZ") == "other"
        assert self.parser._map_purchase_type("") == "other"

    def test_parse_xml_44fz_valid(self):
        """Parse a minimal valid 44-FZ XML notification."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <export xmlns="http://zakupki.gov.ru/oos/export/1">
            <fcsNotificationEF xmlns="http://zakupki.gov.ru/oos/types/1">
                <purchaseNumber>0372100001526000142</purchaseNumber>
                <purchaseObjectInfo>Remont avtodorogi M-5</purchaseObjectInfo>
                <responsibleOrg>
                    <fullName>FKU Uprdor</fullName>
                    <INN>7453098760</INN>
                </responsibleOrg>
                <lot>
                    <maxPrice>245000000.00</maxPrice>
                </lot>
                <publishDTInEIS>2026-03-15T10:00:00</publishDTInEIS>
                <applEndDate>2026-04-01T09:00:00</applEndDate>
            </fcsNotificationEF>
        </export>""".encode("utf-8")

        results = list(self.parser._parse_xml_44fz(xml))
        assert len(results) == 1

        r = results[0]
        assert r["source_number"] == "0372100001526000142"
        assert "Remont" in r["title"]
        assert r["customer_name"] == "FKU Uprdor"
        assert r["customer_inn"] == "7453098760"
        assert r["nmck"] == Decimal("245000000.00")
        assert r["law_type"] == "44-fz"
        assert r["source_id"] == "eis"

    def test_parse_xml_empty(self):
        xml = b"""<?xml version="1.0"?><export xmlns="http://zakupki.gov.ru/oos/export/1"></export>"""
        results = list(self.parser._parse_xml_44fz(xml))
        assert len(results) == 0

    def test_parse_xml_invalid(self):
        """Gracefully handle invalid XML."""
        results = list(self.parser._parse_xml_44fz(b"not xml at all"))
        assert len(results) == 0

    def test_parse_xml_multiple(self):
        """Parse XML with multiple notices."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <export xmlns="http://zakupki.gov.ru/oos/export/1">
            <fcsNotificationEF xmlns="http://zakupki.gov.ru/oos/types/1">
                <purchaseNumber>001</purchaseNumber>
                <purchaseObjectInfo>Tender 1</purchaseObjectInfo>
                <lot><maxPrice>100</maxPrice></lot>
            </fcsNotificationEF>
            <fcsNotificationZK xmlns="http://zakupki.gov.ru/oos/types/1">
                <purchaseNumber>002</purchaseNumber>
                <purchaseObjectInfo>Tender 2</purchaseObjectInfo>
            </fcsNotificationZK>
        </export>""".encode("utf-8")
        results = list(self.parser._parse_xml_44fz(xml))
        assert len(results) >= 1


# ============================================================
# RTS Parser — price/date extraction
# ============================================================

class TestRTSParser:
    """Test RTS utility functions."""

    def setup_method(self):
        self.parser = RTSParser(None)

    def test_parse_price_simple(self):
        assert self.parser._parse_price("12 500 000,00 руб.") == Decimal("12500000.00")

    def test_parse_price_no_kopecks(self):
        assert self.parser._parse_price("89 500 000 руб") == Decimal("89500000")

    def test_parse_price_with_dot(self):
        assert self.parser._parse_price("1.500.000") == Decimal("1500000")

    def test_parse_price_empty(self):
        assert self.parser._parse_price("") is None
        assert self.parser._parse_price("Не указана") is None

    def test_parse_date_ddmmyyyy(self):
        result = self.parser._parse_date("15.03.2026")
        assert result == datetime(2026, 3, 15)

    def test_parse_date_with_time(self):
        result = self.parser._parse_date("15.03.2026 10:30")
        assert result == datetime(2026, 3, 15, 10, 30)

    def test_parse_date_invalid(self):
        assert self.parser._parse_date("не дата") is None


# ============================================================
# Corporate Parsers
# ============================================================

class TestCorporateParser:
    """Test corporate parser utilities."""

    def test_rosneft_price(self):
        p = RosneftParser(None)
        assert p._parse_price("128\xa0500\xa0000,00") == Decimal("128500000.00")

    def test_gazprom_price(self):
        p = GazpromParser(None)
        assert p._parse_price("67 300 000.00 RUB") == Decimal("67300000.00")


# ============================================================
# VsemPodryad Parser
# ============================================================

class TestVsemPodryadParser:
    """Test subcontract parser utilities."""

    def setup_method(self):
        self.parser = VsemPodryadParser(None)

    def test_extract_region_moscow(self):
        assert self.parser._extract_region("Работа в Москве, вентфасад") == "Москва"

    def test_extract_region_hmao(self):
        assert self.parser._extract_region("Бурение скважин ХМАО вахта") == "ХМАО-Югра"

    def test_extract_region_spb(self):
        assert self.parser._extract_region("Санкт-Петербург, электромонтаж") == "Санкт-Петербург"

    def test_extract_region_none(self):
        assert self.parser._extract_region("") is None
        assert self.parser._extract_region("Просто текст без региона") is None

    def test_parse_price_rub(self):
        assert self.parser._parse_price("12 800 000 руб") == Decimal("12800000")

    def test_parse_price_negotiable(self):
        assert self.parser._parse_price("Договорная") is None

    def test_parse_date(self):
        result = self.parser._parse_date("18.03.2026")
        assert result is not None
        assert result.day == 18
        assert result.month == 3
