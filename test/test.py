
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, ReadWrite, RisingEdge, Timer


def encode_s4(value):
    assert -8 <= value <= 7
    return value & 0xF


def pack_pair(first, second):
    return encode_s4(first) | (encode_s4(second) << 4)


def pack_single(value):
    return encode_s4(value)


def matmul_3x3(a, b):
    c = [[0, 0, 0] for _ in range(3)]

    for i in range(3):
        for j in range(3):
            for k in range(3):
                c[i][j] += a[i][k] * b[k][j]

    return c


def flatten_matrix(matrix):
    return [
        matrix[i][j]
        for i in range(3)
        for j in range(3)
    ]


def get_9bit_signed(raw):
    raw &= 0x1FF

    if raw & 0x100:
        return raw - 0x200

    return raw


def read_result(dut):
    raw = int(dut.uo_out.value)
    raw |= (int(dut.uio_out.value) & 0x01) << 8
    return get_9bit_signed(raw)


async def reset_dut(dut):
    await ReadWrite()

    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    await ReadWrite()
    dut.rst_n.value = 1

    await RisingEdge(dut.clk)


async def start_operation(dut):
    await ReadWrite()
    dut.uio_in.value = 0
    await RisingEdge(dut.clk)

    await ReadWrite()
    dut.uio_in.value = 1
    await RisingEdge(dut.clk)

    await ReadWrite()
    dut.uio_in.value = 0


async def load_matrices(dut, a, b):
    payload = [
        pack_pair(a[0][0], a[0][1]),
        pack_single(a[0][2]),

        pack_pair(a[1][0], a[1][1]),
        pack_single(a[1][2]),

        pack_pair(a[2][0], a[2][1]),
        pack_single(a[2][2]),

        pack_pair(b[0][0], b[0][1]),
        pack_single(b[0][2]),

        pack_pair(b[1][0], b[1][1]),
        pack_single(b[1][2]),

        pack_pair(b[2][0], b[2][1]),
        pack_single(b[2][2]),
    ]

    await start_operation(dut)

    for value in payload:
        dut.ui_in.value = value
        await RisingEdge(dut.clk)

    dut.ui_in.value = 0


async def run_compute(dut):
    for _ in range(7):
        await RisingEdge(dut.clk)


async def read_results(dut):
    results = []

    await ReadOnly()

    assert int(dut.uio_oe.value) == 1

    results.append(read_result(dut))

    for _ in range(8):
        await RisingEdge(dut.clk)
        await ReadOnly()
        results.append(read_result(dut))

    await RisingEdge(dut.clk)
    await ReadOnly()

    assert int(dut.uio_oe.value) == 0

    await Timer(1, unit="ps")

    return results


async def run_transaction(dut, a, b):
    await load_matrices(dut, a, b)
    await run_compute(dut)
    return await read_results(dut)


def assert_matrix_result(a, b, observed):
    expected = flatten_matrix(matmul_3x3(a, b))

    assert observed == expected, (
        f"\nA = {a}"
        f"\nB = {b}"
        f"\nExpected = {expected}"
        f"\nObserved = {observed}"
    )


@cocotb.test()
async def test_basic_matrix(dut):
    dut._log.info("Starting basic 3x3 signed matrix test")

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    a = [
        [1, 2, 3],
        [4, 5, 6],
        [7, -1, 2],
    ]

    b = [
        [2, 0, 1],
        [1, 3, -2],
        [4, 2, 1],
    ]

    observed = await run_transaction(dut, a, b)

    assert_matrix_result(a, b, observed)

    dut._log.info("Basic 3x3 matrix test PASS")


@cocotb.test()
async def test_identity_matrices(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    identity = [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
    ]

    b = [
        [-8, 7, 2],
        [3, -1, 6],
        [4, 5, -7],
    ]

    observed = await run_transaction(dut, identity, b)
    assert_matrix_result(identity, b, observed)

    observed = await run_transaction(dut, b, identity)
    assert_matrix_result(b, identity, observed)


@cocotb.test()
async def test_signed_extremes(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    a = [
        [-8, -8, 7],
        [7, 7, -8],
        [-1, 1, -1],
    ]

    b = [
        [-8, 7, -8],
        [7, -8, 7],
        [-8, 7, -8],
    ]

    observed = await run_transaction(dut, a, b)

    assert_matrix_result(a, b, observed)


@cocotb.test()
async def test_zeros(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    a = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]

    b = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]

    observed = await run_transaction(dut, a, b)

    assert observed == [0] * 9


@cocotb.test()
async def test_back_to_back(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    a1 = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 0, -1],
    ]

    b1 = [
        [2, 1, 0],
        [0, 3, 1],
        [4, 0, 2],
    ]

    a2 = [
        [-2, 3, 1],
        [0, -4, 5],
        [6, 2, -3],
    ]

    b2 = [
        [1, -1, 2],
        [3, 0, -2],
        [4, 5, 1],
    ]

    observed1 = await run_transaction(dut, a1, b1)
    assert_matrix_result(a1, b1, observed1)

    observed2 = await run_transaction(dut, a2, b2)
    assert_matrix_result(a2, b2, observed2)


