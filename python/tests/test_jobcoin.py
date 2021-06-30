import asyncio
from fractions import Fraction
from typing import Mapping, Set

import pytest

from ..jobcoin.api import AddrT
from ..jobcoin.jobcoin import disburse_task, gather_deposits_task
from .utils import loop  # noqa: F401 # pylint: disable=unused-import
from .utils import test_api


@pytest.fixture
def recv_addr_to_wthd_addrs() -> Mapping[AddrT, Set[AddrT]]:
    return {
        "recv-3": {
            "recv-3-wthd-1",
            "recv-3-wthd-2",
            "recv-3-wthd-3",
        },
        "recv-4": {
            "recv-4-wthd-1",
            "recv-4-wthd-2",
            "recv-4-wthd-3",
            "recv-4-wthd-4",
        },
        "recv-7": {
            "recv-7-wthd-1",
            "recv-7-wthd-2",
            "recv-7-wthd-3",
            "recv-7-wthd-4",
            "recv-7-wthd-5",
            "recv-7-wthd-6",
            "recv-7-wthd-7",
        },
    }


async def test_simple_gather_deposits(
    aiohttp_client,
) -> None:
    api = await test_api(aiohttp_client)

    src_addr = "src-test"
    resp = await api.client.post(
        "/transactions", json={"toAddress": src_addr, "amount": "20"}
    )
    assert resp.status == 200

    recv_addr = "recv-test"
    house_addr = "house-test"
    task = gather_deposits_task(api, recv_addr, house_addr)

    for i in range(1, 5):
        src_balance = await api.get_balance_for_address(src_addr)
        assert src_balance.balance > 0
        transfer_amount = min(Fraction(5), src_balance.balance)
        await api.post_transfer(src_addr, recv_addr, transfer_amount)
        await asyncio.sleep(3 * 60.0)
        recv_balance = await api.get_balance_for_address(recv_addr)
        assert recv_balance.balance == 0
        assert len(recv_balance.transactions) == 2 * i
        house_balance = await api.get_balance_for_address(house_addr)
        assert house_balance.balance == 20 - src_balance.balance + transfer_amount
        assert len(house_balance.transactions) == i
        transaction = house_balance.transactions[-1]
        assert transaction.from_addr == recv_addr
        assert transaction.amount == transfer_amount

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_complete_disbursement(
    aiohttp_client,
    recv_addr_to_wthd_addrs: Mapping[
        AddrT, Set[AddrT]
    ],  # noqa: F811 # pylint: disable=redefined-outer-name
) -> None:
    api = await test_api(aiohttp_client)

    src_addr = "src-test"
    resp = await api.client.post(
        "/transactions", json={"toAddress": src_addr, "amount": "30"}
    )
    assert resp.status == 200
    src_balance = await api.get_balance_for_address(src_addr)
    assert src_balance.balance == 30

    house_addr = "house-test"
    tasks = []

    for recv_addr in recv_addr_to_wthd_addrs:
        task = gather_deposits_task(api, recv_addr, house_addr)
        tasks.append(task)

    task = disburse_task(
        api,
        house_addr,
        recv_addr_to_wthd_addrs,
        min_distinct_receiver_addrs=len(recv_addr_to_wthd_addrs),
    )
    tasks.append(task)

    for recv_addr in recv_addr_to_wthd_addrs:
        await api.post_transfer(src_addr, recv_addr, Fraction(10))

    await asyncio.sleep(3 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 30

    await asyncio.sleep(61 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 0

    for wthd_addrs in recv_addr_to_wthd_addrs.values():
        total_wthd_balance = Fraction(0)

        for wthd_addr in wthd_addrs:
            wthd_balance = await api.get_balance_for_address(wthd_addr)
            total_wthd_balance += wthd_balance.balance

        assert total_wthd_balance == 10

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)


async def test_disbursement_meets_minimum_criteria(
    aiohttp_client,
    recv_addr_to_wthd_addrs: Mapping[
        AddrT, Set[AddrT]
    ],  # noqa: F811 # pylint: disable=redefined-outer-name
) -> None:
    api = await test_api(aiohttp_client)

    src_addr = "src-test"
    resp = await api.client.post(
        "/transactions", json={"toAddress": src_addr, "amount": "30"}
    )
    assert resp.status == 200
    src_balance = await api.get_balance_for_address(src_addr)
    assert src_balance.balance == 30

    house_addr = "house-test"
    tasks = []

    for recv_addr in recv_addr_to_wthd_addrs:
        task = gather_deposits_task(api, recv_addr, house_addr)
        tasks.append(task)

    task = disburse_task(
        api,
        house_addr,
        recv_addr_to_wthd_addrs,
        min_distinct_receiver_addrs=len(recv_addr_to_wthd_addrs),
    )
    tasks.append(task)

    recv_addrs = list(recv_addr_to_wthd_addrs)

    # Transfer from all but one
    for recv_addr in recv_addrs[:-1]:
        await api.post_transfer(src_addr, recv_addr, Fraction(10))

    await asyncio.sleep(3 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 10 * (len(recv_addrs) - 1)

    # Wait until the last transaction meets the minimum age (still not good enough,
    # since we need another receiver)
    await asyncio.sleep(61 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 10 * (len(recv_addrs) - 1)

    # Final transaction
    await api.post_transfer(src_addr, recv_addrs[-1], Fraction(10))
    await asyncio.sleep(3 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 10 * len(recv_addrs)

    # Wait until the last transaction meets the minimum age
    await asyncio.sleep(61 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 0

    for wthd_addrs in recv_addr_to_wthd_addrs.values():
        total_wthd_balance = Fraction(0)

        for wthd_addr in wthd_addrs:
            wthd_balance = await api.get_balance_for_address(wthd_addr)
            total_wthd_balance += wthd_balance.balance

        assert total_wthd_balance == 10

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)


async def test_disbursus_interruptus(
    aiohttp_client,
    recv_addr_to_wthd_addrs: Mapping[
        AddrT, Set[AddrT]
    ],  # noqa: F811 # pylint: disable=redefined-outer-name
) -> None:
    api = await test_api(aiohttp_client)

    src_addr = "src-test"
    resp = await api.client.post(
        "/transactions", json={"toAddress": src_addr, "amount": "60"}
    )
    assert resp.status == 200
    src_balance = await api.get_balance_for_address(src_addr)
    assert src_balance.balance == 60

    house_addr = "house-test"
    gather_deposits_tasks = []

    for recv_addr in recv_addr_to_wthd_addrs:
        task = gather_deposits_task(api, recv_addr, house_addr)
        gather_deposits_tasks.append(task)

    first_disburse_task = disburse_task(
        api,
        house_addr,
        recv_addr_to_wthd_addrs,
        min_distinct_receiver_addrs=len(recv_addr_to_wthd_addrs),
    )

    for recv_addr in recv_addr_to_wthd_addrs:
        await api.post_transfer(src_addr, recv_addr, Fraction(10))

    await asyncio.sleep(63 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 0

    # Kill the first disburse task
    first_disburse_task.cancel()
    await asyncio.gather(first_disburse_task, return_exceptions=True)

    # Send more to the receive addresses (no disburse task is running at this point)
    for recv_addr in recv_addr_to_wthd_addrs:
        await api.post_transfer(src_addr, recv_addr, Fraction(10))

    await asyncio.sleep(3 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 30

    # Fire up a new disburse task and see if it does the right thing
    second_disburse_task = disburse_task(
        api,
        house_addr,
        recv_addr_to_wthd_addrs,
        min_distinct_receiver_addrs=len(recv_addr_to_wthd_addrs),
    )

    await asyncio.sleep(61 * 60.0)
    house_balance = await api.get_balance_for_address(house_addr)
    assert house_balance.balance == 0

    second_disburse_task.cancel()
    await asyncio.gather(second_disburse_task, return_exceptions=True)

    for wthd_addrs in recv_addr_to_wthd_addrs.values():
        total_wthd_balance = Fraction(0)

        for wthd_addr in wthd_addrs:
            wthd_balance = await api.get_balance_for_address(wthd_addr)
            assert len(wthd_balance.transactions) == 2
            total_wthd_balance += wthd_balance.balance

        assert total_wthd_balance == 20

    for task in gather_deposits_tasks:
        task.cancel()

    await asyncio.gather(*gather_deposits_tasks, return_exceptions=True)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

_ = """
#!/usr/bin/env python
import pytest
import re
from click.testing import CliRunner

from ..jobcoin import config
from .. import cli


@pytest.fixture
def response():
    import requests
    return requests.get('https://jobcoin.gemini.com/')


def test_content(response):
    assert 'Hello!' in response.content


def test_cli_basic():
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert 'Welcome to the Jobcoin mixer' in result.output


def test_cli_creates_address():
    runner = CliRunner()
    address_create_output = runner.invoke(cli.main, input='1234,4321').output
    output_re = re.compile(
        r'You may now send Jobcoins to address [0-9a-zA-Z]{32}. '
        'They will be mixed and sent to your destination addresses.'
    )
    assert output_re.search(address_create_output) is not None
"""
