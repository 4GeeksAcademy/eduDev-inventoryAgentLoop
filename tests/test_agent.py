import csv
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import agent


def call(name, arguments, identity="c1"):
    return NS(id=identity, function=NS(name=name, arguments=arguments))


def response(text=None, calls=None):
    return NS(choices=[NS(message=NS(content=text, tool_calls=calls or []))])


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / "events.csv"
        self.client = Mock()

    def turn(self, messages, text="hello"):
        return agent.run_turn(self.client, messages, text, self.log,
                              api_base_url="http://localhost:8000", model="test")

    def test_schemas_and_http_mapping(self):
        self.assertEqual(len(agent.TOOLS), 4)
        for tool in agent.TOOLS:
            self.assertEqual(tool["type"], "function")
            self.assertEqual(tool["function"]["parameters"]["type"], "object")
        cases = [
            ("get_inventory", {}, "GET", "/inventory", None),
            ("add_product", {"name": "Rice", "quantity": "2.5", "unit": "kg"},
             "POST", "/inventory", {"name": "Rice", "quantity": "2.5", "unit": "kg"}),
            ("change_stock", {"product_id": 7, "delta": -1}, "PATCH",
             "/inventory/7", {"delta": -1}),
            ("get_alerts", {"threshold": 3}, "GET", "/inventory/alerts?threshold=3", None),
            ("get_alerts", {}, "GET", "/inventory/alerts?threshold=10", None),
        ]
        for name, args, method, suffix, body in cases:
            with self.subTest(name=name), patch("agent.urlopen") as opening:
                opening.return_value.__enter__.return_value.read.return_value = b'{"quantity":"2.5"}'
                result = agent.execute_tool(name, json.dumps(args), "http://localhost:8000")
                request = opening.call_args.args[0]
                self.assertEqual(request.full_url, "http://localhost:8000" + suffix)
                self.assertEqual(request.get_method(), method)
                self.assertEqual(json.loads(request.data) if request.data else None, body)
                self.assertEqual(json.loads(result), {"quantity": "2.5"})
                self.assertEqual(opening.call_count, 1)

    def test_multistep_multiple_calls_history_and_log_append(self):
        self.client.chat.completions.create.side_effect = [
            response("Checking", [call("get_inventory", "{}")]),
            response(calls=[call("add_product", '{"name":"Rice","quantity":2,"unit":"kg"}', "c2"),
                            call("get_alerts", "{}", "c3")]),
            response("Done"), response("Still here"),
        ]
        snapshots = []
        def execute(*args):
            return '{"ok":true}'
        original = self.client.chat.completions.create.side_effect
        def create(**kwargs):
            snapshots.append(json.loads(json.dumps(kwargs["messages"])))
            return next(original)
        self.client.chat.completions.create.side_effect = create
        messages = agent.new_messages()
        with patch("agent.execute_tool", side_effect=execute) as tool:
            self.assertEqual(self.turn(messages), "Done")
            self.assertEqual(self.turn(messages, "again"), "Still here")
        self.assertEqual(tool.call_count, 3)
        self.assertEqual([m["tool_call_id"] for m in snapshots[2] if m["role"] == "tool"], ["c1", "c2", "c3"])
        self.assertTrue(all(set(m) == {"role", "tool_call_id", "content"}
                            for m in messages if m["role"] == "tool"))
        self.assertIn({"role": "assistant", "content": "Done"}, snapshots[3])
        self.client.chat.completions.create.side_effect = None
        self.client.chat.completions.create.return_value = response("New session")
        self.turn(agent.new_messages(), "new")
        with self.log.open(newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(list(rows[0]), ["actor", "message", "tool_call", "timestamp"])
        self.assertEqual(len(rows), 13)
        self.assertEqual({r["actor"] for r in rows}, {"user", "agent", "tool"})
        from datetime import datetime
        for row in rows:
            self.assertIsNotNone(datetime.fromisoformat(row["timestamp"]).tzinfo)
        requests = [r for r in rows if r["actor"] == "agent" and r["tool_call"]]
        self.assertEqual(len(requests), 3)
        expected_names = ["get_inventory", "add_product", "get_alerts"]
        self.assertEqual([r["tool_call"] for r in requests], expected_names)
        results = [r for r in rows if r["actor"] == "tool"]
        self.assertEqual([r["tool_call"] for r in results], expected_names)
        plain_rows = [r for r in rows if r["actor"] == "user" or
                      (r["actor"] == "agent" and r["message"] in
                       {"Checking", "Done", "Still here", "New session"})]
        self.assertEqual(len(plain_rows), 7)
        self.assertTrue(all(r["tool_call"] == "" for r in plain_rows))
        self.assertIn("quantity", requests[1]["message"])
        self.assertEqual(self.log.read_text().count("actor,message,tool_call,timestamp"), 1)

    def test_bad_tools_are_errors_without_http(self):
        for name, args in [("unknown", "{}"), ("get_inventory", "{"),
                           ("get_inventory", "[]"), ("change_stock", '{"product_id":"../x","delta":1}'),
                           ("add_product", "{}")]:
            with self.subTest(name=name, args=args), patch("agent.urlopen") as opening:
                self.assertIn("error", json.loads(agent.execute_tool(name, args, "http://localhost")))
                opening.assert_not_called()

    def test_http_errors_no_retry(self):
        for error in [URLError("offline"), TimeoutError(),
                      HTTPError("http://localhost", 422, "invalid", {}, io.BytesIO(b'{"detail":"negative"}'))]:
            with self.subTest(error=error), patch("agent.urlopen", side_effect=error) as opening:
                result = json.loads(agent.execute_tool("change_stock", '{"product_id":1,"delta":-2}', "http://localhost"))
                self.assertIn("error", result)
                opening.assert_called_once()

    def test_provider_failure_after_write_keeps_valid_history(self):
        from openai import APIConnectionError
        self.client.chat.completions.create.side_effect = [
            response(calls=[call("change_stock", '{"product_id":1,"delta":1}')]),
            APIConnectionError(request=Mock()),
            response("Recovered"),
        ]
        messages = agent.new_messages()
        with patch("agent.execute_tool", return_value='{"quantity":"3"}') as tool, patch("builtins.print"):
            self.assertIsNone(self.turn(messages))
            self.assertEqual(messages[-1]["role"], "tool")
            self.assertEqual(self.turn(messages, "what happened?"), "Recovered")
            tool.assert_called_once()

    def test_error_results_and_iteration_cap_complete_all_calls(self):
        self.client.chat.completions.create.return_value = response(calls=[
            call("unknown", "{}", "bad1"), call("get_inventory", "{", "bad2")])
        messages = agent.new_messages()
        with patch("agent.urlopen") as opening, patch("builtins.print"):
            result = agent.run_turn(self.client, messages, "check", self.log,
                                    max_iterations=1)
        self.assertIsNone(result)
        opening.assert_not_called()
        self.assertEqual([m["tool_call_id"] for m in messages[-2:]], ["bad1", "bad2"])
        self.assertTrue(all("error" in json.loads(m["content"]) for m in messages[-2:]))
        self.client.chat.completions.create.assert_called_once()

    def test_cli_missing_key_offline_and_clean_exit(self):
        with patch("agent.load_dotenv"), patch.dict("os.environ", {"GROQ_API_KEY": ""}), patch("agent.OpenAI") as sdk, patch("builtins.print"):
            self.assertEqual(agent.main(), 1)
            sdk.assert_not_called()
        for ending in ["quit", "exit", EOFError(), KeyboardInterrupt()]:
            with self.subTest(ending=ending), patch("agent.load_dotenv"), patch.dict("os.environ", {"GROQ_API_KEY": "fake"}), patch("agent.OpenAI") as sdk, patch("agent.execute_tool", return_value="[]"), patch("builtins.input", side_effect=[ending]), patch("builtins.print"):
                self.assertEqual(agent.main(), 0)
                sdk.return_value.chat.completions.create.assert_not_called()
        with patch("agent.load_dotenv"), patch.dict("os.environ", {"GROQ_API_KEY": "fake"}), patch("agent.execute_tool", return_value='{"error":"offline"}'), patch("builtins.input") as prompt, patch("builtins.print"):
            self.assertEqual(agent.main(), 1)
            prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
