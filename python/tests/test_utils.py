from typing import List, cast

import pytest
from aiohttp.test_utils import TestServer

from ..jobcoin.api import (
    RawCreateTransactionT,
    RawTransactionT,
    RawTransferTransactionT,
)
from .utils import loop  # noqa: F401 # pylint: disable=unused-import
from .utils import FakeDb, InsufficientFundsError, fake_client


def test_fake_db() -> None:
    fake_db = FakeDb([], {})
    transactions: List[RawTransactionT] = [
        cast(
            RawCreateTransactionT,
            {
                "timestamp": "2014-04-22T13:10:01.210Z",
                "toAddress": "BobsAddress",
                "amount": "50.35",
            },
        ),
        cast(
            RawTransferTransactionT,
            {
                "timestamp": "2014-04-23T18:25:43.511Z",
                "fromAddress": "BobsAddress",
                "toAddress": "AlicesAddress",
                "amount": "30.1",
            },
        ),
    ]

    for transaction in transactions:
        fake_db.append_transaction_and_update_balances(transaction)

    assert fake_db.transactions == transactions
    assert fake_db.addresses == {
        "BobsAddress": {
            "balance": "20.25",
            "transactions": transactions,
        },
        "AlicesAddress": {
            "balance": "30.1",
            "transactions": [transactions[-1]],
        },
    }

    with pytest.raises(InsufficientFundsError):
        fake_db.append_transaction_and_update_balances(
            {
                "timestamp": "2014-04-23T18:25:44.511Z",
                "fromAddress": "BobsAddress",
                "toAddress": "AlicesAddress",
                "amount": "30.1",
            }
        )

    # Check that nothing changed
    assert fake_db.transactions == transactions
    assert fake_db.addresses == {
        "BobsAddress": {
            "balance": "20.25",
            "transactions": transactions,
        },
        "AlicesAddress": {
            "balance": "30.1",
            "transactions": [transactions[-1]],
        },
    }


async def test_fake_transactions(
    aiohttp_client,
) -> None:
    client = await fake_client(aiohttp_client)
    fake_db: FakeDb = cast(TestServer, client.server).app["fake_db"]
    assert len(fake_db.transactions) == 0

    resp = await client.get("/transactions")
    assert resp.status == 200
    data = await resp.json()
    assert data == []

    resp = await client.post(
        "/transactions", json={"toAddress": "BobsAddress", "amount": "10"}
    )
    assert resp.status == 200
    assert len(fake_db.transactions) == 1

    resp = await client.get("/transactions")
    assert resp.status == 200
    data = await resp.json()
    assert len(data) == 1
    transaction = data[0]
    assert transaction["amount"] == "10"
    assert transaction["toAddress"] == "BobsAddress"
    assert "timestamp" in transaction


async def test_fake_transactions_insufficient_funds(
    aiohttp_client,
) -> None:
    client = await fake_client(aiohttp_client)
    resp = await client.post(
        "/transactions",
        json={
            "toAddress": "AlicesAddress",
            "fromAddress": "BobsAddress",
            "amount": "20",
        },
    )
    assert resp.status == 422
    fake_db: FakeDb = cast(TestServer, client.server).app["fake_db"]
    assert fake_db.transactions == []


async def test_fake_addresses(
    aiohttp_client,
) -> None:
    client = await fake_client(aiohttp_client)
    fake_db: FakeDb = cast(TestServer, client.server).app["fake_db"]
    assert len(fake_db.addresses) == 0
    assert len(fake_db.transactions) == 0

    resp = await client.get("/addresses/BobsAddress")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"balance": "0", "transactions": []}

    resp = await client.post(
        "/transactions", json={"toAddress": "BobsAddress", "amount": "10"}
    )
    assert resp.status == 200
    assert len(fake_db.addresses) == 1
    assert len(fake_db.transactions) == 1

    resp = await client.get("/addresses/BobsAddress")
    assert resp.status == 200
    data = await resp.json()
    assert data["balance"] == "10"
    assert len(data["transactions"]) == 1
    transaction = data["transactions"][0]
    assert transaction["amount"] == "10"
    assert transaction["toAddress"] == "BobsAddress"
    assert "timestamp" in transaction
