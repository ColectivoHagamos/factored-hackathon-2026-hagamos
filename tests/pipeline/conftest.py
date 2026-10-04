"""Generated source files for pipeline tests. Every value is invented; no dataset record is used."""

from pathlib import Path

import pytest

from pipeline import bronze

CARD = "1234567812345678"

CUSTOMERS = [
    "customer_id,country,segment,customer_status,detected_accent,date_of_birth,registration_date,last_updated,first_name",
    "C1,Colombia,Plus,Active,colombian,1960-05-01,2020-01-01 10:00:00,2026-01-01 00:00:00,Ana",
    "C2,México,Basic,Active,,1990-02-02,2021-01-01 10:00:00,2026-01-01 00:00:00,Luis",
    "C3,Argentina,Premium,Active,argentine,1985-03-03,2022-01-01 10:00:00,2026-01-01 00:00:00,Sol",
    "C4,Colombia,VIP,Active,,1970-04-04,2022-01-01 10:00:00,2026-01-01 00:00:00,Eva",
]
PRODUCTS = [
    "product_id,customer_id,product_type,product_number,currency,product_status,opening_date,expiration_date,last_updated",
    f"P1,C1,Tarjeta Crédito,{CARD},COP,Active,2020-01-01,2028-01-01,2026-01-01 00:00:00",
    "P2,C2,Cuenta Ahorro,0012345678,USD,Active,2021-01-01,,2026-01-01 00:00:00",
    f"P3,C9,Tarjeta Débito,{CARD},USD,Active,2021-01-01,2028-01-01,2026-01-01 00:00:00",
    f"P4,C3,Tarjeta Crédito,{CARD},ARS,Blocked,2022-01-01,2029-01-01,2026-01-01 00:00:00",
]
TRANSACTION_HEADER = (
    "transaction_id,transaction_date,process_date,product_id,customer_id,transaction_type,transaction_category,"
    "amount,currency,amount_usd,channel,merchant_name,merchant_category,transaction_country,transaction_city,"
    "transaction_status,response_code,is_fraud,fraud_score"
)
TRANSACTIONS_DAY_1 = [
    "T1,2026-06-14 21:05:00,2026-06-14,P1,C1,Purchase,Transport,120000,COP,,Web,Uber,Transport,Brazil,Sao Paulo,Approved,00,True,87.5",
    "T2,2026-06-14 09:00:00,2026-06-14,P2,C2,Payment,,50.00,USD,50.00,App,,,Mexico,CDMX,Approved,00,False,",
    "T3,2026-06-14 10:00:00,2026-06-14,P1,C1,Purchase,Food,-5,COP,,POS,Store,Food,Colombia,Cali,Approved,00,False,10",
    "T4,2026-06-14 11:00:00,2026-06-14,P1,C1,Purchase,Food,10,EUR,,POS,Store,Food,Colombia,Cali,Approved,00,False,10",
    "T5,2026-06-14 12:00:00,2026-06-14,P1,C2,Purchase,Food,10,COP,,POS,Store,Food,Colombia,Cali,Approved,00,False,10",
    "T7,2026-01-10 18:00:00,2026-01-10,P1,C1,Purchase,Transport,50000,COP,12.50,App,Uber,Transport,Colombia,Cali,Approved,00,False,3",
    "T8,2026-05-02 08:00:00,2026-05-02,P2,C2,Adjustment,,4.00,USD,4.00,Branch,,,Mexico,CDMX,Approved,00,False,",
]
TRANSACTIONS_DAY_2 = [
    "T1,2026-06-14 21:05:00,2026-06-15,P1,C1,Purchase,Transport,120000,COP,,Web,Uber,Transport,Brazil,Sao Paulo,Approved,00,True,87.5",
    "T6,2026-06-16 03:00:00,2026-06-15,P4,C3,Purchase,Food,35000,ARS,,POS,,,Argentina,Rosario,Pending,,False,5",
]
COMPLAINTS = [
    "complaint_id,creation_date,process_date,customer_id,case_type,category,subcategory,claimed_amount,currency,"
    "priority,status,sla_breached,is_repeat_complainer,description",
    "K1,2026-06-10 10:00:00,2026-06-10,C1,Claim,Transactions,Cargo no reconocido,120000,COP,High,Open,False,False,texto",
    "K2,2026-06-11 10:00:00,2026-06-11,C2,Complaint,Fees,Cobro indebido,,MXN,Low,Open,False,True,texto",
    "K3,2026-06-12 10:00:00,2026-06-12,C3,Claim,Fees,Otra cosa,,,Low,Open,False,False,texto",
]
RATES = [
    "date,source_currency,target_currency,exchange_rate,buy_rate,sell_rate,source",
    "2026-06-17,COP,USD,0.00025,0.00024,0.00026,Central Bank",
    "2026-06-17,ARS,USD,0.0028,0.0027,0.0029,Central Bank",
    "2026-06-18,COP,USD,-1,0.00024,0.00026,Central Bank",
]


def write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_source(root: Path) -> Path:
    write(root / "customers.csv", CUSTOMERS)
    write(root / "products.csv", PRODUCTS)
    write(root / "transactions/year=2026/month=06/day=14/part.csv", [TRANSACTION_HEADER, *TRANSACTIONS_DAY_1])
    write(root / "transactions/year=2026/month=06/day=15/part.csv", [TRANSACTION_HEADER, *TRANSACTIONS_DAY_2])
    write(root / "complaints/year=2026/month=06/day=10/part.csv", COMPLAINTS)
    write(root / "daily_exchange_rates.csv", RATES)
    write(root / "branches.csv", ["branch_id,name", "B1,Center"])
    return root


@pytest.fixture
def lake(tmp_path: Path) -> Path:
    source = make_source(tmp_path / "data")
    bronze.run(source, tmp_path / "lake")
    return tmp_path / "lake"
