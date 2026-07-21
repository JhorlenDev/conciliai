from datetime import date
from decimal import Decimal

from app.services.normalization import names_similar


def invoice_is_candidate(
    statement_value: Decimal | None,
    statement_date: date | None,
    statement_name: str,
    invoice_value: Decimal | None,
    invoice_date: date | None,
    supplier_name: str,
) -> bool:
    """Value alone is never a sufficient invoice match."""
    return bool(
        statement_value is not None
        and statement_value == invoice_value
        and statement_date == invoice_date
        and names_similar(statement_name, supplier_name)
    )
