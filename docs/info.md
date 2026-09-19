## How it works

This project implements a signed 4-bit 3x3 output-stationary systolic array for matrix multiplication.

The accelerator contains nine processing elements (PEs) arranged as:

```text
PE00  PE01  PE02
PE10  PE11  PE12
PE20  PE21  PE22
```

Each PE receives a signed 4-bit A operand from the left and a signed 4-bit B operand from the top. The A values propagate horizontally from left to right, while the B values propagate vertically from top to bottom. Each PE multiplies its two inputs and accumulates the product locally.

For matrices A and B, the accelerator computes:

C[i][j] = A[i][0]B[0][j] + A[i][1]B[1][j] + A[i][2]B[2][j]

The operands use signed two's-complement 4-bit values with a range of -8 to +7. Each PE uses a signed 9-bit accumulator, which is sufficient for the maximum possible sum of three products.

The controller first loads the two 3x3 matrices through the 8-bit input bus. Each matrix row uses two input bytes: the first byte contains two 4-bit elements and the second byte contains the third element in its lower nibble.

After loading, the controller performs seven compute cycles using skewed A and B streams so that corresponding multiplication terms arrive at each PE on the same cycle.

The nine 9-bit results are then transmitted in row-major order:

C00, C01, C02, C10, C11, C12, C20, C21, C22

For each result, the lower eight bits are presented on `uo_out[7:0]` and the ninth bit is presented on `uio_out[0]`.

## How to test

The design is verified using Cocotb and Icarus Verilog.

A transaction follows this sequence:

1. Assert the START command on `uio_in[0]`.
2. Send 12 input bytes through `ui_in[7:0]`.
3. Allow seven compute cycles for the systolic array.
4. Read nine 9-bit results in row-major order.
5. Return to the IDLE state before beginning another transaction.

The verification testbench compares the hardware results against an independent Python 3x3 matrix-multiplication reference model.

The regression suite includes:

* Basic signed matrix multiplication
* Identity matrix tests
* Signed extreme values
* Zero matrices
* Back-to-back matrix operations
* `ena` pause and resume behavior
* START re-arm behavior
* 300 randomized 3x3 matrix tests
* 6,912 exhaustive single-term tests covering every PE position, every multiplication term, and every signed 4-bit operand pair

## External hardware

No external hardware is required for the core accelerator operation.

The design uses the standard Tiny Tapeout digital interface. An external controller, FPGA, microcontroller, or testbench can provide the clock, reset, START command, matrix data, and read the resulting matrix through the Tiny Tapeout pins.
