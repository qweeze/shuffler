import math
from typing import TypeVar


def n_interleavings(*n_ops: int) -> int:
    assert n_ops
    assert all(n_op > 0 for n_op in n_ops)
    return math.factorial(sum(n_ops)) // math.prod(map(math.factorial, n_ops))


T = TypeVar("T")


def all_interleavings(*ops: list[T]) -> list[list[T]]:
    result = []

    def generate(ops: tuple[list[T], ...], current: list[T]) -> None:
        n_empty = 0
        for ix in range(len(ops)):
            if ops[ix]:
                new_current = [*current, ops[ix][0]]
                new_ops = ops[:ix] + (ops[ix][1:],) + ops[ix + 1 :]
                generate(new_ops, new_current)
            else:
                n_empty += 1

        if n_empty == len(ops):
            result.append(current)

    generate(ops, [])
    assert len(result) == n_interleavings(*map(len, ops))
    return result
