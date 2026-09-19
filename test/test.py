import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, ReadWrite, Timer


def encode_s4(value):
    assert -8 <= value <= 7, f"Value {value} is outside signed 4-bit range"
    return value & 0xF


def pack_pair(high_value, low_value):
    return (encode_s4(high_value) << 4) | encode_s4(low_value)


def matmul_2x2(a, b):
    return [
        [
            a[0][0] * b[0][0] + a[0][1] * b[1][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1],
        ],
        [
            a[1][0] * b[0][0] + a[1][1] * b[1][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1],
        ],
    ]


def get_9bit_signed(dut):
    lower_8 = int(dut.uo_out.value)
    upper_bit = int(dut.uio_out.value) & 1

    value = (upper_bit << 8) | lower_8

    if value & 0x100:
        value -= 512

    return value


async def reset_dut(dut):
    await ReadWrite()

    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    dut.rst_n.value = 1

    await RisingEdge(dut.clk)
    await ReadWrite()


async def load_matrices(dut, a, b):
    await ReadWrite()

    assert int(dut.uio_oe.value) == 0, (
        "uio pins must be inputs during loading"
    )

    dut.uio_in.value = 1
    await RisingEdge(dut.clk)

    await ReadWrite()

    dut.uio_in.value = 0

    dut.ui_in.value = pack_pair(a[0][1], a[0][0])
    await RisingEdge(dut.clk)

    await ReadWrite()

    dut.ui_in.value = pack_pair(a[1][1], a[1][0])
    await RisingEdge(dut.clk)

    await ReadWrite()

    dut.ui_in.value = pack_pair(b[0][1], b[0][0])
    await RisingEdge(dut.clk)

    await ReadWrite()

    dut.ui_in.value = pack_pair(b[1][1], b[1][0])
    await RisingEdge(dut.clk)

    await ReadWrite()

    dut.ui_in.value = 0
    dut.uio_in.value = 0


async def compute(dut):
    for _ in range(4):
        await RisingEdge(dut.clk)
        await Timer(5, unit="ns")


async def read_results(dut):
    results = []

    for _ in range(4):
        await ReadOnly()

        assert (int(dut.uio_oe.value) & 1) == 1, (
            "uio[0] must be configured as an output during SEND"
        )

        results.append(get_9bit_signed(dut))

        await RisingEdge(dut.clk)
        await Timer(5, unit="ns")

    return [
        [results[0], results[1]],
        [results[2], results[3]],
    ]


async def run_matrix_test(dut, a, b):
    expected = matmul_2x2(a, b)

    await load_matrices(dut, a, b)
    await compute(dut)
    actual = await read_results(dut)

    assert actual == expected, (
        f"\nA = {a}"
        f"\nB = {b}"
        f"\nExpected = {expected}"
        f"\nActual   = {actual}"
    )


@cocotb.test()
async def test_systolic_array_general(dut):
    cocotb.start_soon(
        Clock(dut.clk, 100, unit="ns").start()
    )

    await reset_dut(dut)

    test_cases = [
        (
            [[0, 0], [0, 0]],
            [[0, 0], [0, 0]],
        ),
        (
            [[1, 2], [3, 4]],
            [[5, 6], [7, 7]],
        ),
        (
            [[7, 7], [7, 7]],
            [[7, 7], [7, 7]],
        ),
        (
            [[-8, -8], [-8, -8]],
            [[-8, -8], [-8, -8]],
        ),
        (
            [[-8, 7], [7, -8]],
            [[7, -8], [-8, 7]],
        ),
        (
            [[-1, 0], [0, -1]],
            [[-8, 0], [0, 7]],
        ),
    ]

    for a, b in test_cases:
        await run_matrix_test(dut, a, b)

    values = list(range(-8, 8))

    product_positions = [
        ("C00 term 0", (0, 0), (0, 0)),
        ("C00 term 1", (0, 1), (1, 0)),
        ("C01 term 0", (0, 0), (0, 1)),
        ("C01 term 1", (0, 1), (1, 1)),
        ("C10 term 0", (1, 0), (0, 0)),
        ("C10 term 1", (1, 1), (1, 0)),
        ("C11 term 0", (1, 0), (0, 1)),
        ("C11 term 1", (1, 1), (1, 1)),
    ]

    for name, a_pos, b_pos in product_positions:
        for a_value in values:
            for b_value in values:
                a = [
                    [0, 0],
                    [0, 0],
                ]

                b = [
                    [0, 0],
                    [0, 0],
                ]

                a[a_pos[0]][a_pos[1]] = a_value
                b[b_pos[0]][b_pos[1]] = b_value

                try:
                    await run_matrix_test(dut, a, b)
                except AssertionError as error:
                    raise AssertionError(
                        f"{name} failed for A={a_value}, B={b_value}\n{error}"
                    ) from error

    random.seed(20260919)

    for _ in range(200):
        a = [
            [
                random.randint(-8, 7),
                random.randint(-8, 7),
            ],
            [
                random.randint(-8, 7),
                random.randint(-8, 7),
            ],
        ]

        b = [
            [
                random.randint(-8, 7),
                random.randint(-8, 7),
            ],
            [
                random.randint(-8, 7),
                random.randint(-8, 7),
            ],
        ]

        await run_matrix_test(dut, a, b)

    dut._log.info(
        "PUMASA! General signed 4-bit 2x2 systolic-array verification completed."
    )