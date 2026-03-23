"""
Seed Script — Load demo data for testing and investor presentations.
Run: python -m app.seed
"""

import asyncio
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
import random

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.models.database import (
    Tender, Company, CompanyOkved, Contact, Financial,
    SroPermit, SubcontractRequest, OkvedCode
)


# ============================================================
# OKVED CODES (our 13 target + parents)
# ============================================================
OKVEDS = [
    ("B", "Добыча полезных ископаемых", None, 0),
    ("09", "Предоставление услуг в области добычи", "B", 1),
    ("09.10", "Услуги в области добычи нефти и газа", "09", 2),
    ("C", "Обрабатывающие производства", None, 0),
    ("33", "Ремонт и монтаж машин и оборудования", "C", 1),
    ("33.12", "Ремонт машин и оборудования", "33", 2),
    ("F", "Строительство", None, 0),
    ("41", "Строительство зданий", "F", 1),
    ("41.20", "Строительство жилых и нежилых зданий", "41", 2),
    ("42", "Строительство инженерных сооружений", "F", 1),
    ("42.11", "Строительство автодорог и магистралей", "42", 2),
    ("42.21", "Строительство инженерных коммуникаций", "42", 2),
    ("43", "Специализированные строительные работы", "F", 1),
    ("43.21", "Электромонтажные работы", "43", 2),
    ("43.99", "Специализированные строительные работы, прочие", "43", 2),
    ("42.99", "Прочее инженерное строительство", "42", 2),
    ("G", "Торговля оптовая и розничная", None, 0),
    ("46", "Торговля оптовая", "G", 1),
    ("46.90", "Торговля оптовая неспециализированная", "46", 2),
    ("H", "Транспортировка и хранение", None, 0),
    ("49", "Деятельность сухопутного транспорта", "H", 1),
    ("49.41", "Грузовой автомобильный транспорт", "49", 2),
    ("J", "Деятельность в области информации и связи", None, 0),
    ("62", "Разработка ПО и консультирование", "J", 1),
    ("62.01", "Разработка программного обеспечения", "62", 2),
    ("62.02", "Консультирование в области IT", "62", 2),
    ("63", "Деятельность в области информационных технологий", "J", 1),
    ("63.11", "Обработка данных, хостинг", "63", 2),
    ("M", "Деятельность профессиональная, научная и техническая", None, 0),
    ("71", "Деятельность в области архитектуры и изысканий", "M", 1),
    ("71.12", "Инженерные изыскания", "71", 2),
]

# ============================================================
# DEMO TENDERS
# ============================================================
TENDERS = [
    {"src": "eis", "num": "0372100001526000142", "title": "Капитальный ремонт автомобильной дороги М-5 Урал км 1842-1849", "org": "ФКУ Упрдор Южный Урал", "inn": "7453098760", "price": 245000000, "region": "Челябинская обл.", "rc": 74, "law": "44-fz", "pt": "auction"},
    {"src": "eis", "num": "0372200001826000087", "title": "Перевозка строительных грузов автотранспортом", "org": "ФГУП ГУССТ №1", "inn": "7701028865", "price": 18700000, "region": "Московская обл.", "rc": 50, "law": "44-fz", "pt": "auction"},
    {"src": "eis", "num": "0173100008926000034", "title": "Строительство школы на 1100 мест в г. Тюмень", "org": "Администрация г. Тюмень", "inn": "7202000261", "price": 890000000, "region": "Тюменская обл.", "rc": 72, "law": "44-fz", "pt": "contest"},
    {"src": "eis", "num": "0362100008726000015", "title": "Поставка медицинского оборудования для ГБУЗ ОКБ", "org": "ГБУЗ Областная клиническая больница", "inn": "6658017600", "price": 34200000, "region": "Свердловская обл.", "rc": 66, "law": "44-fz", "pt": "auction"},
    {"src": "rts", "num": "RTS-2026-44182", "title": "Поставка серверного оборудования и СХД для ЦОД", "org": "ПАО МТС", "inn": "7740000076", "price": 89500000, "region": "Москва", "rc": 77, "law": "commercial", "pt": "auction"},
    {"src": "rts", "num": "RTS-2026-44290", "title": "Разработка корпоративного портала и мобильного приложения", "org": "АО Альфа-Банк", "inn": "7728168971", "price": 42000000, "region": "Москва", "rc": 77, "law": "commercial", "pt": "contest"},
    {"src": "sber", "num": "SBA-2026-18744", "title": "Модернизация системы кондиционирования серверных помещений", "org": "ПАО Сбербанк", "inn": "7707083893", "price": 15800000, "region": "Москва", "rc": 77, "law": "commercial", "pt": "quotation"},
    {"src": "rosneft", "num": "RSN-T-2026-3301", "title": "Бурение поисково-оценочных скважин на Приобском участке", "org": "ПАО НК Роснефть", "inn": "7706107510", "price": 128500000, "region": "ХМАО-Югра", "rc": 86, "law": "corporate", "pt": "other"},
    {"src": "rosneft", "num": "RSN-T-2026-3415", "title": "Обустройство кустовых площадок Ван-Ёганского месторождения", "org": "ПАО НК Роснефть", "inn": "7706107510", "price": 245000000, "region": "ХМАО-Югра", "rc": 86, "law": "corporate", "pt": "other"},
    {"src": "gazprom", "num": "GP-ZAK-2026-1148", "title": "ТО газоперекачивающих агрегатов КС Хабаровская", "org": "ПАО Газпром", "inn": "7736050003", "price": 67300000, "region": "Хабаровский край", "rc": 27, "law": "corporate", "pt": "other"},
    {"src": "gazprom", "num": "GP-ZAK-2026-1205", "title": "Строительство АГНКС в Краснодарском крае (3 объекта)", "org": "ПАО Газпром", "inn": "7736050003", "price": 186000000, "region": "Краснодарский край", "rc": 23, "law": "corporate", "pt": "other"},
    {"src": "vsem_podryad", "num": "VP-SUB-84821", "title": "Монтаж вентилируемого фасада 4500 м2, аванс 30%", "org": "ООО СтройГарант", "inn": None, "price": 12800000, "region": "Москва", "rc": 77, "law": "subcontract", "pt": "direct_request"},
    {"src": "vsem_podryad", "num": "VP-SUB-84935", "title": "Электромонтаж на складском комплексе, бригада 5-8 чел.", "org": "ИП Козлов А.С.", "inn": None, "price": 3200000, "region": "Краснодарский край", "rc": 23, "law": "subcontract", "pt": "direct_request"},
    {"src": "vsem_podryad", "num": "VP-SUB-85012", "title": "Каменщики на ЖК Северный, 12 этажей, кирпич", "org": "ООО Домострой", "inn": None, "price": 8500000, "region": "Москва", "rc": 77, "law": "subcontract", "pt": "direct_request"},
]

