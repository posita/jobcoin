import re
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from typing import (
    List,
    NamedTuple,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    cast,
)

from aiohttp import ClientSession
from aiohttp.web import HTTPException

from . import config

AddrT = str

RawCreateTransactionT = TypedDict(
    "RawCreateTransactionT",
    {
        "timestamp": str,
        "toAddress": str,
        "amount": str,
    },
)

RawTransferTransactionT = TypedDict(
    "RawTransferTransactionT",
    {
        "timestamp": str,
        "toAddress": str,
        "fromAddress": str,
        "amount": str,
    },
)

RawTransactionT = Union[RawCreateTransactionT, RawTransferTransactionT]

RawBalanceT = TypedDict(
    "RawBalanceT",
    {
        "balance": str,
        "transactions": List[RawTransactionT],
    },
)


class Transaction(NamedTuple):
    timestamp: datetime
    amount: Fraction
    to_addr: AddrT
    from_addr: Optional[AddrT] = None

    @staticmethod
    def from_raw(raw_transaction: RawTransactionT) -> "Transaction":
        return Transaction(
            timestamp=str2iso(raw_transaction["timestamp"]),
            from_addr=cast(Optional[str], raw_transaction.get("fromAddress")) or None,
            to_addr=raw_transaction["toAddress"],
            amount=Fraction(raw_transaction["amount"]),
        )

    def to_raw(self) -> RawTransactionT:
        if self.from_addr is None:
            return {
                "timestamp": iso2str(self.timestamp),
                "toAddress": self.to_addr,
                "amount": frac2str(self.amount),
            }
        else:
            assert self.from_addr

            return {
                "timestamp": iso2str(self.timestamp),
                "fromAddress": self.from_addr,
                "toAddress": self.to_addr,
                "amount": frac2str(self.amount),
            }


class Balance(NamedTuple):
    addr: AddrT
    balance: Fraction
    transactions: Tuple[Transaction, ...]

    @staticmethod
    def from_raw(addr: AddrT, raw_balance: RawBalanceT) -> "Balance":
        return Balance(
            addr=addr,
            balance=Fraction(raw_balance["balance"]),
            transactions=tuple(
                Transaction.from_raw(t) for t in raw_balance["transactions"]
            ),
        )


class Config(Protocol):
    API_ADDRESS_URL: str
    API_TRANSACTIONS_URL: str


class InsufficientFundsError(Exception):
    pass


class Api:
    def __init__(
        self,
        client: ClientSession,
        config: Config = cast(Config, config),  # pylint: disable=redefined-outer-name
    ):
        self.client = client
        self.config = config

    def now(self) -> datetime:
        # This is an odd place for this, but we need some way to replace the notion of
        # "now" for reconciliation with a deterministic clock in testing
        return datetime.now(tz=timezone.utc)

    async def get_balance_for_address(
        self,
        addr: AddrT,
    ) -> Balance:
        async with self.client.get(
            self.config.API_ADDRESS_URL.format(addr=urllib.parse.quote(addr, safe="")),
            raise_for_status=True,
        ) as resp:
            raw_balance = await resp.json()

            return Balance.from_raw(addr, raw_balance)

    async def get_transactions(self) -> Sequence[Transaction]:
        async with self.client.get(
            self.config.API_TRANSACTIONS_URL,
            raise_for_status=True,
        ) as resp:
            raw_transactions = await resp.json()

            return tuple(Transaction.from_raw(t) for t in raw_transactions)

    async def post_transfer(
        self,
        from_addr: AddrT,
        to_addr: AddrT,
        amount: Fraction,
    ):
        async with self.client.post(
            self.config.API_TRANSACTIONS_URL,
            json={
                "toAddress": to_addr,
                "fromAddress": from_addr,
                "amount": frac2str(amount),
            },
        ) as resp:
            if resp.status == 422:
                raise InsufficientFundsError
            elif isinstance(resp, HTTPException):
                raise resp


def frac2str(frac: Fraction) -> str:
    return str(Decimal(frac.numerator) / Decimal(frac.denominator))


def iso2str(dt: datetime) -> str:
    return re.sub(r"[-+][0-9:]+\Z", r"Z", dt.isoformat(timespec="milliseconds"))


def str2iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(str(re.sub(r"Z\Z", r"+00:00", dt_str)))
