"""Template-first research memo.

The memo is generated from the structured graph, not from a free-form prompt.
That keeps every number traceable to the transmission model. An optional LLM
narrator can rewrite the prose, but it receives the finished memo and is not
allowed to add mechanisms, tickers or numbers.
"""

from __future__ import annotations

from ..schemas import MacroEvent, MechanismMatch, Memo
from .transmission import TransmissionResult

_CHANNEL_FALSIFIERS = {
    "real_yields": "If the 2y/10y Treasury yield does not move in the predicted direction within two sessions, the real-rate channel is not being priced.",
    "nominal_yields": "If Treasury yields fail to follow the policy signal, the duration channel is absent.",
    "discount_rates": "If long-duration equities do not underperform when discount rates rise, the duration channel is not priced.",
    "usd": "If DXY moves against the prediction while rate differentials move as expected, global liquidity is dominating the dollar channel.",
    "risk_premium": "If VIX falls and credit spreads tighten, the risk-premium channel is absent.",
    "credit_spreads": "If HY OAS does not widen, the credit channel is not transmitting.",
    "oil_price": "If Brent does not follow the supply signal, the market is discounting demand rather than supply.",
    "inflation_expectations": "If breakevens do not move, the inflation-expectations channel is not being priced.",
    "growth_expectations": "If PMIs or earnings revisions do not follow, the growth channel is unconfirmed.",
    "policy_support": "If credit spreads do not compress, policy support is not reaching risk assets.",
    "china_demand": "If China credit impulse or property sales do not stabilise, the stimulus is not transmitting.",
    "funding_liquidity": "If cross-currency basis and JPY funding stress do not widen, the funding channel is absent.",
    "safe_haven": "If gold and Treasuries fail to rally together, the flight-to-quality leg is not active.",
    "energy_costs": "If input-cost proxies (airlines, utilities) do not underperform, the cost channel is weak.",
}

_MONITORING = [
    "2y and 10y Treasury yields; 2s10s slope",
    "DXY and USD/JPY; cross-currency basis",
    "VIX, MOVE and HY OAS",
    "Brent crude and front-month futures curve",
    "Policy-rate pricing from SOFR/OIS futures",
    "China credit impulse and property sales (for China channels)",
]


class MemoBuilder:
    def __init__(self, knowledge=None):
        self.knowledge = knowledge

    def build(
        self,
        event: MacroEvent,
        matches: list[MechanismMatch],
        transmission: TransmissionResult,
    ) -> Memo:
        active_channels = sorted(
            transmission.channels.values(), key=lambda activation: -abs(activation.score)
        )
        channel_names = [activation.name for activation in active_channels[:4]]
        top_assets = [prediction for prediction in transmission.predictions if not prediction.abstain][:5]

        direction_word = {
            "tightening": "hawkish",
            "hawkish_hold": "hawkish hold",
            "easing": "dovish",
            "dovish_hold": "dovish hold",
            "upside": "upside",
            "downside": "downside",
            "escalation": "escalation",
            "deescalation": "de-escalation",
            "supply_cut": "supply cut",
            "supply_increase": "supply increase",
            "risk_off": "risk-off",
            "risk_on": "risk-on",
            "stress": "stress",
            "stimulus": "stimulus",
            "neutral": "neutral",
        }.get(event.direction.value, event.direction.value)

        if not matches:
            summary = (
                f"The extractor classified this item as {event.event_type.value} / {direction_word}, "
                "but no cited transmission mechanism met its conditions. The engine abstains rather "
                "than filling the gap with an ungrounded narrative."
            )
        else:
            channel_text = ", ".join(channel_names) if channel_names else "no channels above threshold"
            asset_text = ", ".join(
                f"{prediction.asset} ({prediction.direction}, {prediction.expected_car_bps:+.0f}bp prior)"
                for prediction in top_assets
            )
            summary = (
                f"{event.headline.strip()} is classified as a {direction_word} "
                f"{event.event_type.value.replace('_', ' ')} event. "
                f"The cited library activates {channel_text}. "
                f"The largest transmission priors are {asset_text}. "
                "These are conditional 5-day priors from a small mechanism library, not a forecast "
                "of the event outcome."
            )

        transmission_lines = []
        for activation in active_channels[:5]:
            spec = self.knowledge.channels[activation.channel] if self.knowledge else None
            description = spec.description if spec else ""
            transmission_lines.append(
                f"{activation.name}: score {activation.score:+.2f}. {description}"
            )

        asset_lines = []
        for prediction in top_assets:
            asset_lines.append(
                f"{prediction.asset} ({prediction.label}): {prediction.direction}, "
                f"P(up)={prediction.p_up:.2f}, prior {prediction.expected_car_bps:+.0f}bp over "
                f"{prediction.horizon_days}d, evidence {prediction.evidence_grade.value}"
                + (" [conflicting channels]" if prediction.conflicting else "")
            )

        falsifiers = []
        for activation in active_channels[:4]:
            if activation.channel in _CHANNEL_FALSIFIERS:
                falsifiers.append(_CHANNEL_FALSIFIERS[activation.channel])
        if not falsifiers:
            falsifiers.append(
                "If the first observable proxy for the hypothesised channel does not move within two sessions, treat the map as unconfirmed."
            )

        citations: list[str] = []
        for match in matches:
            for citation in match.mechanism.citations:
                if citation not in citations:
                    citations.append(citation)

        return Memo(
            title=f"Transmission note: {event.headline[:80]}",
            summary=summary,
            transmission=transmission_lines,
            asset_views=asset_lines,
            falsifiers=falsifiers,
            monitoring=_MONITORING.copy(),
            citations=citations,
        )
