"""One local HTTP integration; only the SDK response boundary is mocked."""

import csv
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock
from urllib.error import URLError
from urllib.request import urlopen

import agent


ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def start_server(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.app:app", "--host",
             "127.0.0.1", "--port", str(port), "--log-level", "error"],
            cwd=ROOT, env=dict(os.environ, INVENTORY_CSV_PATH=str(self.stock)),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.addCleanup(self.stop_server, process)
        for _ in range(100):
            if process.poll() is not None:
                self.fail(f"API exited: {process.communicate()[0].decode()}")
            try:
                with urlopen(self.url + "/inventory", timeout=1):
                    return process
            except (URLError, TimeoutError):
                time.sleep(0.05)
        self.fail("API did not become ready")

    @staticmethod
    def stop_server(process):
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=5)

    def test_tool_history_restart_and_append(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.stock = Path(temporary.name) / "inventory.csv"
        log = Path(temporary.name) / "events.csv"
        process = self.start_server()
        product = {"id": 1, "name": "Rice", "quantity": "12", "unit": "kg"}
        updated = dict(product, quantity="9")
        steps = [
            ("add_product", {"name": "Rice", "quantity": "12", "unit": "kg"}, product),
            ("get_inventory", {}, [product]),
            ("change_stock", {"product_id": 1, "delta": "-3"}, updated),
            ("get_alerts", {}, [updated]),
        ]
        client = Mock()
        snapshots = []

        def create(**kwargs):
            history = json.loads(json.dumps(kwargs["messages"]))
            snapshots.append(history)
            index = len(snapshots) - 1
            # Every subsequent SDK request must contain all earlier real results.
            results = [m for m in history if m["role"] == "tool"]
            self.assertEqual(len(results), index)
            for number, result in enumerate(results):
                self.assertEqual(result["tool_call_id"], f"call-{number}")
                self.assertEqual(json.loads(result["content"]), steps[number][2])
                request = next(m for m in history if m.get("tool_calls")
                               and m["tool_calls"][0]["id"] == f"call-{number}")
                self.assertEqual(request["tool_calls"][0]["function"]["name"], steps[number][0])
            if index == len(steps):
                message = NS(content="Rice now has 9 kg and is below 10.", tool_calls=[])
            else:
                name, arguments, _ = steps[index]
                call = NS(id=f"call-{index}", function=NS(
                    name=name, arguments=json.dumps(arguments)))
                message = NS(content=None, tool_calls=[call])
            return NS(choices=[NS(message=message)])

        client.chat.completions.create.side_effect = create
        history = agent.new_messages()
        self.assertEqual(agent.run_turn(
            client, history, "Add Rice with 12 kg, identify it, sell 3 kg and check alerts.",
            log, api_base_url=self.url, model="mock-model"),
            "Rice now has 9 kg and is below 10.")
        self.assertEqual(len(snapshots), 5)
        with self.stock.open(newline="", encoding="utf-8") as source:
            self.assertEqual(list(csv.DictReader(source)), [dict(updated, id="1")])

        self.stop_server(process)
        self.start_server()
        self.assertEqual(json.loads(agent.execute_tool("get_inventory", "{}", self.url)), [updated])
        before = log.read_bytes()
        client.chat.completions.create.side_effect = None
        client.chat.completions.create.return_value = NS(choices=[NS(message=NS(
            content="New session ready.", tool_calls=[]))])
        fresh = agent.new_messages()
        agent.run_turn(client, fresh, "Hello again", log, api_base_url=self.url)
        self.assertEqual([m["role"] for m in fresh], ["system", "user", "assistant"])
        self.assertTrue(log.read_bytes().startswith(before))
        with log.open(newline="", encoding="utf-8") as source:
            rows = list(csv.reader(source))
        header = ["actor", "message", "tool_call", "timestamp"]
        self.assertEqual(rows[0], header)
        self.assertEqual(rows.count(header), 1)
        self.assertEqual(len(rows), 13)  # header + ten first-session + two new events
        expected = [step[0] for step in steps]
        for actor in ("agent", "tool"):
            self.assertEqual([row[2] for row in rows[1:] if row[0] == actor and row[2]], expected)
        self.assertEqual([row[0] for row in rows[-2:]], ["user", "agent"])


if __name__ == "__main__":
    unittest.main()
