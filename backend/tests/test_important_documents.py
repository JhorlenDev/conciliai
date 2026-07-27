from pathlib import Path

from openpyxl import Workbook

from app.api.routes import extract_important_catalog


def test_xlsx_plan_extracts_unique_account_rows(tmp_path: Path):
    path = tmp_path / "plano.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Código", "Classificação", "Nome"])
    sheet.append(["1.1", "Ativo circulante", "Caixa"])
    sheet.append(["1.1", "Outra classificação", "Caixa"])
    workbook.save(path)

    catalog = extract_important_catalog(path, ".xlsx", "plano_contas")

    assert "1.1 - Caixa" in catalog["contas"]
    assert catalog["contas"].count("1.1 - Caixa") == 1
    assert all("classificação" not in account.lower() for account in catalog["contas"])
