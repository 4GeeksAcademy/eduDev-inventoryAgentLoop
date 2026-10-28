"""Educational manual Groq tool loop; inventory remains owned by the HTTP API."""

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_API = "http://127.0.0.1:8000"
SYSTEM_PROMPT = """You are an inventory assistant. Use the inventory API as the only
source of stock and product IDs; never invent them. Resolve product names by
listing inventory first. Ask the user when products are ambiguous or units are
missing. Each product has one fixed unit. Do not convert units or forecast weekly
demand. Report tool failures truthfully, never as successes. A failed write may
have applied: inspect inventory and ask before attempting it again. Reply in the
user's language. Do not expose private reasoning."""


def tool_schema(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required, "additionalProperties": False}}}


DECIMAL = {"type": ["number", "string"], "description": "Number or decimal string in the product's fixed unit"}
TOOLS = [
    tool_schema("get_inventory", "List all products and their IDs, quantities and units", {}, []),
    tool_schema("add_product", "Create a product with an explicit unit", {
        "name": {"type": "string"}, "quantity": DECIMAL,
        "unit": {"type": "string"}}, ["name", "quantity", "unit"]),
    tool_schema("change_stock", "Apply a signed delta to an existing product", {
        "product_id": {"type": "integer", "minimum": 1}, "delta": DECIMAL},
        ["product_id", "delta"]),
    tool_schema("get_alerts", "List products strictly below threshold (default 10)", {
        "threshold": DECIMAL}, []),
]


def execute_tool(name, arguments, api_base_url=DEFAULT_API):
    """Dispatch only known routes. Never retry HTTP requests, especially writes."""
    try:
        schema = next((t["function"]["parameters"] for t in TOOLS
                       if t["function"]["name"] == name), None)
        if schema is None:
            raise ValueError("Unknown tool")
        args = json.loads(arguments)
        if not isinstance(args, dict):
            raise ValueError("Arguments must be an object")
        if set(args) - set(schema["properties"]) or set(schema["required"]) - set(args):
            raise ValueError("Unexpected or missing arguments")
        for key, value in args.items():
            types = schema["properties"][key]["type"]
            if types == "integer":
                valid = type(value) is int and value > 0
            elif types == "string":
                valid = isinstance(value, str) and bool(value.strip())
            else:
                valid = type(value) in (int, float, str)
            if not valid:
                raise ValueError(f"Invalid argument: {key}")
        method, route, body = "GET", "/inventory", None
        if name == "add_product":
            method, body = "POST", args
        elif name == "change_stock":
            method, route, body = "PATCH", f"/inventory/{args['product_id']}", {"delta": args["delta"]}
        elif name == "get_alerts":
            route += "/alerts?" + urlencode({"threshold": args.get("threshold", 10)})
        request = Request(api_base_url.rstrip("/") + route, method=method,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=15) as response:
            return json.dumps(json.loads(response.read()), ensure_ascii=False)
    except HTTPError as error:
        return json.dumps({"error": f"API HTTP {error.code}",
                           "detail": error.read().decode("utf-8", errors="replace")})
    except (URLError, OSError):
        return json.dumps({"error": "API unavailable or request timed out. A write may have applied; do not blindly retry."})
    except (ValueError, TypeError):
        return json.dumps({"error": "Invalid tool arguments or invalid API JSON response"})


def new_messages():
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def log_event(log_path, actor, message, tool_call=""):
    """Append each public event immediately; no reasoning traces are requested."""
    path = Path(log_path)
    with path.open("a", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        if target.tell() == 0:
            writer.writerow(["actor", "message", "tool_call", "timestamp"])
        writer.writerow([actor, message, tool_call, datetime.now(timezone.utc).isoformat()])


def run_turn(client, messages, text, log_path=ROOT / "conversation_log.csv", *,
             api_base_url=DEFAULT_API, model=DEFAULT_MODEL, max_iterations=12):
    """Mutate session history in place, returning final text or None on failure."""
    messages.append({"role": "user", "content": text})
    log_event(log_path, "user", text)
    for _ in range(max_iterations):
        try:
            reply = client.chat.completions.create(
                model=model, messages=messages, tools=TOOLS).choices[0].message
        except OpenAIError:
            # Avoid printing SDK exception strings: they may include request data.
            print("Groq request failed. Check connectivity, key, model or quota. No automatic retry; you may continue or quit.")
            return None
        assistant = {"role": "assistant", "content": reply.content}
        calls = reply.tool_calls or []
        if calls:
            assistant["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {
                    "name": c.function.name, "arguments": c.function.arguments}}
                for c in calls]
        messages.append(assistant)
        if reply.content:
            log_event(log_path, "agent", reply.content)
            print(reply.content)
        for call in calls:
            log_event(log_path, "agent", json.dumps({"name": call.function.name,
                      "arguments": call.function.arguments}, ensure_ascii=False), call.function.name)
            result = execute_tool(call.function.name, call.function.arguments, api_base_url)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            log_event(log_path, "tool", result, call.function.name)
        if not calls:
            return reply.content
    # All pending calls have results, even when stopping at the iteration limit.
    print("Tool iteration limit reached. Inspect inventory before requesting further changes.")
    return None


def main():
    # Configuration loading is deliberately limited to CLI entry, never import.
    load_dotenv(ROOT / ".env")
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        print("Set GROQ_API_KEY in the environment or project-root .env before starting.")
        return 1
    api_base_url = os.environ.get("API_BASE_URL", DEFAULT_API)
    if "error" in json.loads(execute_tool("get_inventory", "{}", api_base_url)):
        print("Inventory API unavailable. Start uvicorn api.app:app first; check API_BASE_URL.")
        return 1
    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1", max_retries=0)
    messages = new_messages()
    print("Inventory assistant ready. Type exit or quit to leave.")
    try:
        while True:
            text = input("You: ").strip()
            if text.lower() in {"exit", "quit"}:
                break
            if text:
                run_turn(client, messages, text, api_base_url=api_base_url,
                         model=os.environ.get("GROQ_MODEL", DEFAULT_MODEL))
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
    except OSError:
        print("Cannot write conversation log; stopping to avoid unlogged actions.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
