"""Grok backend wiring for LLMAgent — deterministic, no model calls.

Pins that grok-* model names route to the native-Windows grok backend (not WSL) and
that the Grok CLI JSON envelope ({text, stopReason, thought, ...}) normalizes into the
shared {result, usage, total_cost_usd, modelUsage} shape with zero usage (the CLI
surfaces no token counts). A live end-to-end check is separate (env-gated) so the suite
stays offline and deterministic.

    python -m unittest agents.tests.test_llm_agent_grok
"""

from __future__ import annotations

import json
import os
import unittest

from agents.llm_agent import LLMAgent, LLMAgentError, _grok_bin


class TestGrokBackendInference(unittest.TestCase):
    def test_grok_models_route_to_grok_backend(self) -> None:
        self.assertEqual(LLMAgent(model="grok-build").backend, "grok")
        self.assertEqual(LLMAgent(model="grok-composer-2.5-fast").backend, "grok")

    def test_other_models_unchanged(self) -> None:
        self.assertEqual(LLMAgent(model="gemini-2.5-flash").backend, "gemini")
        self.assertEqual(LLMAgent(model="sonnet").backend, "claude")
        self.assertEqual(LLMAgent(model="opus").backend, "claude")

    def test_explicit_backend_override_wins(self) -> None:
        self.assertEqual(LLMAgent(model="grok-build", backend="claude").backend, "claude")

    def test_grok_bin_resolution_honours_env(self) -> None:
        prev = os.environ.get("GROK_BIN")
        os.environ["GROK_BIN"] = "/custom/grok"
        try:
            self.assertEqual(_grok_bin(), "/custom/grok")
        finally:
            if prev is None:
                del os.environ["GROK_BIN"]
            else:
                os.environ["GROK_BIN"] = prev


class TestParseGrokEnvelope(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = LLMAgent(model="grok-build")

    def test_extracts_text_and_zeros_usage(self) -> None:
        # The real CLI returns the reply (a JSON array of node ids) inside "text".
        stdout = json.dumps({
            "text": '["qualify", "inquiry_complete"]',
            "stopReason": "EndTurn",
            "thought": "reasoning that must be ignored",
            "sessionId": "abc",
        })
        env = self.agent._parse_grok(stdout)
        self.assertEqual(env["result"], '["qualify", "inquiry_complete"]')
        self.assertEqual(env["total_cost_usd"], 0.0)
        self.assertEqual(env["usage"]["input_tokens"], 0)
        self.assertEqual(env["usage"]["output_tokens"], 0)
        self.assertIn("grok-build", env["modelUsage"])

    def test_envelope_flows_through_accumulate_usage(self) -> None:
        env = self.agent._parse_grok('{"text": "PONG", "stopReason": "EndTurn"}')
        self.agent._accumulate_usage(env)
        self.assertEqual(self.agent.usage["calls"], 1)
        self.assertEqual(self.agent.usage["cost_usd"], 0.0)
        self.assertEqual(self.agent.usage["output_tokens"], 0)

    def test_parse_grok_finds_json_amid_log_lines(self) -> None:
        # grok writes INFO logs to stderr, but be robust if a line leaks onto stdout.
        stdout = 'INFO starting\n{"text": "[]", "stopReason": "EndTurn"}\n'
        env = self.agent._parse_grok(stdout)
        self.assertEqual(env["result"], "[]")

    def test_missing_text_raises(self) -> None:
        with self.assertRaises(LLMAgentError):
            self.agent._parse_grok('{"stopReason": "EndTurn", "thought": "x"}')

    def test_empty_text_cancelled_raises(self) -> None:
        # The transient proxy-cancellation shape: 0-exit envelope, empty text. Must
        # raise so _call_grok retries it rather than returning an empty plan/action.
        with self.assertRaises(LLMAgentError):
            self.agent._parse_grok('{"text": "", "stopReason": "Cancelled"}')

    def test_no_json_raises(self) -> None:
        with self.assertRaises(LLMAgentError):
            self.agent._parse_grok("not json at all")


if __name__ == "__main__":
    unittest.main()
