import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.csv = Path(self.temp.name) / "inventory.csv"
        self.start_server()

    def start_server(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        env = dict(os.environ, INVENTORY_CSV_PATH=str(self.csv))
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.app:app", "--host",
             "127.0.0.1", "--port", str(port), "--log-level", "error"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.addCleanup(self.stop_server)
        for _ in range(100):
            if self.process.poll() is not None:
                output = self.process.communicate()[0].decode()
                self.fail(f"Server exited during startup:\n{output}")
            try:
                self.request("GET", "/inventory")
                return
            except (URLError, TimeoutError):
                time.sleep(0.05)
        self.fail("Server did not become ready")

    def stop_server(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.communicate(timeout=5)

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.url + path, data=data, method=method,
                          headers={"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def create(self, name="Rice", quantity="12.5", unit="kg"):
        return self.request("POST", "/inventory", {
            "name": name, "quantity": quantity, "unit": unit,
        })

    def test_stock_and_restart(self):
        self.assertEqual(self.request("GET", "/inventory"), (200, []))
        status, rice = self.create(" Rice ", "12.5", " kg ")
        self.assertEqual(status, 201)
        self.assertEqual(rice, {"id": 1, "name": "Rice", "quantity": "12.5", "unit": "kg"})
        self.assertEqual(self.request("PATCH", "/inventory/1", {"delta": "-2.25"})[1]["quantity"], "10.25")
        self.assertEqual(self.request("PATCH", "/inventory/1", {"delta": "0.05"})[1]["quantity"], "10.30")
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", "/inventory")[1][0]["quantity"], "10.30")
        self.assertEqual(self.create("Beans", 0)[1]["id"], 2)
        self.assertEqual(self.csv.read_text().splitlines()[0], "id,name,quantity,unit")

    def test_decimal_precision_and_csv_quoting(self):
        name = 'Rice, "premium"'
        quantity = "123456789012345678901234567890.12"
        self.assertEqual(self.create(name, quantity)[0], 201)
        updated = self.request("PATCH", "/inventory/1", {"delta": "0.01"})
        self.assertEqual(updated[1]["quantity"], "123456789012345678901234567890.13")
        self.assertEqual(self.request("GET", "/inventory")[1][0]["name"], name)

    def test_thresholds(self):
        for quantity in ("0", "9.99", "10", "11"):
            self.create(quantity, quantity)
        self.assertEqual([p["name"] for p in self.request("GET", "/inventory/alerts")[1]], ["0", "9.99"])
        self.assertEqual([p["name"] for p in self.request("GET", "/inventory/alerts?threshold=11")[1]], ["0", "9.99", "10"])
        self.assertEqual(self.request("GET", "/inventory/alerts?threshold=0"), (200, []))
        for value in ("NaN", "Infinity", "bad", "-1"):
            self.assertEqual(self.request("GET", f"/inventory/alerts?threshold={value}")[0], 422)

    def test_invalid_input_and_unknown_id(self):
        for name, quantity, unit in ((" ", 1, "kg"), ("Rice", 1, " "),
                                     ("Rice", -1, "kg"), ("Rice", "NaN", "kg"),
                                     ("Rice", "Infinity", "kg"), ("Rice", "bad", "kg")):
            with self.subTest(name=name, quantity=quantity, unit=unit):
                self.assertEqual(self.create(name, quantity, unit)[0], 422)
        self.assertEqual(self.request("POST", "/inventory", {})[0], 422)
        self.assertEqual(self.request("PATCH", "/inventory/999", {"delta": 1})[0], 404)
        self.create(quantity="0.3")
        for delta in ("-0.31", "NaN", "Infinity", "bad"):
            self.assertEqual(self.request("PATCH", "/inventory/1", {"delta": delta})[0], 422)
        self.assertEqual(self.request("GET", "/inventory")[1][0]["quantity"], "0.3")
        self.assertEqual(self.request("PATCH", "/inventory/1", {"delta": "-0.3"})[1]["quantity"], "0.0")

    def test_malformed_csv_is_not_overwritten(self):
        for content in ("wrong,header\n", "id,name,quantity,unit\n1,Rice,-2,kg\n",
                        "id,name,quantity,unit\n1,Rice,1,kg\n1,Beans,2,kg\n",
                        "id,name,quantity,unit\n1,Rice,NaN,kg\n",
                        "id,name,quantity,unit\n1,Rice,1\n"):
            with self.subTest(content=content):
                self.csv.write_text(content)
                self.assertEqual(self.request("GET", "/inventory")[0], 500)
                self.assertEqual(self.create()[0], 500)
                self.assertEqual(self.csv.read_text(), content)


if __name__ == "__main__":
    unittest.main()
