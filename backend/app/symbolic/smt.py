"""SMT certification of qualitative asset directions.

The sign algebra answers "what follows from all cited mechanisms". The SMT
layer answers the sharper question a reviewer asks: *which minimal set of
mechanisms is sufficient to entail this direction, and is the claim even
consistent?*

Encoding: each mechanism has an activation Boolean. Each edge's sign is the
sign of the active weighted sum. Each event -> channel -> asset path has a
qualitative sign; an asset is definitely positive if some path is positive and
no path is negative. We then minimize the number of active mechanisms subject
to the claim. The resulting set is a machine-checkable proof core.

If Z3 is unavailable the certifier degrades to UNVERIFIED rather than failing
the analysis.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum

from ..schemas import ChannelSpec, MechanismMatch
from .graph import InfluenceGraph
from .signs import Sign

try:  # pragma: no cover - exercised by the installed dependency
    import z3
except ImportError:  # pragma: no cover
    z3 = None


class ProofStatus(str, Enum):
    PROVED = "proved"
    AMBIGUOUS = "ambiguous"
    NOT_ENTAILED = "not_entailed"
    UNVERIFIED = "unverified"


@dataclass
class ProofResult:
    asset: str
    claim: str
    status: ProofStatus
    core: list[str]
    paths: list[str]
    note: str

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "claim": self.claim,
            "status": self.status.value,
            "core": self.core,
            "paths": self.paths,
            "note": self.note,
        }


class SMTCertifier:
    def __init__(
        self,
        matches: list[MechanismMatch],
        channels: dict[str, ChannelSpec],
        assets: list[str],
        timeout_ms: int = 3000,
    ):
        self.matches = matches
        self.channels = channels
        self.assets = assets
        self.timeout_ms = timeout_ms
        self.graph = InfluenceGraph.from_matches(matches, channels, assets)

    def certify(self, asset: str, claim: Sign) -> ProofResult:
        if z3 is None:
            return ProofResult(
                asset=asset,
                claim=claim.value,
                status=ProofStatus.UNVERIFIED,
                core=[],
                paths=[],
                note="z3-solver is not installed; symbolic proof skipped.",
            )
        if claim not in (Sign.POS, Sign.NEG):
            return ProofResult(
                asset=asset,
                claim=claim.value,
                status=ProofStatus.UNVERIFIED,
                core=[],
                paths=[],
                note="Only definite directions can be certified.",
            )
        if not self.matches:
            return ProofResult(
                asset=asset,
                claim=claim.value,
                status=ProofStatus.NOT_ENTAILED,
                core=[],
                paths=[],
                note="No mechanism matched; nothing to prove.",
            )

        paths = self.graph.paths("event", f"asset:{asset}")
        if not paths:
            return ProofResult(
                asset=asset,
                claim=claim.value,
                status=ProofStatus.NOT_ENTAILED,
                core=[],
                paths=[],
                note="No cited path reaches this asset.",
            )

        optimizer = z3.Optimize()
        optimizer.set(timeout=self.timeout_ms)
        activation = {
            match.mechanism.id: z3.Bool(f"act_{match.mechanism.id}") for match in self.matches
        }
        edge_signs = self._edge_signs(activation)
        path_pos, path_neg, path_zero = [], [], []
        for path in paths:
            pos, neg, zero = self._path_signs(path, edge_signs)
            path_pos.append(pos)
            path_neg.append(neg)
            path_zero.append(zero)

        asset_pos = z3.Or(path_pos) if path_pos else z3.BoolVal(False)
        asset_neg = z3.Or(path_neg) if path_neg else z3.BoolVal(False)
        if claim is Sign.POS:
            target = z3.And(asset_pos, z3.Not(asset_neg))
        else:
            target = z3.And(asset_neg, z3.Not(asset_pos))

        optimizer.add(target)
        # Prefer a small, non-empty proof core.
        optimizer.add(z3.Or([act for act in activation.values()]))
        optimizer.minimize(z3.Sum([z3.If(act, 1, 0) for act in activation.values()]))
        result = optimizer.check()
        if result == z3.sat:
            model = optimizer.model()
            core = sorted(
                mechanism_id
                for mechanism_id, act in activation.items()
                if z3.is_true(model.eval(act, model_completion=True))
            )
            supporting = [
                path
                for path in paths
                if self._path_supports(path, edge_signs, claim, core)
            ]
            return ProofResult(
                asset=asset,
                claim=claim.value,
                status=ProofStatus.PROVED,
                core=core,
                paths=[" -> ".join(path) for path in (supporting or paths)],
                note=(
                    f"Minimal mechanism set of size {len(core)} entails the "
                    f"{claim.value} direction."
                ),
            )

        # Not provable. Is it because both directions are possible?
        ambiguity_solver = z3.Solver()
        ambiguity_solver.set(timeout=self.timeout_ms)
        for name, act in activation.items():
            ambiguity_solver.add(act)  # all cited mechanisms active
        ambiguity_solver.add(asset_pos, asset_neg)
        if ambiguity_solver.check() == z3.sat:
            return ProofResult(
                asset=asset,
                claim=claim.value,
                status=ProofStatus.AMBIGUOUS,
                core=[],
                paths=[" -> ".join(path) for path in paths],
                note="Both the positive and negative direction are consistent with the cited paths.",
            )
        return ProofResult(
            asset=asset,
            claim=claim.value,
            status=ProofStatus.NOT_ENTAILED,
            core=[],
            paths=[" -> ".join(path) for path in paths],
            note="The cited paths do not entail this direction.",
        )

    # ------------------------------------------------------------- internals
    def _edge_signs(self, activation: dict[str, "z3.BoolRef"]) -> dict[tuple[str, str], tuple]:
        edge_terms: dict[tuple[str, str], list] = {}
        for match in self.matches:
            mechanism = match.mechanism
            for channel_id, weight in mechanism.channels.items():
                edge_terms.setdefault(("event", f"channel:{channel_id}"), []).append(
                    (activation[mechanism.id], weight)
                )
                spec = self.channels[channel_id]
                for asset in self.assets:
                    loading = spec.loadings.get(asset)
                    if loading is None:
                        continue
                    edge_terms.setdefault((f"channel:{channel_id}", f"asset:{asset}"), []).append(
                        (activation[mechanism.id], loading)
                    )
        edge_signs = {}
        for edge, terms in edge_terms.items():
            total = z3.Sum([z3.If(act, weight, 0.0) for act, weight in terms])
            edge_signs[edge] = (total > 0, total < 0, total == 0)
        return edge_signs

    def _path_signs(self, path: list[str], edge_signs: dict):
        edges = [edge_signs[(source, target)] for source, target in zip(path, path[1:])]
        pos_terms, neg_terms, zero_terms = [], [], []
        for assignment in itertools.product((-1, 0, 1), repeat=len(edges)):
            product = 1
            constraints = []
            for edge, value in zip(edges, assignment):
                if value == 1:
                    constraints.append(edge[0])
                elif value == -1:
                    constraints.append(edge[1])
                else:
                    constraints.append(edge[2])
                product *= value
            conjunction = z3.And(*constraints) if constraints else z3.BoolVal(True)
            if product == 1:
                pos_terms.append(conjunction)
            elif product == -1:
                neg_terms.append(conjunction)
            else:
                zero_terms.append(conjunction)
        return (
            z3.Or(*pos_terms) if pos_terms else z3.BoolVal(False),
            z3.Or(*neg_terms) if neg_terms else z3.BoolVal(False),
            z3.Or(*zero_terms) if zero_terms else z3.BoolVal(False),
        )

    def _path_supports(
        self, path: list[str], edge_signs: dict, claim: Sign, core: list[str]
    ) -> bool:
        # A path supports the claim if every edge used by an active core
        # mechanism has the sign required by the path product.
        required = 1 if claim is Sign.POS else -1
        product = 1
        for source, target in zip(path, path[1:]):
            total_sign = 0
            for match in self.matches:
                if match.mechanism.id not in core:
                    continue
                mechanism = match.mechanism
                if source == "event":
                    weight = mechanism.channels.get(target.split(":", 1)[1])
                else:
                    channel_id = source.split(":", 1)[1]
                    weight = self.channels[channel_id].loadings.get(asset_of(target))
                if weight is None:
                    continue
                total_sign += 1 if weight > 0 else -1 if weight < 0 else 0
            if total_sign == 0:
                return False
            product *= 1 if total_sign > 0 else -1
        return product == required


def asset_of(node: str) -> str:
    return node.split(":", 1)[1] if ":" in node else node
