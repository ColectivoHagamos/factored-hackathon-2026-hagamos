"""Tests of the pseudonymized demo subset on generated files."""

import stat
from pathlib import Path

import duckdb
import pytest

from pipeline import demo, gold, silver
from pipeline.paths import REPO
from pipeline.pseudonym import invented_last4, load_or_create_key, pseudonym

KEY = bytes(range(32))
ORIGINAL_IDS = ("C1", "C2", "C3", "P1", "P2", "P4", "T1", "T6", "T7", "T8", "K1", "K2")


@pytest.fixture
def demo_db(lake: Path, tmp_path: Path) -> tuple[duckdb.DuckDBPyConnection, dict]:
    silver.run(lake, report_path=None)
    gold.run(lake)
    key_file = tmp_path / "secrets" / "demo.key"
    key_file.parent.mkdir()
    key_file.write_text(KEY.hex(), encoding="utf-8")
    summary = demo.run(lake, key_file, report_path=None)
    con = duckdb.connect(str(lake / "demo" / "demo.duckdb"), read_only=True)
    yield con, summary
    con.close()


def everything(con: duckdb.DuckDBPyConnection) -> str:
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    return "\n".join(str(con.execute(f"SELECT * FROM {table}").fetchall()) for table in tables)


def test_no_original_identifier_reaches_the_demo(demo_db):
    con, _ = demo_db
    dump = everything(con)
    assert not [original for original in ORIGINAL_IDS if f"'{original}'" in dump]
    assert pseudonym(KEY, "customer", "C1") in dump


def test_fraud_label_and_raw_score_are_absent(demo_db):
    con, _ = demo_db
    columns = {row[0] for row in con.execute("DESCRIBE charges").fetchall()}
    assert "is_fraud" not in columns and "fraud_score" not in columns
    assert {"fraud_score_band", "is_known_merchant"} <= columns
    bands = dict(con.execute("SELECT charge_ref, fraud_score_band FROM charges").fetchall())
    assert bands[pseudonym(KEY, "transaction", "T1")] == ">30"


def test_cards_use_invented_digits_and_adjustments_have_no_card(demo_db):
    con, _ = demo_db
    masked = con.execute(
        "SELECT masked_card FROM cards WHERE card_ref = $ref", {"ref": pseudonym(KEY, "product", "P1")}
    )
    assert masked.fetchone()[0] == f"•••• {invented_last4(KEY, 'P1')}"
    card = con.execute(
        "SELECT card_ref FROM charges WHERE charge_ref = $ref", {"ref": pseudonym(KEY, "transaction", "T8")}
    ).fetchone()[0]
    assert card is None


def test_customers_get_aliases_without_names(demo_db):
    con, summary = demo_db
    aliases = [row[0] for row in con.execute("SELECT alias FROM customers ORDER BY alias").fetchall()]
    assert aliases and all(alias[:2] in ("AR", "CO", "MX") and " · " in alias for alias in aliases)
    assert summary["customers"] == len(aliases)
    assert "first_name" not in {row[0] for row in con.execute("DESCRIBE customers").fetchall()}


def test_pseudonyms_are_stable_per_key_and_change_with_another_key():
    assert pseudonym(KEY, "customer", "C1") == pseudonym(KEY, "customer", "C1")
    assert pseudonym(KEY, "customer", "C1") != pseudonym(bytes(32), "customer", "C1")
    assert pseudonym(KEY, "customer", "C1").startswith("CUS-") and len(pseudonym(KEY, "customer", "C1")) == 20


def test_key_is_created_once_outside_the_repository_and_private(tmp_path: Path):
    key_file = tmp_path / "secrets" / "vera.key"
    key = load_or_create_key(key_file)
    assert len(key) == 32 and load_or_create_key(key_file) == key
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    with pytest.raises(ValueError, match="outside the repository"):
        load_or_create_key(REPO / "vera.key")
