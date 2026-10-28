"""Single-process inventory API backed by one project-local CSV file."""

import csv
from decimal import Decimal, localcontext
import os
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, StringConstraints, ValidationError


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / os.environ.get("INVENTORY_CSV_PATH", "products.csv")
HEADER = ["id", "name", "quantity", "unit"]
LOCK = Lock()
app = FastAPI(title="Inventory API")

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Stock = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]


class NewProduct(BaseModel):
    name: Text
    quantity: Stock
    unit: Text


class Product(NewProduct):
    id: Annotated[int, Field(gt=0)]


class StockChange(BaseModel):
    delta: FiniteDecimal


def read_products() -> list[Product]:
    """A missing file is empty; malformed existing data must never be replaced."""
    if not CSV_PATH.exists():
        return []
    try:
        with CSV_PATH.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source, strict=True)
            if reader.fieldnames != HEADER:
                raise ValueError("Expected CSV header id,name,quantity,unit")
            products = []
            ids = set()
            for row in reader:
                if set(row) != set(HEADER) or any(value is None for value in row.values()):
                    raise ValueError("Invalid CSV row")
                product = Product.model_validate(row)
                if product.id in ids:
                    raise ValueError("Duplicate product ID")
                ids.add(product.id)
                products.append(product)
            return products
    except (ValueError, csv.Error, ValidationError, OSError) as error:
        raise HTTPException(500, "Cannot read inventory CSV; repair the file before continuing") from error


def write_products(products: list[Product]) -> None:
    # Validation/read happens before opening for writing; the lock covers both.
    try:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=HEADER)
            writer.writeheader()
            writer.writerows(product.model_dump() for product in products)
    except OSError as error:
        raise HTTPException(500, "Cannot write inventory CSV") from error


@app.get("/inventory", response_model=list[Product])
def inventory():
    with LOCK:
        return read_products()


@app.post("/inventory", response_model=Product, status_code=201)
def add_product(body: NewProduct):
    with LOCK:
        products = read_products()
        product = Product(id=max((p.id for p in products), default=0) + 1,
                          **body.model_dump())
        products.append(product)
        write_products(products)
        return product


@app.get("/inventory/alerts", response_model=list[Product])
def alerts(threshold: Annotated[Stock, Query()] = Decimal("10")):
    with LOCK:
        return [product for product in read_products() if product.quantity < threshold]


@app.patch("/inventory/{product_id}", response_model=Product)
def change_stock(product_id: int, body: StockChange):
    with LOCK:
        products = read_products()
        for product in products:
            if product.id == product_id:
                # Preserve decimal precision even when inputs exceed 28 digits.
                with localcontext() as context:
                    values = (product.quantity, body.delta)
                    context.prec = max(v.adjusted() for v in values) - min(
                        v.as_tuple().exponent for v in values
                    ) + 2
                    quantity = product.quantity + body.delta
                if quantity < 0:
                    raise HTTPException(422, "Stock cannot become negative")
                product.quantity = quantity
                write_products(products)
                return product
        raise HTTPException(404, "Product not found")