@cocotb.test()
async def test_ena_pause(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    a = [
        [1, 2, 3],
        [4, 5, 6],
        [7, -1, 2],
    ]

    b = [
        [2, 0, 1],
        [1, 3, -2],
        [4, 2, 1],
    ]

    await load_matrices(dut, a, b)

    for _ in range(3):
        await RisingEdge(dut.clk)

    await ReadWrite()
    dut.ena.value = 0

    paused_results = []

    for _ in range(2):
        await RisingEdge(dut.clk)
        await ReadOnly()

        paused_results.append([
            read_result(dut),
            int(dut.uio_oe.value),
        ])

    await Timer(1, unit="ps")
    dut.ena.value = 1

    for _ in range(4):
        await RisingEdge(dut.clk)

    observed = await read_results(dut)

    assert_matrix_result(a, b, observed)

    assert all(uoe == 0 for _, uoe in paused_results)


@cocotb.test()
async def test_start_must_be_rearmed(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    a = [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
    ]

    b = [
        [3, 2, 1],
        [4, 5, 6],
        [7, 7, -1],
    ]

    await load_matrices(dut, a, b)
    await run_compute(dut)

    await ReadOnly()
    assert int(dut.uio_oe.value) == 1

    for _ in range(9):
        await RisingEdge(dut.clk)

    await ReadOnly()
    assert int(dut.uio_oe.value) == 0

    await Timer(1, unit="ps")
    dut.uio_in.value = 1

    await RisingEdge(dut.clk)
    await ReadOnly()

    assert int(dut.uio_oe.value) == 0

    await Timer(1, unit="ps")
    dut.uio_in.value = 0

    await RisingEdge(dut.clk)
    await ReadOnly()

    await Timer(1, unit="ps")
    dut.uio_in.value = 1

    await RisingEdge(dut.clk)
    await ReadOnly()

    assert int(dut.uio_oe.value) == 0


@cocotb.test()
async def test_random_matrices(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    rng = random.Random(20260919)

    for test_number in range(300):
        a = [
            [rng.randint(-8, 7) for _ in range(3)]
            for _ in range(3)
        ]

        b = [
            [rng.randint(-8, 7) for _ in range(3)]
            for _ in range(3)
        ]

        observed = await run_transaction(dut, a, b)

        expected = flatten_matrix(matmul_3x3(a, b))

        assert observed == expected, (
            f"Random test {test_number} failed"
            f"\nA = {a}"
            f"\nB = {b}"
            f"\nExpected = {expected}"
            f"\nObserved = {observed}"
        )

@cocotb.test()
async def test_exhaustive_single_terms(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    case_count = 0

    for i in range(3):
        for j in range(3):
            for k in range(3):
                for a_value in range(-8, 8):
                    for b_value in range(-8, 8):

                        a = [
                            [0, 0, 0],
                            [0, 0, 0],
                            [0, 0, 0],
                        ]

                        b = [
                            [0, 0, 0],
                            [0, 0, 0],
                            [0, 0, 0],
                        ]

                        a[i][k] = a_value
                        b[k][j] = b_value

                        observed = await run_transaction(dut, a, b)

                        expected = [0] * 9
                        expected[(i * 3) + j] = a_value * b_value

                        assert observed == expected, (
                            f"Exhaustive single-term test failed"
                            f"\nCase = {case_count}"
                            f"\ni={i}, j={j}, k={k}"
                            f"\nA term = {a_value}"
                            f"\nB term = {b_value}"
                            f"\nA = {a}"
                            f"\nB = {b}"
                            f"\nExpected = {expected}"
                            f"\nObserved = {observed}"
                        )

                        case_count += 1

                dut._log.info(
                    f"Completed i={i}, j={j}, k={k}: "
                    f"{case_count}/6912 cases"
                )

    assert case_count == 6912

    dut._log.info("Exhaustive single-term test PASS")