# ============================================================
# DEMO COMPANIES
# ============================================================
COMPANIES = [
    {"inn": "8601012345", "ogrn": "1028600508200", "name": "ООО БурСервис", "short": "БурСервис", "region": "ХМАО-Югра", "rc": 86, "dir": "Петров И.С.", "okved": "09.10", "sro": True, "wins": 42, "rev": 2800000000},
    {"inn": "7202098765", "ogrn": "1027200012345", "name": "АО Мостострой-11", "short": "Мостострой-11", "region": "Тюменская обл.", "rc": 72, "dir": "Иванов А.В.", "okved": "42.11", "sro": True, "wins": 87, "rev": 8500000000},
    {"inn": "7701234567", "ogrn": "1057700000001", "name": "ООО ТрансЛогистик", "short": "ТрансЛогистик", "region": "Москва", "rc": 77, "dir": "Сидоров К.М.", "okved": "49.41", "sro": False, "wins": 31, "rev": 1200000000},
    {"inn": "7814567890", "ogrn": "1027800000002", "name": "АО ПромИнжиниринг", "short": "ПромИнжиниринг", "region": "Санкт-Петербург", "rc": 78, "dir": "Козлова Е.А.", "okved": "71.12", "sro": True, "wins": 55, "rev": 640000000},
    {"inn": "7703456789", "ogrn": "1037700000003", "name": "ООО НефтеХимСнаб", "short": "НефтеХимСнаб", "region": "Москва", "rc": 77, "dir": "Абрамов Д.Л.", "okved": "46.90", "sro": False, "wins": 18, "rev": 3500000000},
    {"inn": "6612345678", "ogrn": "1066600000004", "name": "ООО УралЭлектроМонтаж", "short": "УралЭМ", "region": "Свердловская обл.", "rc": 66, "dir": "Волков Р.А.", "okved": "43.21", "sro": True, "wins": 24, "rev": 420000000},
    {"inn": "7709876543", "ogrn": "1167700000005", "name": "ООО ДигиталСофт", "short": "ДигиталСофт", "region": "Москва", "rc": 77, "dir": "Новиков М.П.", "okved": "62.01", "sro": False, "wins": 12, "rev": 180000000},
    {"inn": "2312345678", "ogrn": "1022300000006", "name": "ООО КубаньСтрой", "short": "КубаньСтрой", "region": "Краснодарский край", "rc": 23, "dir": "Кузнецов В.И.", "okved": "41.20", "sro": True, "wins": 36, "rev": 1100000000},
]


