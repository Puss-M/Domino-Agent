"""Signed influence graph over the cited mechanism library.

Nodes: event -> transmission channel -> asset.
Edges carry one or more mechanism contributions with a sign. Parallel
contributions on the same edge combine by qualitative addition; a serial path
composes by multiplication. The output is a *qualitative* prediction per asset,
with explicit ambiguity when paths disagree.

This is deliberately separate from the numeric transmission model. The numeric
model answers "how large"; the sign algebra answers "is the direction provable,
and if not, which mechanisms disagree".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from ..schemas import ChannelSpec, MechanismMatch
from .signs import Sign, combine, direction_word, from_number, mul


@dataclass(frozen=True)
class Contribution:
    mechanism_id: str
    sign: Sign
    weight: float
    citations: tuple[str, ...] = ()


@dataclass
class InfluenceEdge:
    source: str
    target: str
    contributions: list[Contribution] = field(default_factory=list)

    @property
    def sign(self) -> Sign:
        return combine(contribution.sign for contribution in self.contributions)

    @property
    def weight(self) -> float:
        return round(sum(abs(c.weight) for c in self.contributions), 4)

    @property
    def mechanisms(self) -> list[str]:
        return sorted({c.mechanism_id for c in self.contributions})


@dataclass
class PathResult:
    nodes: list[str]
    sign: Sign
    mechanisms: list[str]

    @property
    def readable(self) -> str:
        return " -> ".join(self.nodes)


@dataclass
class Conflict:
    positive_path: str
    negative_path: str
    positive_mechanisms: list[str]
    negative_mechanisms: list[str]


@dataclass
class QualitativeView:
    asset: str
    sign: Sign
    paths: list[PathResult]
    conflicts: list[Conflict]
    mechanisms: list[str]
    explanation: str

    @property
    def definite(self) -> bool:
        return self.sign in (Sign.POS, Sign.NEG)

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "sign": self.sign.value,
            "direction": direction_word(self.sign),
            "definite": self.definite,
            "paths": [
                {"path": p.readable, "sign": p.sign.value, "mechanisms": p.mechanisms}
                for p in self.paths
            ],
            "conflicts": [
                {
                    "positive_path": c.positive_path,
                    "negative_path": c.negative_path,
                    "positive_mechanisms": c.positive_mechanisms,
                    "negative_mechanisms": c.negative_mechanisms,
                }
                for c in self.conflicts
            ],
            "mechanisms": self.mechanisms,
            "explanation": self.explanation,
        }


class InfluenceGraph:
    def __init__(self) -> None:
        self.edges: dict[tuple[str, str], InfluenceEdge] = {}
        self._nodes: set[str] = set()

    # ----------------------------------------------------------------- build
    @classmethod
    def from_matches(
        cls,
        matches: list[MechanismMatch],
        channels: dict[str, ChannelSpec],
        assets: list[str],
    ) -> "InfluenceGraph":
        graph = cls()
        event_node = "event"
        graph._nodes.add(event_node)
        for match in matches:
            mechanism = match.mechanism
            for channel_id, weight in mechanism.channels.items():
                channel_spec = channels[channel_id]
                channel_node = f"channel:{channel_id}"
                graph._add_edge(
                    event_node,
                    channel_node,
                    Contribution(
                        mechanism_id=mechanism.id,
                        sign=from_number(weight),
                        weight=weight,
                        citations=tuple(mechanism.citations),
                    ),
                )
                for asset in assets:
                    loading = channel_spec.loadings.get(asset)
                    if loading is None:
                        continue
                    graph._add_edge(
                        channel_node,
                        f"asset:{asset}",
                        Contribution(
                            mechanism_id=mechanism.id,
                            sign=from_number(loading),
                            weight=loading,
                            citations=tuple(channel_spec.citations),
                        ),
                    )
        return graph

    def _add_edge(self, source: str, target: str, contribution: Contribution) -> None:
        edge = self.edges.setdefault((source, target), InfluenceEdge(source, target))
        edge.contributions.append(contribution)
        self._nodes.update((source, target))

    # ------------------------------------------------------------------ graph
    @property
    def nodes(self) -> list[str]:
        return sorted(self._nodes)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def adjacency(self) -> dict[str, list[str]]:
        adjacency: dict[str, list[str]] = {node: [] for node in self._nodes}
        for source, target in self.edges:
            adjacency[source].append(target)
        return adjacency

    def is_acyclic(self) -> tuple[bool, list[list[str]]]:
        adjacency = self.adjacency()
        state = {node: 0 for node in self._nodes}
        cycles: list[list[str]] = []

        def visit(node: str, stack: list[str]) -> None:
            state[node] = 1
            stack.append(node)
            for nxt in adjacency.get(node, []):
                if state[nxt] == 1:
                    cycles.append(stack[stack.index(nxt):] + [nxt])
                elif state[nxt] == 0:
                    visit(nxt, stack)
            stack.pop()
            state[node] = 2

        for node in self._nodes:
            if state[node] == 0:
                visit(node, [])
        return (not cycles, cycles)

    def paths(self, source: str, target: str, max_depth: int = 4) -> list[list[str]]:
        adjacency = self.adjacency()
        results: list[list[str]] = []
        stack: list[tuple[str, list[str]]] = [(source, [source])]
        while stack:
            node, path = stack.pop()
            if node == target:
                results.append(path)
                continue
            if len(path) >= max_depth:
                continue
            for nxt in adjacency.get(node, []):
                if nxt not in path:
                    stack.append((nxt, path + [nxt]))
        return results

    def _path_sign(self, path: list[str]) -> tuple[Sign, list[str]]:
        sign = Sign.POS
        mechanisms: set[str] = set()
        for source, target in zip(path, path[1:]):
            edge = self.edges[(source, target)]
            sign = mul(sign, edge.sign)
            mechanisms.update(edge.mechanisms)
        return sign, sorted(mechanisms)

    # -------------------------------------------------------------- reasoning
    def qualitative_views(self, assets: list[str]) -> dict[str, QualitativeView]:
        views: dict[str, QualitativeView] = {}
        for asset in assets:
            target = f"asset:{asset}"
            raw_paths = self.paths("event", target)
            path_results = []
            for path in raw_paths:
                sign, mechanisms = self._path_sign(path)
                path_results.append(PathResult(nodes=path, sign=sign, mechanisms=mechanisms))
            net = combine(p.sign for p in path_results)
            positives = [p for p in path_results if p.sign is Sign.POS]
            negatives = [p for p in path_results if p.sign is Sign.NEG]
            conflicts = [
                Conflict(
                    positive_path=p.readable,
                    negative_path=n.readable,
                    positive_mechanisms=p.mechanisms,
                    negative_mechanisms=n.mechanisms,
                )
                for p, n in combinations(positives + negatives, 2)
                if p.sign is not n.sign
            ]
            mechanisms = sorted({m for p in path_results for m in p.mechanisms})
            if not path_results:
                explanation = "No cited path reaches this asset."
            elif net.is_definite:
                explanation = (
                    f"All {len(path_results)} cited paths agree: the asset "
                    f"{direction_word(net)} on this event."
                )
            elif net is Sign.ZERO:
                explanation = "All cited paths have zero net effect."
            else:
                explanation = (
                    f"{len(positives)} positive and {len(negatives)} negative cited paths; "
                    "the qualitative direction is ambiguous until a regime condition or "
                    "data resolves the conflict."
                )
            views[asset] = QualitativeView(
                asset=asset,
                sign=net,
                paths=path_results,
                conflicts=conflicts,
                mechanisms=mechanisms,
                explanation=explanation,
            )
        return views

    def to_dict(self) -> dict:
        return {
            "nodes": self.node_count,
            "edges": self.edge_count,
            "acyclic": self.is_acyclic()[0],
            "edge_list": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "sign": edge.sign.value,
                    "weight": edge.weight,
                    "mechanisms": edge.mechanisms,
                }
                for edge in sorted(self.edges.values(), key=lambda e: (e.source, e.target))
            ],
        }
