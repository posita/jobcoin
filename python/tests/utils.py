from asyncio import AbstractEventLoop
from datetime import datetime, timezone
from fractions import Fraction
from typing import Dict, List, NamedTuple, cast

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from ..jobcoin.api import (
    AddrT,
    InsufficientFundsError,
    RawBalanceT,
    RawTransactionT,
    RawTransferTransactionT,
    frac2str,
    iso2str,
)


class TestConfig:
    API_ADDRESS_URL = "/addresses/{addr}"
    API_TRANSACTIONS_URL = "/transactions"


@pytest.fixture
def fake_client(
    loop: AbstractEventLoop,
    aiohttp_client,
) -> TestClient:
    app = web.Application()
    app["fake_db"] = FakeDb([], {})
    app.router.add_get("/addresses/{addr}", fake_addresses)
    app.router.add_get("/transactions", fake_transactions)
    app.router.add_post("/transactions", fake_transactions)

    return loop.run_until_complete(aiohttp_client(app))


class FakeDb(NamedTuple):
    transactions: List[RawTransactionT]
    addresses: Dict[AddrT, RawBalanceT]

    def append_transaction_and_update_balances(self, transaction: RawTransactionT):
        if "fromAddress" in transaction:
            from_addr = cast(RawTransferTransactionT, transaction)["fromAddress"]
            assert from_addr
            self._append_transaction_to_addr(from_addr, transaction, is_from=True)

        self.transactions.append(transaction)
        to_addr = transaction["toAddress"]
        self._append_transaction_to_addr(to_addr, transaction)

    def _append_transaction_to_addr(
        self, addr: AddrT, transaction: RawTransactionT, is_from: bool = False
    ):
        if addr in self.addresses:
            balance = self.addresses[addr]

            if is_from:
                new_balance = Fraction(balance["balance"]) - Fraction(
                    transaction["amount"]
                )

                if new_balance < 0:
                    raise InsufficientFundsError
            else:
                new_balance = Fraction(balance["balance"]) + Fraction(
                    transaction["amount"]
                )

            balance["balance"] = frac2str(new_balance)
            self.addresses[addr]["transactions"].append(transaction)
        else:
            if is_from:
                raise InsufficientFundsError
            else:
                self.addresses[addr] = {
                    "balance": transaction["amount"],
                    "transactions": [transaction],
                }


async def fake_transactions(request: web.Request):
    assert "fake_db" in request.app
    fake_db: FakeDb = request.app["fake_db"]

    if request.method == "GET":
        return web.json_response(fake_db.transactions)
    elif request.method == "POST":
        now = datetime.now(tz=timezone.utc)
        timestamp = iso2str(now)
        transaction = await request.json()
        transaction["timestamp"] = timestamp

        try:
            fake_db.append_transaction_and_update_balances(transaction)
        except InsufficientFundsError:
            return web.json_response({"error": "Insufficient Funds"}, status=422)
        else:
            return web.json_response({"status": "OK"})


async def fake_addresses(request: web.Request):
    assert request.method == "GET"
    assert "fake_db" in request.app
    fake_db: FakeDb = request.app["fake_db"]
    addr = request.match_info["addr"]
    raw_balance: RawBalanceT = (
        fake_db.addresses[addr]
        if addr in fake_db.addresses
        else {"balance": "0", "transactions": []}
    )

    return web.json_response(raw_balance)
