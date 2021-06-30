import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from random import uniform
from typing import DefaultDict, Dict, Mapping, NoReturn, Set

from .api import AddrT, Api, Transaction

LOGGER = logging.getLogger()


def gather_deposits_task(
    api: Api,
    recv_addr: AddrT,
    house_addr: AddrT,
    poll_sec: float = 2.0 * 60,
) -> asyncio.Task:
    async def _watcher() -> NoReturn:
        while True:
            recv_balance = await api.get_balance_for_address(recv_addr)

            if recv_balance.balance > 0:
                await api.post_transfer(recv_addr, house_addr, recv_balance.balance)

            await asyncio.sleep(poll_sec)

    # create_task(..., name=...) requires Python >= 3.8
    return asyncio.create_task(_watcher(), name="gather_deposits_task")


def disburse_task(
    api: Api,
    house_addr: AddrT,
    recv_addr_to_wthd_addrs: Mapping[AddrT, Set[AddrT]],
    min_distinct_receiver_addrs: int = 20,
    min_transaction_age: timedelta = timedelta(hours=1),
    poll_sec: float = 2.0 * 60,
) -> asyncio.Task:
    async def _watcher() -> NoReturn:
        # It's possible we were killed after we received funds to the house address but
        # before they were disbursed among the withdrawal addresses, so we first have to
        # reconstruct our state from what we can observe in the network. Thankfully,
        # this is similar to what we have to do when detecting new deposits, but with
        # some additional housekeeping.
        unpaid_receipts: DefaultDict[AddrT, Fraction] = defaultdict(Fraction)
        reconciled_transactions: Set[Transaction] = set()
        newest_transaction_dt = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        while True:
            # Build a map back from withdrawal addresses to our receive address. This is
            # necessary to account for payouts. This assumes no client is reusing the
            # same withdrawal address with multiple receive addresses. While it's nice
            # to be able to recreate one's internal state entirely from the network,
            # these are not constraints one could rely on in the real world. Some
            # reliably persisted local state would likely be prudent. We do this every
            # iteration of the loop because recv_addr_to_wthd_addrs might have changed
            # since we last ran.
            wthd_addr_to_recv_addr: Dict[AddrT, AddrT] = {}

            for recv_addr, wthd_addrs in recv_addr_to_wthd_addrs.items():
                assert wthd_addrs

                for wthd_addr in wthd_addrs:
                    assert wthd_addr not in wthd_addr_to_recv_addr
                    wthd_addr_to_recv_addr[wthd_addr] = recv_addr

            house_balance = await api.get_balance_for_address(house_addr)

            for transaction in house_balance.transactions:
                if transaction not in reconciled_transactions:
                    if (
                        transaction.from_addr
                        and transaction.from_addr in recv_addr_to_wthd_addrs
                    ):
                        assert transaction.to_addr == house_addr
                        newest_transaction_dt = max(
                            newest_transaction_dt,
                            transaction.timestamp,
                        )
                        unpaid_receipts[transaction.from_addr] += transaction.amount
                    elif transaction.to_addr in wthd_addr_to_recv_addr:
                        assert transaction.from_addr == house_addr
                        recv_addr = wthd_addr_to_recv_addr[transaction.to_addr]
                        unpaid_receipts[recv_addr] -= transaction.amount
                    else:
                        LOGGER.warning(
                            "ignoring transaction found that does not belong to a known receive or withdrawal address: %r",
                            transaction,
                        )

                reconciled_transactions.add(transaction)

            # Clear out anyone who's been paid
            cleaned_unpaid_receipts = {
                recv_addr: balance_owed
                for recv_addr, balance_owed in unpaid_receipts.items()
                if balance_owed != 0
            }
            unpaid_receipts.clear()
            unpaid_receipts.update(cleaned_unpaid_receipts)

            # We should always have enough in our balance to make our payouts. (Note:
            # using sum(..., start=...) requires Python >= 3.8.)
            total_unpaid = sum(unpaid_receipts.values(), start=Fraction(0))
            assert total_unpaid <= house_balance.balance

            if house_balance.balance > total_unpaid:
                LOGGER.warning(
                    'Balance on "%s" shows a surplus of %s (probably a bug, not free money)',
                    house_addr,
                    house_balance.balance - total_unpaid,
                )

            # This is a toy attempt to try to accumulate a "sufficient" number of
            # sources prior to distribution. There are big problems with this approach.
            # One is that the disburser will starve (never disburse) so long as the
            # number of receiving addresses are under the threshold or new transactions
            # keep coming in. Another is that a nefarious actor seeking to defeat the
            # privacy of participants could flood the house address with tiny
            # transactions such that they end up making a bulk of the addresses involved
            # in the payouts. They can trace and subtract their own transactions, which
            # likely leaves a much clearer picture around what's left. Collecting a fee
            # might present a disincentive for this kind of attack. I'm not sure it
            # would eliminate it, though.
            now = api.now()

            if (
                len(unpaid_receipts) >= min_distinct_receiver_addrs
                and now >= newest_transaction_dt + min_transaction_age
            ):
                for recv_addr, balance_owed in unpaid_receipts.items():
                    wthd_addrs = recv_addr_to_wthd_addrs[recv_addr]
                    # This could result in a repeating decimal, so we have to massage
                    # some more
                    split = balance_owed / len(wthd_addrs)

                    # We could introduce some randomization or jitter here in an attempt
                    # to obfuscate things, but I would hope that's beyond the scope of
                    # this already ridiculously cumbersome exercise
                    base_value = Decimal(split.numerator) / Decimal(split.denominator)

                    for i, wthd_addr in enumerate(wthd_addrs):
                        if i < len(wthd_addrs) - 1:
                            jitter_value = base_value * Decimal(uniform(0.9, 1.1))
                            rounded_split = Fraction(
                                jitter_value.quantize(Decimal("0.01"))
                            )
                            await api.post_transfer(
                                house_addr, wthd_addr, rounded_split
                            )
                            balance_owed -= rounded_split
                        else:
                            await api.post_transfer(house_addr, wthd_addr, balance_owed)
                            balance_owed = Fraction(0)

                    # Note that we don't update unpaid_receipts here. We wait until our
                    # next run to observe and reconcile the transactions we just
                    # created.
                    assert balance_owed == 0

            await asyncio.sleep(poll_sec)

    # create_task(..., name=...) requires Python >= 3.8
    return asyncio.create_task(_watcher(), name="disburse_task")
