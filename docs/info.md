## How it works

This project implements a signed 4-bit 2x2 output-stationary systolic array for matrix multiplication.

The accelerator contains four processing elements (PEs) arranged as:

```text
PE00  PE01
PE10  PE11
```

Each PE receives a signed 4-bit A operand from the left and a signed 4-bit B operand from the top. The A values propagate horizontally while the B values propagate vertically. Each PE multiplies its two inputs and accumulates the product locally.

For matrices A and B, the accelerator computes:

```text
C00 = A00B00 + A01B10
C01 = A00B01 + A01B11
C10 = A10B00 + A11B10
C11 = A10B01 + A11B11
```

The operands use signed two's-complement 4-bit values from -8 to +7. Each PE uses a signed 9-bit accumulator.

The controller loads the two 2x2 matrices through the 8-bit input bus. Each byte contains two 4-bit signed values.

After loading, the controller performs four compute cycles using skewed A and B streams so that the required multiplication terms arrive at the correct PEs.

The four 9-bit results are then transmitted in row-major order:

C00, C01, C10, C11

For each result, the lower eight bits are presented on `uo_out[7:0]` and the ninth bit is presented on `uio_out[0]`.

## How to test

The design is verified using Cocotb and Icarus Verilog.

A transaction follows this sequence:

1. Assert START on `uio_in[0]`.
2. Send four input bytes through `ui_in[7:0]`.
3. Allow four compute cycles.
4. Read four 9-bit results in row-major order.
5. Return to IDLE before starting another transaction.

The regression includes signed corner cases, exhaustive single-term tests, and randomized 2x2 matrix multiplication tests.

## External hardware

No external hardware is required for core accelerator operation.

The design uses the standard Tiny Tapeout digital interface. An external controller, FPGA, microcontroller, or testbench can provide the clock, reset, START command, matrix data, and read the resulting matrix through the Tiny Tapeout pins.
