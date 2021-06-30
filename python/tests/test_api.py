from datetime import datetime, timezone
from fractions import Fraction
from typing import List, cast

import pytest

from ..jobcoin.api import (
    Balance,
    InsufficientFundsError,
    RawBalanceT,
    RawCreateTransactionT,
    RawTransactionT,
    RawTransferTransactionT,
    Transaction,
    frac2str,
    iso2str,
    str2iso,
)
from .utils import loop  # noqa: F401 # pylint: disable=unused-import
from .utils import test_api


def test_frac2str() -> None:
    for tenths in range(1, 10):
        assert frac2str(Fraction(tenths, 10)) == "0.{}".format(tenths)


def test_iso2str() -> None:
    dt = datetime(2021, 7, 1, 12, 34, 56, 789000, tzinfo=timezone.utc)
    assert iso2str(dt) == "2021-07-01T12:34:56.789Z"
    assert str2iso(iso2str(dt)) == dt


def test_balance() -> None:
    raw_balance: RawBalanceT = {
        "balance": "20.25",
        "transactions": [
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
        ],
    }

    assert Balance.from_raw("BobsAddress", raw_balance) == Balance(
        addr="BobsAddress",
        balance=Fraction(2025, 100),
        transactions=(
            Transaction(
                timestamp=datetime(2014, 4, 22, 13, 10, 1, 210000, tzinfo=timezone.utc),
                to_addr="BobsAddress",
                amount=Fraction(5035, 100),
            ),
            Transaction(
                timestamp=datetime(
                    2014, 4, 23, 18, 25, 43, 511000, tzinfo=timezone.utc
                ),
                from_addr="BobsAddress",
                to_addr="AlicesAddress",
                amount=Fraction(3010, 100),
            ),
        ),
    )


def test_transaction() -> None:
    raw_transactions: List[RawTransactionT] = [
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

    transactions = [
        Transaction(
            timestamp=datetime(2014, 4, 22, 13, 10, 1, 210000, tzinfo=timezone.utc),
            to_addr="BobsAddress",
            amount=Fraction(5035, 100),
        ),
        Transaction(
            timestamp=datetime(2014, 4, 23, 18, 25, 43, 511000, tzinfo=timezone.utc),
            from_addr="BobsAddress",
            to_addr="AlicesAddress",
            amount=Fraction(3010, 100),
        ),
    ]

    assert [Transaction.from_raw(t) for t in raw_transactions] == transactions
    assert [t.to_raw() for t in transactions] == raw_transactions


async def test_api_balances(
    aiohttp_client,
) -> None:
    api = await test_api(aiohttp_client)

    bob_balance = await api.get_balance_for_address("BobsAddress")
    assert bob_balance.balance == Fraction(0)
    assert len(bob_balance.transactions) == 0

    alice_balance = await api.get_balance_for_address("AlicesAddress")
    assert alice_balance.balance == Fraction(0)
    assert len(alice_balance.transactions) == 0

    resp = await api.client.post(
        "/transactions", json={"toAddress": "BobsAddress", "amount": "10"}
    )
    assert resp.status == 200

    bob_balance = await api.get_balance_for_address("BobsAddress")
    assert bob_balance.balance == Fraction(10)
    assert len(bob_balance.transactions) == 1

    alice_balance = await api.get_balance_for_address("AlicesAddress")
    assert alice_balance.balance == Fraction(0)
    assert len(alice_balance.transactions) == 0

    await api.post_transfer("BobsAddress", "AlicesAddress", Fraction(5))

    bob_balance = await api.get_balance_for_address("BobsAddress")
    assert bob_balance.balance == Fraction(5)
    assert len(bob_balance.transactions) == 2

    alice_balance = await api.get_balance_for_address("AlicesAddress")
    assert alice_balance.balance == Fraction(5)
    assert len(alice_balance.transactions) == 1


async def test_api_transactions(
    aiohttp_client,
) -> None:
    api = await test_api(aiohttp_client)
    transactions = await api.get_transactions()
    assert len(transactions) == 0

    resp = await api.client.post(
        "/transactions", json={"toAddress": "BobsAddress", "amount": "10"}
    )
    assert resp.status == 200

    transactions = await api.get_transactions()
    assert len(transactions) == 1
    transaction = transactions[-1]
    assert transaction.to_addr == "BobsAddress"
    assert transaction.amount == Fraction(10)

    await api.post_transfer("BobsAddress", "AlicesAddress", Fraction(5))

    transactions = await api.get_transactions()
    assert len(transactions) == 2
    transaction = transactions[-1]
    assert transaction.to_addr == "AlicesAddress"
    assert transaction.from_addr == "BobsAddress"
    assert transaction.amount == Fraction(5)


async def test_api_transactions_insufficient_funds(
    aiohttp_client,
) -> None:
    api = await test_api(aiohttp_client)
    transactions = await api.get_transactions()
    assert len(transactions) == 0

    with pytest.raises(InsufficientFundsError):
        await api.post_transfer("BobsAddress", "AlicesAddress", Fraction(5))