async def seed():
    """Main seed function."""
    engine = create_async_engine(settings.async_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        print("Seeding OKVED codes...")
        for code, name, parent, level in OKVEDS:
            section = code if len(code) == 1 else code.split(".")[0] if "." not in code and len(code) <= 2 else None
            okved = OkvedCode(code=code, name=name, parent_code=parent, level=level, section=section)
            session.add(okved)
        await session.commit()
        print(f"  {len(OKVEDS)} OKVED codes loaded")

        print("Seeding companies...")
        for cd in COMPANIES:
            company = Company(
                inn=cd["inn"], ogrn=cd["ogrn"], full_name=cd["name"], short_name=cd["short"],
                region=cd["region"], region_code=cd["rc"], director_name=cd["dir"],
                primary_okved=cd["okved"], company_type="contractor", status="active",
                has_sro=cd["sro"], tender_wins_count=cd["wins"],
                tender_wins_sum=Decimal(cd["rev"]) * 2, is_verified=True,
                egrul_updated_at=datetime.utcnow(),
                registration_date=date(random.randint(2005, 2020), random.randint(1, 12), random.randint(1, 28)),
                authorized_capital=Decimal(random.choice([10000, 100000, 1000000, 10000000])),
            )
            session.add(company)
            await session.flush()

            # Add OKVEDs
            session.add(CompanyOkved(company_id=company.id, okved_code=cd["okved"], is_primary=True))
            # Add a secondary OKVED
            extras = {"09.10": "42.21", "42.11": "43.99", "49.41": "46.90", "71.12": "42.21",
                      "46.90": "49.41", "43.21": "42.21", "62.01": "63.11", "41.20": "43.99"}
            if cd["okved"] in extras:
                session.add(CompanyOkved(company_id=company.id, okved_code=extras[cd["okved"]]))

            # Add contacts
            session.add(Contact(company_id=company.id, contact_type="email",
                                value=f"info@{cd['short'].lower().replace(' ', '')}.ru", source="website", is_primary=True))
            session.add(Contact(company_id=company.id, contact_type="phone",
                                value=f"+7 ({random.randint(300, 999)}) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
                                source="2gis"))

            # Add financials (2 years)
            for year in [2023, 2024]:
                rev = cd["rev"] * (1 + random.uniform(-0.1, 0.15))
                session.add(Financial(company_id=company.id, year=year,
                                      revenue=Decimal(int(rev)), profit=Decimal(int(rev * random.uniform(0.03, 0.12))),
                                      employees=random.randint(50, 3000)))

            # SRO
            if cd["sro"]:
                session.add(SroPermit(company_id=company.id, sro_name="НОСТРОЙ №" + str(random.randint(100, 999)),
                                      permit_number=f"СРО-{random.randint(10000, 99999)}",
                                      max_contract_sum=Decimal(random.choice([10000000, 60000000, 500000000, 3000000000])),
                                      status="active"))

        await session.commit()
        print(f"  {len(COMPANIES)} companies loaded with contacts, financials, SRO")

        print("Seeding tenders...")
        for td in TENDERS:
            tender = Tender(
                source_id=td["src"], source_number=td["num"],
                source_url=f"https://zakupki.gov.ru/epz/order/notice/ea/view/common-info.html?regNumber={td['num']}",
                title=td["title"], law_type=td["law"], purchase_type=td["pt"],
                okved_codes=[], nmck=Decimal(td["price"]), currency="RUB",
                customer_name=td["org"], customer_inn=td.get("inn"),
                region=td["region"], region_code=td["rc"],
                publish_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                deadline=datetime.utcnow() + timedelta(days=random.randint(5, 45)),
                status="active",
            )
            session.add(tender)
        await session.commit()
        print(f"  {len(TENDERS)} tenders loaded")

        print("Seeding subcontract requests...")
        requests_data = [
            {"title": "Монтаж вентфасада клинкер на защёлках", "cat": "Фасады", "desc": "Москва. 4500 м2. Аванс, оплата за объём.", "budget": "12 800 000", "region": "Москва"},
            {"title": "Электромонтаж на складском комплексе", "cat": "Электромонтаж", "desc": "Бригада 5-8 чел. Срок 2 мес., проживание.", "budget": "3 200 000", "region": "Краснодарский край"},
            {"title": "Бурение ПНП-скважин, вахта 30/30", "cat": "Бурение", "desc": "ХМАО, вахта 30/30. Аванс 30%.", "budget": "Договорная", "region": "ХМАО-Югра"},
            {"title": "Монтаж трубопровода DN300, 4.2 км", "cat": "Строительство", "desc": "Сварка нефтепровода. СРО обязательно.", "budget": "18 500 000", "region": "Оренбургская обл."},
            {"title": "Каменщики на ЖК Северный", "cat": "Строительство", "desc": "12-этажный дом, кирпичная кладка.", "budget": "от 7 000 /м3", "region": "Москва"},
        ]
        for rd in requests_data:
            req = SubcontractRequest(
                source_id="vsem_podryad", is_user_created=False,
                title=rd["title"], description=rd["desc"], category=rd["cat"],
                budget_text=rd["budget"], region=rd["region"], status="active",
                publish_date=date.today() - timedelta(days=random.randint(0, 10)),
            )
            session.add(req)
        await session.commit()
        print(f"  {len(requests_data)} requests loaded")

    print("\n✅ Seed complete!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
