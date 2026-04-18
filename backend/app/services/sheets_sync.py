# EcomProfit Guard — sync data from Google Sheets
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectIntegration
from app.models.act import Act
from app.models.cost import Cost
from app.models.specialist import Specialist, SpecialistMonthlyRevenue
from app.models.metric import Metric
from app.services.google_auth import MONTH_NAMES_RU

# =============================================================================
# АКТЫ = ДОХОДЫ (приходящие деньги): выручка, акты выполненных работ.
# Лист «Акты» → таблица Act → поле revenue → на дашборде «Выручка».
# =============================================================================
# Маппинг по листу «Акты» (первая строка — названия столбцов)
ACT_COLUMNS = {
    "цех": "department",
    "подразделение цеха": "sub_department",
    "клиент": "client",
    "проект": "project_name",
    "юр. лицо клиента": "client_legal",
    "юр лицо клиента": "client_legal",
    "договор / дс / заказ": "contract",
    "договор": "contract",
    "статус документов": "doc_status",
    "задача": "task",
    "специалист": "specialist",
    "часы": "hours",
    "ставка": "rate",
    "сумма отгрузки без ндс": "revenue",
    "сумма отгрузки": "revenue",
    "cумма отгрузки": "revenue",  # опечатка с латинской C (таблица Income для университета)
    "выручка": "revenue",
    "сумма отгрузки (с ндс)": "revenue_vat",
    "сумма оплаты с ндс": "payment_vat",
    "сумма оплаты": "payment",
    "сумма оплаты (с ндс)": "payment_vat",
    "ожидание оплаты": "payment_due",
    "дата оплаты": "payment_date",
    "статус счета": "payment_status",
    "статус счета / статус оплаты": "payment_status",
    "статус оплаты": "payment_status",
    "дата акта": "act_date",
    "статус акта": "act_status",
    "дата отгрузки": "shipment_date",
    "ожидание отгрузки": "shipment_due",
    "долги по отгрузке": "shipment_debt",
    "цфо": "cfo", "компания": "company", "аккаунт": "account_manager",
    "счет": "invoice_number", "дата счета": "invoice_date",
    "номер акта": "act_number", "месяц": "period_month",
    "дата начала работ/план": "plan_start", "дата начала работ/факт": "fact_start",
    "дата окончания работ/план": "plan_end",
    "рентабельность проекта план": "profitability_plan",
    "рентабельность проекта факт / рентабельность задачи": "profitability_fact",
    "рентабельность задачи": "profitability_fact",
    "идентификатор": "external_id",
    "pm": "pm", "tl": "tl",
}

# Номера столбцов листа АКТЫ (доходы). A=0, B=1, ..., Q=16 (выручка), ...
ACT_INDEX_MAP = {
    "department": 1,      # B Цех
    "sub_department": 2,  # C
    "client": 5,          # F Клиент
    "project_name": 6,    # G Проект
    "contract": 8,        # I Договор/ДС/Заказ
    "doc_status": 9,     # J Статус документов
    "task": 10,           # K Задача
    "specialist": 13,     # N
    "hours": 14,          # O Часы
    "rate": 15,           # P Ставка
    "revenue": 16,        # Q Сумма отгрузки без ндс
    "client_legal": 17,   # R Юр лицо клиента
    "payment_vat": 18,    # S Сумма оплаты с НДС
    "payment_due": 21,    # V ожидание оплаты
    "payment_date": 22,   # W дата оплаты
    "payment_status": 23, # X Статус счета
    "act_date": 25,       # Z дата акта
    "act_status": 26,     # AA Статус акта
    "shipment_date": 24,  # Y Дата отгрузки — по ней считаем когда пришли деньги
    "shipment_due": 27,   # AB Ожидание отгрузки
    "shipment_debt": 29,  # AD Долги по отгрузке
}
# =============================================================================
# ЗАТРАТЫ = РАСХОДЫ (уходящие деньги): траты, платежи, расходы.
# Лист «Затраты» → таблица Cost → поле amount → на дашборде «Затраты».
# =============================================================================
# Номера столбцов листа ЗАТРАТЫ (расходы). A=0 (Цех), N=13 (сумма затраты), ...
COST_INDEX_MAP = {
    "cost_center": 0,    # A Цех
    "category": 1,       # B Категория
    "tag": 2,            # C
    "counterparty": 4,   # E Клиент/Контрагент
    "sheet_project": 5,  # F Проект
    "purpose": 7,        # H Задача/Назначение
    "specialist": 11,    # L
    "amount": 13,        # N Сумма затраты
    "payment_amount": 14,# O Сумма оплаты
    "payment_deadline": 15, # P Дедлайн оплаты
    "payment_date": 16,  # Q Дата оплаты
    "payment_status": 17,# R Статус оплаты
    "cost_date": 19,     # T Дата затраты
    "cost_month": 20,    # U Месяц затраты
    "debt": 21,          # V Долги по затрате
}

