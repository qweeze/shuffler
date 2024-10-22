from __future__ import annotations
from dataclasses import dataclass, field
from typing import Generic

from .protocol import Strategy, T


@dataclass
class Node(Generic[T]):
    value: T | None
    children: list[Node[T]] = field(default_factory=list)
    parent: Node[T] | None = None
    visited: bool = False
    explored: bool = False

    def add_child(self, child: Node[T]) -> None:
        child.parent = self
        self.children.append(child)

    def __eq__(self, other: object) -> bool:
        match other:
            case Node():
                return self.value == other.value
            case _:
                return False

    def __hash__(self) -> int:
        return hash(self.value)


class ExhaustiveStrategy(Strategy[T]):
    def __init__(self) -> None:
        self._root: Node[T] = Node(None)
        self._curr_node = self._root
        self._curr_path: list[Node[T]] = []

    def choose_next(self, options: set[T]) -> T:
        assert options
        selected = None

        if self._curr_node.children:
            assert len(options) == len(self._curr_node.children)
        else:
            for option in sorted(options):
                self._curr_node.add_child(Node(option))

        for node in self._curr_node.children:
            if not node.visited:
                selected = node
                break

        if selected is None:
            for node in self._curr_node.children:
                if not node.explored:
                    selected = node
                    break

        assert selected is not None

        self._curr_path.append(selected)
        self._curr_node = selected
        selected.visited = True

        assert selected.value is not None
        assert selected.value in options
        return selected.value

    def is_completed(self) -> bool:
        return bool(self._root.children) and all(
            child.explored for child in self._root.children
        )

    def finish_sequence(self) -> list[T]:
        node = self._curr_node
        while True:
            if all(child.explored for child in node.children):
                node.explored = True

            if node.parent is None:
                break

            node = node.parent

        path, self._curr_path = self._curr_path, []
        self._curr_node = self._root
        return [node.value for node in path if node.value is not None]

    def reset(self) -> None:
        self._curr_node = self._root = Node(None)
        self._curr_path = []
