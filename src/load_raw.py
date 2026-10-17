import os
from pathlib import Path

import psycopg
from psycopg import sql

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
TABLES = ["customers", "products", "channels", "orders", "order_items", "returns"]


def connect():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5434"),
        dbname=os.getenv("PGDATABASE", "ecommerce"),
        user=os.getenv("PGUSER", "analyst"),
        password=os.getenv("PGPASSWORD", "analyst"),
    )


def load(cur, name):
    path = RAW / f"{name}.csv"
    with path.open() as f:
        cols = f.readline().strip().split(",")
    table = sql.Identifier("raw", name)
    cur.execute(sql.SQL("drop table if exists {}").format(table))
    cur.execute(
        sql.SQL("create table {} ({})").format(
            table,
            sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in cols),
        )
    )
    copy = sql.SQL("copy {} from stdin with (format csv, header true)").format(table)
    with path.open("rb") as f, cur.copy(copy) as cp:
        while chunk := f.read(1 << 20):
            cp.write(chunk)


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("create schema if not exists raw")
        for name in TABLES:
            load(cur, name)
        for name in TABLES:
            cur.execute(sql.SQL("select count(*) from {}").format(sql.Identifier("raw", name)))
            print(f"{name}: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
