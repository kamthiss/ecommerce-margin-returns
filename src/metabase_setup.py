import os
import time

import requests

URL = os.environ.get("MB_URL", "http://localhost:3001")
EMAIL = os.environ.get("MB_ADMIN_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("MB_ADMIN_PASSWORD", "Metabase-local-1")

COLLECTION = "Маржа и возвраты"
MART = "mart_category_channel_month"
TABLES = [MART, "mart_returns_by_return_month", "fct_orders", "fct_order_lines", "fct_returns", "dim_products", "dim_channels"]

LABELS = {
    "order_month": "Месяц заказа",
    "return_month": "Месяц возврата",
    "is_mature": "Зрелый месяц",
    "category": "Категория",
    "channel": "Канал",
    "order_id": "Заказ",
    "order_item_id": "Позиция",
    "return_id": "Возврат",
    "product_id": "Товар",
    "customer_id": "Клиент",
    "status": "Статус",
    "order_date": "Дата заказа",
    "return_date": "Дата возврата",
    "quantity": "Количество",
    "returned_qty": "Возвращено, шт.",
    "net_sales": "Чистые продажи",
    "cost": "Себестоимость",
    "commission": "Комиссия канала",
    "coupon_amount": "Купон",
    "shipping_fee": "Доставка",
    "condition": "Состояние",
    "return_amount": "Сумма возврата",
    "cost_reversal": "Сторно себестоимости",
    "return_shipping_cost": "Обратная доставка",
}

PARAMS = {
    "month": {"name": "Месяц заказа", "slug": "month", "type": "date/month-year", "sectionId": "date"},
    "category": {"name": "Категория", "slug": "category", "type": "string/=", "sectionId": "string"},
    "channel": {"name": "Канал", "slug": "channel", "type": "string/=", "sectionId": "string"},
    "mature": {"name": "Только зрелые месяцы", "slug": "mature", "type": "boolean/="},
    "order": {"name": "Заказ", "slug": "order_id", "type": "id", "sectionId": "id"},
}

s = requests.Session()


def api(method, path, **kw):
    r = s.request(method, f"{URL}/api{path}", **kw)
    r.raise_for_status()
    return r.json() if r.content else None


def wait_ready():
    for _ in range(150):
        try:
            if requests.get(f"{URL}/api/health", timeout=5).json().get("status") == "ok":
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise TimeoutError("Metabase не ответил на /api/health")


def login():
    props = api("GET", "/session/properties")
    if not props["has-user-setup"]:
        api("POST", "/setup", json={
            "token": props["setup-token"],
            "user": {"email": EMAIL, "password": PASSWORD, "first_name": "Admin", "last_name": "Local"},
            "prefs": {"site_name": "Ecommerce", "site_locale": "ru", "allow_tracking": False},
        })
    s.headers["X-Metabase-Session"] = api("POST", "/session", json={"username": EMAIL, "password": PASSWORD})["id"]


def connect_db():
    found = [d for d in api("GET", "/database")["data"] if d["name"] == "ecommerce"]
    db = found[0] if found else api("POST", "/database", json={
        "engine": "postgres",
        "name": "ecommerce",
        "details": {
            "host": "postgres",
            "port": 5432,
            "dbname": "ecommerce",
            "user": "analyst",
            "password": "analyst",
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": "marts",
        },
    })
    api("POST", f"/database/{db['id']}/sync_schema")
    for _ in range(90):
        meta = api("GET", f"/database/{db['id']}/metadata")
        tables = {t["name"]: t for t in meta["tables"] if t["schema"] == "marts"}
        if meta["initial_sync_status"] == "complete" and set(TABLES) <= tables.keys():
            return db["id"], {n: {"id": t["id"], "fields": {f["name"]: f for f in t["fields"]}} for n, t in tables.items()}
        time.sleep(2)
    raise TimeoutError("схема marts не синхронизировалась")


def set_labels(tables):
    for name in TABLES:
        for col, f in tables[name]["fields"].items():
            if col in LABELS and f["display_name"] != LABELS[col]:
                api("PUT", f"/field/{f['id']}", json={"display_name": LABELS[col]})


def reset_collection():
    found = [c for c in api("GET", "/collection") if c["name"] == COLLECTION and not c.get("archived")]
    if not found:
        return api("POST", "/collection", json={"name": COLLECTION})["id"]
    coll = found[0]["id"]
    for model in ["dashboard", "card"]:
        for item in api("GET", f"/collection/{coll}/items", params={"models": model})["data"]:
            api("DELETE", f"/{model}/{item['id']}")
    return coll


def main():
    """Настраивает Metabase и пересоздаёт дашборд по витринам marts."""
    wait_ready()
    login()
    db, tables = connect_db()
    set_labels(tables)
    coll = reset_collection()

    def f(table, col, opts=None):
        return ["field", tables[table]["fields"][col]["id"], opts]

    def m(col):
        return f(MART, col)

    def agg(name, title, expr):
        return ["aggregation-options", expr, {"name": name, "display-name": title}]

    def card(name, display, query, viz=None):
        return api("POST", "/card", json={
            "name": name,
            "display": display,
            "collection_id": coll,
            "visualization_settings": viz or {},
            "dataset_query": {"type": "query", "database": db, "query": query},
        })["id"]

    def dashcard(card_id, row, col, w, h, maps, series_maps=(), **extra):
        mappings = [(p, card_id, field) for p, field in maps.items()] + list(series_maps)
        return {
            "card_id": card_id,
            "row": row,
            "col": col,
            "size_x": w,
            "size_y": h,
            "parameter_mappings": [{"parameter_id": p, "card_id": c, "target": ["dimension", field]} for p, c, field in mappings],
            **extra,
        }

    def dashboard(name, params, dashcards, width="fixed"):
        d = api("POST", "/dashboard", json={
            "name": name,
            "collection_id": coll,
            "parameters": [{"id": p, **PARAMS[p]} for p in params],
        })
        for i, dc in enumerate(dashcards):
            dc["id"] = -i - 1
        api("PUT", f"/dashboard/{d['id']}", json={"width": width, "dashcards": dashcards})
        return d["id"]

    def cols(**settings):
        return {"column_settings": {f'["name","{k}"]': v for k, v in settings.items()}}

    def pct(decimals=1):
        return {"number_style": "percent", "decimals": decimals}

    def link(target, mapping):
        return {"type": "link", "linkType": "dashboard", "targetId": target, "parameterMapping": {
            p: {"id": p, "source": src, "target": {"type": "parameter", "id": p}} for p, src in mapping.items()
        }}

    def by_column(name):
        return {"type": "column", "id": name, "name": name}

    def by_param(p):
        return {"type": "parameter", "id": p, "name": PARAMS[p]["name"]}

    def table_card(name, table, fields, filters=None):
        query = {
            "source-table": tables[table]["id"],
            "fields": [f(table, c) for c in fields],
            "order-by": [["desc", f(table, fields[0])]],
        }
        if filters:
            query["filter"] = filters
        settings = {c: {"number_separators": "."} for c in fields if c.endswith("_id")}
        settings.update({c: {"number_style": "decimal"} for c in fields if c in ("cost", "cost_reversal")})
        return card(name, "table", query, cols(**settings))

    def bar_viz(col, metrics, title):
        viz = cols(**{col: {"column_title": LABELS[col]}}, **{k: pct() for k in metrics})
        viz.update({"graph.dimensions": [col], "graph.metrics": metrics,
                    "graph.x_axis.title_text": LABELS[col], "graph.y_axis.title_text": title,
                    "graph.show_values": True})
        return viz

    order_cols = ["order_id", "order_date", "customer_id", "channel", "status", "net_sales", "coupon_amount", "shipping_fee"]
    line_cols = ["order_item_id", "order_id", "order_date", "category", "channel", "product_id", "quantity", "net_sales", "cost", "commission"]
    return_cols = ["return_id", "order_item_id", "return_date", "condition", "returned_qty", "return_amount", "cost_reversal", "return_shipping_cost"]

    order_dash = dashboard("Заказ", ["order"], [
        dashcard(table_card("Заказ", "fct_orders", order_cols), 0, 0, 24, 4, {"order": f("fct_orders", "order_id")}),
        dashcard(table_card("Позиции заказа", "fct_order_lines", line_cols), 4, 0, 24, 5,
                 {"order": f("fct_order_lines", "order_id")}),
        dashcard(table_card("Возвраты по заказу", "fct_returns", return_cols), 9, 0, 24, 5,
                 {"order": f("fct_returns", "order_id")}),
    ])
    open_order = cols(order_id={"number_separators": ".", "click_behavior": link(order_dash, {"order": by_column("order_id")})})

    lines_dash = dashboard("Позиции заказов", ["month", "category", "channel"], [
        dashcard(
            table_card("Позиции заказов", "fct_order_lines", line_cols, ["=", f("fct_order_lines", "is_cancelled"), False]),
            0, 0, 24, 12,
            {p: f("fct_order_lines", c) for p, c in [("month", "order_month"), ("category", "category"), ("channel", "channel")]},
            visualization_settings=open_order,
        ),
    ])

    def open_lines(col):
        mapping = {p: by_param(p) for p in ["month", "category", "channel"]}
        mapping[col] = by_column(col)
        return {"click_behavior": link(lines_dash, mapping)}

    mart_maps = {"month": m("order_month"), "category": m("category"), "channel": m("channel"), "mature": m("is_mature")}
    ns = ["sum", m("net_sales")]
    mar = ["sum", m("margin_after_returns")]
    margin_before = ["/", ["sum", m("margin_before_returns")], ["sum", m("costed_net_sales")]]
    margin_after = ["/", mar, ["-", ["sum", m("costed_net_sales")], ["sum", m("costed_returns_amount")]]]

    def kpi(name, expr, fmt):
        viz = cols(value=fmt)
        viz["scalar.compact_primary_number"] = False
        return card(name, "scalar", {"source-table": tables[MART]["id"], "aggregation": [agg("value", name, expr)]}, viz)

    money = {"number_style": "decimal", "decimals": 0}
    kpis = [
        kpi("Чистые продажи", ns, money),
        kpi("Маржинальный доход после возвратов", mar, money),
        kpi("Маржа % до возвратов", margin_before, pct()),
        kpi("Маржа % после возвратов", margin_after, pct()),
        kpi("Доля возвратов в продажах", ["/", ["sum", m("returns_amount")], ns], pct()),
        kpi("Покрытие себестоимостью", ["/", ["sum", m("costed_net_sales")], ns], pct(2)),
    ]

    def share_card(name, dim_table, col):
        dim = f(dim_table, col, {"join-alias": "dim"})
        same = ["=", m(col), dim]
        query = {
            "source-table": tables[MART]["id"],
            "joins": [{
                "source-table": tables[dim_table]["id"],
                "alias": "dim",
                "condition": ["=", dim, dim],
                "fields": "none",
                "strategy": "left-join",
            }],
            "breakout": [dim],
            "aggregation": [
                agg("sales_share", "Доля в чистых продажах", ["/", ["sum-where", m("net_sales"), same], ns]),
                agg("margin_share", "Доля в маржинальном доходе", ["/", ["sum-where", m("margin_after_returns"), same], mar]),
            ],
        }
        return card(name, "bar", query, bar_viz(col, ["sales_share", "margin_share"], "Доля")), dim

    def margin_card(name, col):
        query = {
            "source-table": tables[MART]["id"],
            "breakout": [m(col)],
            "aggregation": [
                agg("margin_before", "Маржа % до возвратов", margin_before),
                agg("margin_after", "Маржа % после возвратов", margin_after),
            ],
        }
        return card(name, "bar", query, bar_viz(col, ["margin_before", "margin_after"], "Маржа"))

    cat_share, cat_dim = share_card("Доля категорий в продажах и марже", "dim_products", "category")
    ch_share, ch_dim = share_card("Доля каналов в продажах и марже", "dim_channels", "channel")
    cat_margin = margin_card("Маржа % по категориям", "category")
    ch_margin = margin_card("Маржа % по каналам", "channel")

    returns_by_order = card("Возвраты по месяцу заказа", "bar", {
        "source-table": tables[MART]["id"],
        "breakout": [f(MART, "order_month", {"temporal-unit": "month"})],
        "aggregation": [
            agg("mature", "По дате заказа, зрелые месяцы", ["sum-where", m("returns_amount"), ["=", m("is_mature"), True]]),
            agg("immature", "По дате заказа, незрелые месяцы", ["sum-where", m("returns_amount"), ["=", m("is_mature"), False]]),
        ],
    })
    rr = "mart_returns_by_return_month"
    returns_by_return = card("По дате возврата", "line", {
        "source-table": tables[rr]["id"],
        "breakout": [f(rr, "return_month", {"temporal-unit": "month"})],
        "aggregation": [agg("returns", "По дате возврата", ["sum", f(rr, "returns_amount")])],
    })

    orders = table_card("Заказы", "fct_orders", order_cols)

    main_dash = dashboard("Прибыль категорий и каналов", ["month", "category", "channel", "mature"], [
        *[dashcard(k, 3 * (i // 3), 8 * (i % 3), 8, 3, mart_maps) for i, k in enumerate(kpis)],
        dashcard(cat_share, 6, 0, 12, 8, {**mart_maps, "category": cat_dim},
                 visualization_settings=open_lines("category")),
        dashcard(ch_share, 6, 12, 12, 8, {**mart_maps, "channel": ch_dim},
                 visualization_settings=open_lines("channel")),
        dashcard(cat_margin, 14, 0, 12, 8, mart_maps,
                 visualization_settings=open_lines("category")),
        dashcard(ch_margin, 14, 12, 12, 8, mart_maps,
                 visualization_settings=open_lines("channel")),
        dashcard(
            returns_by_order, 22, 0, 24, 8, mart_maps,
            series=[{"id": returns_by_return}],
            series_maps=[("category", returns_by_return, f(rr, "category")), ("channel", returns_by_return, f(rr, "channel"))],
            visualization_settings={
                "card.title": "Возвраты помесячно: по дате заказа и по дате возврата",
                "stackable.stack_type": "stacked",
                "series_settings": {
                    "mature": {"title": "По дате заказа, зрелые месяцы"},
                    "immature": {"title": "По дате заказа, незрелые месяцы"},
                    "По дате возврата": {"display": "line"},
                },
                "graph.x_axis.title_text": "Месяц",
                "graph.y_axis.title_text": "Сумма возвратов",
            },
        ),
        dashcard(orders, 30, 0, 24, 10, {"month": f("fct_orders", "order_month"), "channel": f("fct_orders", "channel")},
                 visualization_settings=open_order),
    ], width="full")
    print(f"{URL}/dashboard/{main_dash}")


if __name__ == "__main__":
    main()
