"""Data contracts of the silver layer: one module per source table used by the agent."""

from pipeline.contracts.base import Reference, Rule, TableContract
from pipeline.contracts.complaints import COMPLAINTS
from pipeline.contracts.customers import CUSTOMERS
from pipeline.contracts.exchange_rates import EXCHANGE_RATES
from pipeline.contracts.products import PRODUCTS
from pipeline.contracts.transactions import TRANSACTIONS

# Parents first: references are checked against tables that are already in silver.
CONTRACTS: tuple[TableContract, ...] = (CUSTOMERS, PRODUCTS, TRANSACTIONS, COMPLAINTS, EXCHANGE_RATES)

__all__ = ["CONTRACTS", "Reference", "Rule", "TableContract"]