# Маппинг по листу «Затраты» (по заголовкам — запасной)
COST_COLUMNS = {
    "цех": "cost_center",
    "категория": "category",
    "тег": "tag",
    "проект": "sheet_project",
    "клиент/контрагент": "counterparty",
    "клиент": "counterparty",
    "контрагент": "counterparty",
    "задача/назначение": "purpose",
    "задача": "purpose",
    "назначение": "purpose",
    "специалист": "specialist",
    "сумма затраты": "amount",
    "сумма оплаты": "payment_amount",
    "дата оплаты": "payment_date",
    "дедлайн оплаты": "payment_deadline",
    "статус оплаты": "payment_status",
    "дата затраты": "cost_date",
    "месяц затраты": "cost_month",
    "долги по затрате": "debt",
    "договор/дс/заказ": "contract",
    "вид платежа": "payment_type",
}


def _norm_key(s: str) -> str:
    """Нормализует заголовок колонки Google Sheets для сопоставления с `ACT_COLUMNS` / `COST_COLUMNS`."""
    if s is None:
        return ""
    s = str(s).strip().replace("\xa0", " ").replace("\u00a0", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    s = s.lower()
    # В таблицах часто «Cумма» с латинской C — приводим к кириллице для сопоставления
    s = s.replace("\u0063\u0443\u043c\u043c\u0430", "\u0441\u0443\u043c\u043c\u0430")  # "cумма" -> "сумма"
    return s


def _row_by_indices(row: list[Any], index_map: dict[str, int]) -> dict[str, Any]:
    """Собирает словарь полей строки по фиксированным индексам столбцов (раскладка листа)."""
    out = {}
    for field, idx in index_map.items():
        if idx < len(row):
            val = row[idx]
            if isinstance(val, str):
                val = val.strip()
            out[field] = val
    return out


def _row_to_dict(row: list[str], headers: list[str], column_map: dict[str, str]) -> dict[str, Any]:
    """Сопоставляет ячейки строки заголовкам и внешнему маппингу имя_колонки → внутреннее поле."""
    out = {}
    for i, h in enumerate(headers):
        key = _norm_key(h)
        if key in column_map:
            field = column_map[key]
            val = row[i] if i < len(row) else ""
            if isinstance(val, str):
                val = val.strip()
            out[field] = val
    return out


def _parse_date(v: Any) -> date | None:
    """Парсит дату из ячейки Sheets: `date`, serial number, строки `YYYY-MM-DD` / `DD.MM.YYYY`."""
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    # Google Sheets иногда возвращает число (Excel serial: дни с 30.12.1899)
    try:
        if isinstance(v, (int, float)):
            from datetime import timedelta
            base = date(1899, 12, 30)
            return base + timedelta(days=int(float(v)))
    except (ValueError, OverflowError):
        pass
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(v: Any) -> Decimal | None:
    """Парсит денежное значение с поддержкой запятой как десятичного разделителя и пробелов."""
    if v is None or v == "":
        return None
    try:
        s = str(v).replace(",", ".")
        # Убрать все пробелы (в т.ч. неразрывный \xa0 из Google Sheets)
        for c in (" ", "\xa0", "\u00a0", "\u202f"):
            s = s.replace(c, "")
        return Decimal(s) if s else None
    except (InvalidOperation, ValueError):
        return None


def _parse_float(v: Any) -> float | None:
    """Парсит вещественное число из строки или числа."""
    if v is None or v == "":
        return None
    try:
        s = str(v).replace(",", ".")
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def _parse_int(v: Any) -> int | None:
    """Парсит целое из строки или float-представления."""
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _build_act(d: dict[str, Any], project_id: int) -> Act:
    """Создаёт ORM-модель `Act` из нормализованного словаря строки листа «Акты»."""
    return Act(
        project_id=project_id,
        external_id=d.get("external_id") or None,
        cfo=d.get("cfo"),
        department=d.get("department"),
        sub_department=d.get("sub_department"),
        company=d.get("company"),
        account_manager=d.get("account_manager"),
        client=d.get("client") or "",
        project_name=d.get("project_name"),
        client_legal=d.get("client_legal"),
        contract=d.get("contract"),
        doc_status=d.get("doc_status"),
        task=d.get("task"),
        pm=d.get("pm"),
        tl=d.get("tl"),
        specialist=d.get("specialist"),
        hours=_parse_float(d.get("hours")),
        rate=_parse_decimal(d.get("rate")),
        revenue=_parse_decimal(d.get("revenue")),
        revenue_vat=_parse_decimal(d.get("revenue_vat")),
        payment=_parse_decimal(d.get("payment")),
        payment_vat=_parse_decimal(d.get("payment_vat")),
        invoice_number=d.get("invoice_number"),
        invoice_date=_parse_date(d.get("invoice_date")),
        payment_due=_parse_date(d.get("payment_due")),
        payment_date=_parse_date(d.get("payment_date")),
        payment_status=d.get("payment_status"),
        act_number=d.get("act_number"),
        act_date=_parse_date(d.get("act_date")),
        act_status=d.get("act_status"),
        shipment_date=_parse_date(d.get("shipment_date")),
        shipment_due=_parse_date(d.get("shipment_due")),
        shipment_debt=d.get("shipment_debt"),
        plan_start=_parse_date(d.get("plan_start")),
        fact_start=_parse_date(d.get("fact_start")),
        plan_end=_parse_date(d.get("plan_end")),
        tracker_link=d.get("tracker_link"),
        profitability_plan=_parse_float(d.get("profitability_plan")),
        profitability_fact=_parse_float(d.get("profitability_fact")),
        period_month=d.get("period_month"),
    )


def _build_cost(d: dict[str, Any], project_id: int) -> Cost:
    """Создаёт ORM-модель `Cost` из словаря строки листа «Затраты»."""
    return Cost(
        project_id=project_id,
        counterparty=d.get("counterparty") or "",
        amount=_parse_decimal(d.get("amount")) or Decimal("0"),
        cost_date=_parse_date(d.get("cost_date")),
        category=d.get("category"),
        tag=d.get("tag"),
        contract=d.get("contract"),
        purpose=d.get("purpose"),
        payment_type=d.get("payment_type"),
        payment_deadline=_parse_date(d.get("payment_deadline")),
        cost_center=d.get("cost_center"),
        sheet_project=d.get("sheet_project"),
        specialist=d.get("specialist"),
        payment_amount=_parse_decimal(d.get("payment_amount")),
        payment_date=_parse_date(d.get("payment_date")),
        payment_status=d.get("payment_status"),
        cost_month=d.get("cost_month"),
        debt=d.get("debt"),
    )


# Строки листа TL/Специалисты с итоговой выручкой: строка 66 = 2024, 139 = 2025, 160 = 2026 (1-based).
# В массиве rows из API: rows[0] = строка 1, rows[65] = строка 66, rows[138] = 139, rows[159] = 160.
# Столбцы C–N (янв–дек) = индексы 2..13.
TL_REVENUE_ROW_INDICES = (65, 138, 159)  # 0-based в rows
TL_REVENUE_YEARS = (2024, 2025, 2026)
TL_MONTH_START, TL_MONTH_END = 2, 14  # C=2, N=13 → slice [2:14]


async def _write_tl_revenue_to_metrics(
    session: AsyncSession,
    project_id: int,
    rows: list[list[Any]],
) -> None:
    """Пишет эталонную выручку из уже загруженных строк листа TL (строки 66, 139, 160, столбцы C–N) в Metric."""
    if not rows:
        print(f"TL revenue: лист пустой или не загружен, строк=0 (проект {project_id})")
        return
    written = 0
    sample_2026_02 = None
    for year, row_idx in zip(TL_REVENUE_YEARS, TL_REVENUE_ROW_INDICES, strict=True):
        if row_idx >= len(rows):
            continue
        row = rows[row_idx]
        month_values = row[TL_MONTH_START:TL_MONTH_END] if len(row) >= TL_MONTH_END else row[TL_MONTH_START:]
        for month in range(1, 13):
            col_idx = month - 1
            if col_idx >= len(month_values):
                continue
            val = _parse_decimal(month_values[col_idx])
            if val is None:
                continue
            if year == 2026 and month == 2:
                sample_2026_02 = val
            existing = await session.execute(
                select(Metric).where(
                    Metric.project_id == project_id,
                    Metric.year == year,
                    Metric.month == month,
                )
            )
            m = existing.scalar_one_or_none()
            if m:
                m.revenue = val
                if m.costs is not None and val and val > 0:
                    m.profitability_pct = float((val - m.costs) / val * 100)
            else:
                session.add(Metric(project_id=project_id, year=year, month=month, revenue=val, costs=None, profitability_pct=None))
            written += 1
    await session.flush()
    msg = f"TL revenue: строк листа={len(rows)}, записано метрик={written}, проект {project_id}, февраль 2026: {sample_2026_02}"
    logger.info(msg)
    print(msg)  # всегда видно в консоли uvicorn


def _month_index(label: str) -> int | None:
    """Определяет номер месяца 1–12 по подписи (рус./англ.) или числу."""
    s = (label or "").strip().lower()[:4]
    for i, name in enumerate(MONTH_NAMES_RU, 1):
        if name.startswith(s) or s in name:
            return i
    en = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    for i, name in enumerate(en, 1):
        if name.startswith(s):
            return i
    return _parse_int(label)


# =============================================================================
# Синхронизация: загрузка листов Google Sheets → локальная БД
# =============================================================================


async def sync_project_sheets(
    session: AsyncSession,
    project_id: int,
    creds: Credentials,
) -> datetime:
    """Читает листы Акты, Затраты, TL/Специалисты и пересобирает связанные таблицы проекта.

    Args:
        session: Async-сессия SQLAlchemy.
        project_id: Идентификатор проекта с настроенной `ProjectIntegration`.
        creds: OAuth credentials пользователя Google.

    Returns:
        Время успешного завершения (`last_sync_at`).

    Raises:
        ValueError: Если у проекта нет интеграции с таблицей.
    """
    result = await session.execute(
        select(ProjectIntegration).where(ProjectIntegration.project_id == project_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise ValueError("Project has no integration")
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    now = datetime.utcnow()

    # Delete existing data for project
    await session.execute(delete(Act).where(Act.project_id == project_id))
    await session.execute(delete(Cost).where(Cost.project_id == project_id))
    specialists = await session.execute(select(Specialist.id).where(Specialist.project_id == project_id))
    for (sid,) in specialists.all():
        await session.execute(delete(SpecialistMonthlyRevenue).where(SpecialistMonthlyRevenue.specialist_id == sid))
    await session.execute(delete(Specialist).where(Specialist.project_id == project_id))
    await session.execute(delete(Metric).where(Metric.project_id == project_id))

    # ДОХОДЫ: лист «Акты» (sheet_acts) — приходящие деньги, выручка.
    # Столбцы определяем по заголовкам (первая строка), чтобы «Сумма отгрузки» и «Дата отгрузки» находились верно.
    try:
        r = sheet.values().get(
            spreadsheetId=integration.spreadsheet_id,
            range=f"'{integration.sheet_acts}'",
        ).execute()
        rows = r.get("values", [])
        if len(rows) >= 2:
            headers = rows[0]
            # Строим индекс по заголовкам: заголовок -> наш ключ (revenue, shipment_date и т.д.)
            act_index = {}
            for i, h in enumerate(headers):
                key = _norm_key(h)
                if key in ACT_COLUMNS:
                    act_index[ACT_COLUMNS[key]] = i
            # Если по заголовкам ничего не нашли — используем фиксированную раскладку
            if not act_index:
                act_index = ACT_INDEX_MAP.copy()
            for row in rows[1:]:
                if not row:
                    continue
                d = _row_by_indices(row, act_index)
                if not d.get("client"):
                    d["client"] = d.get("project_name") or "—"
                if d.get("client") or d.get("revenue"):
                    session.add(_build_act(d, project_id))
    except Exception:
        pass

    # РАСХОДЫ: лист «Затраты» (sheet_costs) — уходящие деньги, траты
    try:
        r = sheet.values().get(
            spreadsheetId=integration.spreadsheet_id,
            range=f"'{integration.sheet_costs}'",
        ).execute()
        rows = r.get("values", [])
        for row in rows[1:] if len(rows) >= 2 else []:
            if not row:
                continue
            d = _row_by_indices(row, COST_INDEX_MAP)
            if not d.get("counterparty"):
                d["counterparty"] = "—"
            amt = _parse_decimal(d.get("amount"))
            if amt is None:
                amt = Decimal("0")
            d["amount"] = amt
            if d.get("counterparty"):
                session.add(_build_cost(d, project_id))
    except Exception:
        pass

    # TL/Специалисты — Год A=0, Специалист B=1, месяцы C–N=2..13, Итого P=15. Строки 66, 139, 160 — выручка по годам.
    # Запрашиваем явно до строки 200, иначе API может вернуть только «используемый» диапазон без строки 160.
    tl_rows: list = []
    try:
        sheet_name = integration.sheet_specialists.replace("'", "''")  # экранировать кавычку в названии
        r = sheet.values().get(
            spreadsheetId=integration.spreadsheet_id,
            range=f"'{sheet_name}'!A1:P200",
        ).execute()
        tl_rows = r.get("values", [])
        print(f"Синхронизация: лист «{integration.sheet_specialists}» — загружено строк: {len(tl_rows)}")
        year_col, name_col, total_col = 0, 1, 15
        month_cols = [(i, i - 1) for i in range(2, 14)]  # C=2 -> month 1, D=3 -> 2, ...
        for row in tl_rows[1:] if len(tl_rows) >= 2 else []:
            if len(row) <= name_col:
                continue
            name = (row[name_col] or "").strip()
            if not name:
                continue
            spec = Specialist(
                project_id=project_id,
                name=name,
                specialist_type=None,
                year=_parse_int(row[year_col]) if year_col < len(row) else None,
                total_revenue=_parse_decimal(row[total_col]) if total_col < len(row) else None,
            )
            session.add(spec)
            await session.flush()
            for col_idx, month in month_cols:
                if col_idx < len(row) and row[col_idx]:
                    rev = _parse_decimal(row[col_idx]) or Decimal("0")
                    session.add(SpecialistMonthlyRevenue(specialist_id=spec.id, month=month, revenue=rev))
    except Exception:
        pass

    # Лист «Метрики» не используется — метрики считаем из актов и затрат
    await _ensure_monthly_metrics(session, project_id)

    # Эталонная выручка по месяцам из тех же rows TL: строки 66, 139, 160 (индексы 65, 138, 159), столбцы C–N
    await _write_tl_revenue_to_metrics(session, project_id, tl_rows)

    integration.last_sync_at = now
    await session.flush()
    return now


def _parse_period_month(s: str) -> tuple[int, int] | None:
    """Парсит период из period_month: 2024-01, 01.2024, янв 2024, 2024 и т.п."""
    if not s or not str(s).strip():
        return None
    s = str(s).strip().replace(",", ".").replace(" ", ".")
    parts = s.split(".")
    if len(parts) >= 2:
        a, b = parts[0], parts[1]
        if len(a) == 4 and a.isdigit() and b.isdigit():
            y, m = int(a), int(b)
            if 1 <= m <= 12 and 2020 <= y <= 2030:
                return (y, m)
        if b.isdigit() and len(b) == 4 and a.isdigit():
            m, y = int(a), int(b)
            if 1 <= m <= 12 and 2020 <= y <= 2030:
                return (y, m)
    if "-" in s:
        a, b = s.split("-", 1)[0], s.split("-", 1)[-1]
        if a.isdigit() and len(a) == 4 and b.isdigit():
            y, m = int(a), int(b)
            if 1 <= m <= 12:
                return (y, m)
    if s.isdigit() and len(s) == 4:
        y = int(s)
        if 2020 <= y <= 2030:
            return (y, 1)
    return None


async def _ensure_monthly_metrics(session: AsyncSession, project_id: int) -> None:
    """Всегда пересобираем метрики из актов и затрат (листа «Метрики» нет)."""
    from datetime import date
    await session.execute(delete(Metric).where(Metric.project_id == project_id))
    acts = await session.execute(
        select(Act.revenue, Act.shipment_date, Act.act_date, Act.period_month).where(Act.project_id == project_id)
    )
    revenue_by_ym: dict[tuple[int, int], Decimal] = {}
    for row in acts.all():
        rev = row.revenue or Decimal("0")
        # Деньги считаем по дате отгрузки, иначе по дате акта
        dt = row.shipment_date or row.act_date
        if dt:
            ym = (dt.year, dt.month)
            revenue_by_ym[ym] = revenue_by_ym.get(ym, Decimal("0")) + rev
        elif row.period_month:
            ym = _parse_period_month(row.period_month)
            if ym:
                revenue_by_ym[ym] = revenue_by_ym.get(ym, Decimal("0")) + rev
    costs = await session.execute(
        select(Cost.amount, Cost.cost_date, Cost.cost_month).where(Cost.project_id == project_id)
    )
    cost_by_ym: dict[tuple[int, int], Decimal] = {}
    for row in costs.all():
        amt = row.amount or Decimal("0")
        dt = row.cost_date
        if dt:
            ym = (dt.year, dt.month)
            cost_by_ym[ym] = cost_by_ym.get(ym, Decimal("0")) + amt
        elif getattr(row, "cost_month", None):
            ym = _parse_period_month(row.cost_month)
            if ym:
                cost_by_ym[ym] = cost_by_ym.get(ym, Decimal("0")) + amt
    today = date.today()
    all_ym = set(revenue_by_ym) | set(cost_by_ym)
    for (y, m) in all_ym:
        if (y, m) < (today.year - 5, 1) or (y, m) > (today.year + 1, 12):
            continue
        rev = revenue_by_ym.get((y, m), Decimal("0"))
        cst = cost_by_ym.get((y, m), Decimal("0"))
        pct = float((rev - cst) / rev * 100) if rev else None
        session.add(Metric(
            project_id=project_id,
            year=y,
            month=m,
            revenue=rev,
            costs=cst,
            profitability_pct=pct,
        ))
