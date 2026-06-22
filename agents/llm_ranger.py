"""A model-backed three-role Ranger — one LLMAgent in all three seats.

The deterministic :class:`agents.ranger.RangerAgent` splits into **Scout** (plan +
escalate + authorize), sandboxed **Worker** (act / request only), and offline
**Dreamer** (propose working-graph edits the RSI gate judges). The plan/act/rsi
runners already drive a real model through those seams, but each runner builds its
*own* :class:`LLMAgent`, so the three roles never share one agent or one cost
ledger — the model is multi-role only across separate processes, never as one
coherent agent.

:class:`LLMRanger` unifies them: a SINGLE :class:`LLMAgent` backs Scout (``plan``)
and Worker (``act``), and an :class:`LLMDreamer` over that *same* agent is the
Dreamer (``propose_cycle`` -> the harness RSI gate). One object, one
``usage``/cost ledger, every Ranger role filled by the model — the model-backed
mirror of :class:`RangerAgent`. It exposes the union of the seams the existing
adapters call (``plan``, ``act``, ``set_journey_context``, ``usage``, ``name``),
so :class:`agents.stepwise_adapter.StepwiseAdapter` drives it unchanged;
:func:`harness.rsi.run_rsi` drives ``self.dreamer``.

``experiments/ranger_run.py`` orchestrates one journey end-to-end (Scout plan +
Worker stepwise execution + Dreamer cycles) and reports every axis plus a single
token total from this one agent — the actual benchmark run exercising the FULL
long-horizon, multi-role agent rather than a single plan/act policy.
"""

from __future__ import annotations

from typing import Any, Optional

from agents.llm_agent import LLMAgent
from agents.llm_dreamer import LLMDreamer


class LLMRanger:
    """One real model wearing all three Ranger hats, sharing a single ledger.

    Pass ``llm`` to reuse/inject an existing agent (the runners build one from
    ``model``; tests inject a stub exposing ``plan``/``act``/``complete``/``usage``/
    ``set_journey_context``). When ``llm`` is given, ``model``/``seed`` are read
    from it for labelling.
    """

    def __init__(
        self,
        *,
        model: str = "sonnet",
        seed: int = 0,
        timeout: int = 150,
        gemini_mode: str = "vertex",
        vertex_project: Optional[str] = None,
        vertex_location: Optional[str] = None,
        vertex_key: Optional[str] = None,
        dreamer_max_edits: int = 2,
        llm: Optional[Any] = None,
    ) -> None:
        self.llm = llm or LLMAgent(
            model=model, seed=seed, timeout=timeout, gemini_mode=gemini_mode,
            vertex_project=vertex_project, vertex_location=vertex_location,
            vertex_key=vertex_key,
        )
        # Scout + Worker are the SAME model instance: planning authority and the
        # sandboxed executor share one agent and therefore one usage/cost ledger.
        # The Dreamer wraps that same agent for offline self-edit proposals.
        self.scout = self.llm
        self.worker = self.llm
        self.dreamer = LLMDreamer(self.llm, max_edits=dreamer_max_edits)
        self.model = getattr(self.llm, "model", model)
        self.seed = getattr(self.llm, "seed", seed)
        self.name = f"llm-ranger:{self.model}"

    # The single ledger every role writes to (plan + act + dreamer completions).
    @property
    def usage(self) -> dict[str, Any]:
        return self.llm.usage

    def set_journey_context(self, journey: dict[str, Any]) -> None:
        self.llm.set_journey_context(journey)

    # -- Scout seam: planning authority (cost-optimal walk + escalation intent) -- #
    def plan(self, visible_view: dict[str, Any]) -> list[str]:
        return self.llm.plan(visible_view)

    # -- Worker seam: sandboxed stepwise execution (one action per turn) --------- #
    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        return self.llm.act(observation)

    # -- Dreamer seam is driven by harness.rsi.run_rsi(working, self.dreamer, ...) #


__all__ = ["LLMRanger"]
