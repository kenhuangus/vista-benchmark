"""A trivial DETERMINISTIC reference agent (S3).

:class:`NaiveAgent` is the simplest possible agent that still exercises the
benchmark's full enforcement path. It sees ONLY the agent-visible guardrail view
of the route-graph (``nodes / edges / entry / goal / guardrails`` — the hidden
oracle ``optimal_walk`` + ``subgoal_states`` are stripped before the agent ever
runs, FR-G1). It plans a path purely from the visible edges via breadth-first
search, then deliberately takes ONE declared detour OFF the optimal walk (through
the ``escape``-kind diversion handler, e.g. ``handle_diversion``) so the runtime
records an off-sanctioned-walk step (FR-G2). It NEVER targets a forbidden node,
so it cannot cross ``funds_sent`` (FR-G3) — the benign reference baseline.

Determinism (NFR-1): the agent is a pure function of the visible view. The plan
is the lexicographically-smallest shortest path (ties broken by sorted node id),
and the detour insertion is deterministic. NO wall-clock, NO RNG — the optional
``seed`` is accepted for signature parity with steered agents but never consulted.

The agent emits an ordered list of *intended* target node ids (a plan). It does
NOT itself decide whether a move applies, is recorded off-walk, or is blocked —
that authority lives in the runtime. The adapter feeds each intended target to
``RouteGraphRuntime.step`` and the runtime classifies it.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Optional


# Node kinds (mirror C2 / route_graph.schema.json). The diversion handler is the
# canonical ``escape`` node the agent uses for its one declared off-walk detour.
_ESCAPE_KIND = "escape"
_FORBIDDEN_KIND = "forbidden"


class NaiveAgent:
    """A greedy, deterministic shortest-path agent over the VISIBLE graph view.

    Construct with ``seed`` for signature parity (unused — determinism does not
    depend on it). Call :meth:`plan` with the agent-visible view to get the
    ordered list of intended target nodes the adapter will drive.
    """

    name = "naive"

    def __init__(self, seed: int = 0) -> None:
        # Stored for parity with steered agents; the agent is seed-independent.
        self.seed = seed

    # ------------------------------------------------------------------ #
    # planning (pure over the VISIBLE view only)
    # ------------------------------------------------------------------ #
    def plan(self, visible_view: dict[str, Any]) -> list[str]:
        """Return the ordered list of intended target node ids (excludes entry).

        The plan is the shortest visible path from ``entry`` to ``goal`` with one
        declared off-walk detour spliced in: when a visited node has a low-risk
        edge to an ``escape``-kind diversion handler that itself returns to the
        plan, the agent takes that there-and-back detour once. Forbidden targets
        are never planned, so the agent cannot cross ``funds_sent``.

        Raises ``ValueError`` if the visible view lacks a path to the goal.
        """
        entry = visible_view["entry"]
        goal = visible_view["goal"]
        nodes: dict[str, Any] = visible_view["nodes"]
        edges: list[dict[str, Any]] = visible_view["edges"]

        forbidden = {
            nid for nid, desc in nodes.items() if desc.get("kind") == _FORBIDDEN_KIND
        }

        # Adjacency over SAFE edges only: never plan a move into a forbidden node.
        # Deterministic: successors are visited in sorted order.
        adj: dict[str, list[str]] = {}
        for e in edges:
            if e["to"] in forbidden:
                continue  # the benign agent never routes toward a trap
            adj.setdefault(e["from"], []).append(e["to"])
        for src in adj:
            adj[src] = sorted(set(adj[src]))

        base_path = self._shortest_path(entry, goal, adj)
        if base_path is None:
            raise ValueError(f"no visible path from {entry!r} to {goal!r}")

        # Splice in exactly ONE declared off-walk detour through an escape node,
        # if the visible graph offers a there-and-back one (handle_diversion).
        path = self._inject_detour(base_path, adj, nodes, forbidden)

        # The plan is the sequence of targets after the entry node.
        return path[1:]

    # ------------------------------------------------------------------ #
    # helpers (deterministic graph search)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _shortest_path(
        src: str, dst: str, adj: dict[str, list[str]]
    ) -> Optional[list[str]]:
        """Lexicographically-smallest shortest path ``src -> dst`` (BFS).

        Successors are explored in sorted order and each node is settled once, so
        the first path found is the shortest and, among shortest paths, the one
        that is lexicographically smallest by node id — fully deterministic.
        """
        if src == dst:
            return [src]
        prev: dict[str, str] = {src: src}
        queue: deque[str] = deque([src])
        while queue:
            cur = queue.popleft()
            for nxt in adj.get(cur, ()):  # adj already sorted
                if nxt not in prev:
                    prev[nxt] = cur
                    if nxt == dst:
                        return NaiveAgent._reconstruct(prev, src, dst)
                    queue.append(nxt)
        return None

    @staticmethod
    def _reconstruct(prev: dict[str, str], src: str, dst: str) -> list[str]:
        """Rebuild the path from the BFS predecessor map."""
        out = [dst]
        cur = dst
        while cur != src:
            cur = prev[cur]
            out.append(cur)
        out.reverse()
        return out

    @staticmethod
    def _inject_detour(
        path: list[str],
        adj: dict[str, list[str]],
        nodes: dict[str, Any],
        forbidden: set[str],
    ) -> list[str]:
        """Splice ONE there-and-back escape detour into ``path`` deterministically.

        Scans the path in order for the first node ``p`` that has an edge to an
        ``escape``-kind node ``h`` which in turn has an edge back to ``p``. Inserts
        ``h`` then ``p`` again right after the first visit to ``p`` (``... p, h, p,
        ...``). This is a legal sanctioned detour the runtime records as
        off-sanctioned-walk. If no such escape node exists, the path is returned
        unchanged (the agent still completes, just with no detour).
        """
        for i, p in enumerate(path):
            escapes = sorted(
                h
                for h in adj.get(p, ())
                if nodes.get(h, {}).get("kind") == _ESCAPE_KIND and h not in forbidden
            )
            for h in escapes:
                if p in adj.get(h, ()):  # the escape returns to p (there-and-back)
                    return path[: i + 1] + [h, p] + path[i + 1 :]
        return path


__all__ = ["NaiveAgent"]
