"""
EIS Parser — zakupki.gov.ru FTP XML
Downloads XML archives from ftp.zakupki.gov.ru, parses purchase notices,
and loads them into the database.

FTP structure:
  ftp.zakupki.gov.ru/fcs_regions/{region_code}/notifications/
    currMonth/  — current month archives
    prevMonth/  — previous month

Each archive contains XML files with purchase notifications (44-FZ, 223-FZ).
"""

import ftplib
import gzip
import io
import os
import tempfile
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Generator
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

# EIS FTP config
FTP_HOST = "ftp.zakupki.gov.ru"
FTP_BASE_44 = "/fcs_regions"
FTP_BASE_223 = "/out/published"

# Regions to parse (start with a few active ones)
REGIONS_44 = [
    "Moskva_Resp",
    "Tjumenskaja_obl",
    "Hmao",
    "Sverdlovskaja_obl",
    "Sankt-Peterburg_Resp",
    "Krasnodarskij_kraj",
    "Chelyabinskaya_obl",
]

# XML namespaces used in EIS
NS = {
    "ns": "http://zakupki.gov.ru/oos/types/1",
    "ns2": "http://zakupki.gov.ru/oos/printform/1",
    "oos": "http://zakupki.gov.ru/oos/export/1",
}


class EISParser:
    """Parser for zakupki.gov.ru FTP XML data."""

    def __init__(self, db_session_factory):
        self.session_factory = db_session_factory
        self.stats = {"found": 0, "new": 0, "updated": 0, "errors": 0}

    def _connect_ftp(self) -> ftplib.FTP:
        """Connect to EIS FTP server."""
        ftp = ftplib.FTP(FTP_HOST, timeout=60)
        ftp.login()  # Anonymous login
        logger.info(f"Connected to {FTP_HOST}")
        return ftp

    def _list_archives(self, ftp: ftplib.FTP, path: str) -> list[str]:
        """List .xml.zip or .xml.gz files in directory."""
        try:
            files = ftp.nlst(path)
            return [f for f in files if f.endswith(('.xml.zip', '.xml.gz', '.xml'))]
        except ftplib.error_perm:
            logger.warning(f"Cannot list {path}")
            return []

    def _download_file(self, ftp: ftplib.FTP, filepath: str) -> bytes:
        """Download file from FTP into memory."""
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {filepath}", buf.write)
        buf.seek(0)
        return buf.read()

    def _parse_xml_44fz(self, xml_content: bytes) -> Generator[dict, None, None]:
        """
        Parse 44-FZ notification XML.
        Extracts key fields from purchase notices.
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return

        # Try different root elements
        for notice_tag in [
            ".//ns:fcsNotificationEF",       # Electronic auction
            ".//ns:fcsNotificationZK",       # Quotation request  
            ".//ns:fcsNotificationOK",       # Open contest
            ".//ns:fcsNotificationEP",       # Single source
            ".//ns:epNotificationEF",        # Electronic auction (new format)
        ]:
            for notice in root.findall(notice_tag, NS):
                yield self._extract_notice_44(notice)

    def _extract_notice_44(self, node) -> dict:
        """Extract fields from a single 44-FZ notice."""
        def _text(xpath, default=None):
            el = node.find(xpath, NS)
            return el.text.strip() if el is not None and el.text else default

        def _decimal(xpath):
            val = _text(xpath)
            if val:
                try:
                    return Decimal(val.replace(" ", "").replace(",", "."))
                except (InvalidOperation, ValueError):
                    return None
            return None

        # Purchase number
        purchase_number = _text(".//ns:purchaseNumber") or _text(".//ns:regNum") or ""
        
        # Title / object
        title = _text(".//ns:purchaseObjectInfo") or _text(".//ns:name") or "Без названия"

        # Customer
        customer_name = _text(".//ns:responsibleOrg/ns:fullName") or _text(".//ns:placer/ns:fullName")
        customer_inn = _text(".//ns:responsibleOrg/ns:INN") or _text(".//ns:placer/ns:INN")

        # Price (NMCK)
        nmck = _decimal(".//ns:lot/ns:maxPrice") or _decimal(".//ns:maxPrice")

        # Region
        region_name = _text(".//ns:placingWay/ns:name")
        
        # OKPD/OKVED codes
        okpd_codes = []
        for okpd in node.findall(".//ns:OKPD2/ns:code", NS):
            if okpd.text:
                okpd_codes.append(okpd.text.strip())

        # Purchase type
        placing_way = _text(".//ns:placingWay/ns:code") or ""
        purchase_type = self._map_purchase_type(placing_way)

        # Dates
        publish_date = _text(".//ns:publishDTInEIS") or _text(".//ns:docPublishDate")
        deadline = _text(".//ns:applEndDate") or _text(".//ns:endDate")

        # URL
        href = _text(".//ns:href")
        source_url = href or f"https://zakupki.gov.ru/epz/order/notice/ea/view/common-info.html?regNumber={purchase_number}"

        return {
            "source_id": "eis",
            "source_number": purchase_number,
            "source_url": source_url,
            "title": title[:5000],  # Truncate
            "description": _text(".//ns:purchaseObjectInfo"),
            "law_type": "44-fz",
            "purchase_type": purchase_type,
            "okpd_codes": okpd_codes[:20],
            "okved_codes": [],  # Will be mapped from OKPD later
            "nmck": nmck,
            "currency": "RUB",
            "customer_name": customer_name,
            "customer_inn": customer_inn,
            "region": region_name,
            "publish_date": self._parse_date(publish_date),
            "deadline": self._parse_date(deadline),
            "status": "active",
        }

    def _map_purchase_type(self, code: str) -> str:
        """Map EIS placing way code to our enum."""
        mapping = {
            "EF": "auction",
            "ZK": "quotation",
            "OK": "contest",
            "EP": "single_source",
        }
        for key, val in mapping.items():
            if key in code.upper():
                return val
        return "other"

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse various date formats from EIS XML."""
        if not date_str:
            return None
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d.%m.%Y"]:
            try:
                return datetime.strptime(date_str[:19], fmt[:len(date_str[:19])+2])
            except ValueError:
                continue
        return None

    async def upsert_tenders(self, tenders: list[dict]):
        """Bulk upsert tenders into database."""
        if not tenders:
            return

        async with self.session_factory() as session:
            for tender_data in tenders:
                stmt = pg_insert(
                    # Import the table object
                    __import__("app.models.database", fromlist=["Tender"]).Tender.__table__
                ).values(**tender_data)

                stmt = stmt.on_conflict_do_update(
                    constraint="uq_tender_source",
                    set_={
                        "title": stmt.excluded.title,
                        "nmck": stmt.excluded.nmck,
                        "status": stmt.excluded.status,
                        "deadline": stmt.excluded.deadline,
                        "customer_name": stmt.excluded.customer_name,
                        "updated_at": datetime.utcnow(),
                    },
                )

                try:
                    await session.execute(stmt)
                    self.stats["new"] += 1
                except Exception as e:
                    logger.error(f"Upsert error: {e}")
                    self.stats["errors"] += 1

            await session.commit()

    async def parse_region(self, region: str):
        """Parse a single region from FTP."""
        logger.info(f"Parsing region: {region}")
        ftp = self._connect_ftp()

        try:
            base_path = f"{FTP_BASE_44}/{region}/notifications/currMonth"
            archives = self._list_archives(ftp, base_path)
            logger.info(f"  Found {len(archives)} archives in {region}")

            batch = []
            for archive_path in archives[:50]:  # Limit per run
                try:
                    data = self._download_file(ftp, archive_path)

                    # Decompress if gzipped
                    if archive_path.endswith(".gz"):
                        data = gzip.decompress(data)

                    for tender in self._parse_xml_44fz(data):
                        if tender.get("source_number"):
                            batch.append(tender)
                            self.stats["found"] += 1

                        # Flush batch every 100
                        if len(batch) >= 100:
                            await self.upsert_tenders(batch)
                            batch = []

                except Exception as e:
                    logger.error(f"  Error processing {archive_path}: {e}")
                    self.stats["errors"] += 1

            # Final flush
            if batch:
                await self.upsert_tenders(batch)

        finally:
            ftp.quit()

        logger.info(f"  Region {region} done: {self.stats}")

    async def run(self, regions: Optional[list[str]] = None):
        """Run parser for specified regions (or default list)."""
        regions = regions or REGIONS_44
        logger.info(f"Starting EIS parser for {len(regions)} regions")

        for region in regions:
            try:
                await self.parse_region(region)
            except Exception as e:
                logger.error(f"Region {region} failed: {e}")

        logger.info(f"EIS parser finished: {self.stats}")
        return self.stats
