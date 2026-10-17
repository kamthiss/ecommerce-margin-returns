from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START = pd.Timestamp("2024-01-01")
END = pd.Timestamp("2025-12-31")
SNAPSHOT = pd.Timestamp("2026-01-15")
N_CUSTOMERS = 15_000
N_ORDERS = 50_000
N_PRODUCTS = 300
FREE_SHIPPING_FROM = 50.0
SHIPPING_FEE = 4.99
RETURN_SHIPPING = 6.50
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"

CATEGORIES = pd.DataFrame(
    {
        "category": ["electronics", "apparel", "home", "beauty", "sports", "books"],
        "weight": [0.15, 0.28, 0.17, 0.15, 0.12, 0.13],
        "median_price": [250.0, 45.0, 60.0, 25.0, 70.0, 18.0],
        "cost_share": [0.85, 0.40, 0.55, 0.45, 0.55, 0.65],
        "return_rate": [0.09, 0.24, 0.08, 0.04, 0.10, 0.02],
        "damaged_share": [0.10, 0.30, 0.10, 0.10, 0.10, 0.10],
    }
).set_index("category")

CHANNELS = pd.DataFrame(
    {
        "channel": ["organic", "email", "paid_search", "social_ads", "marketplace"],
        "fee_pct": [0.0, 0.0, 0.0, 0.0, 15.0],
        "weight": [0.30, 0.12, 0.22, 0.18, 0.18],
    }
).set_index("channel")

SOCIAL_RETURN_MULT = 1.8


def make_products(rng):
    cats = rng.choice(CATEGORIES.index, size=N_PRODUCTS, p=CATEGORIES["weight"])
    median = CATEGORIES.loc[cats, "median_price"].to_numpy()
    price = np.round(median * rng.lognormal(0, 0.35, N_PRODUCTS), 2)
    share = CATEGORIES.loc[cats, "cost_share"].to_numpy() * rng.uniform(0.9, 1.1, N_PRODUCTS)
    cost = np.round(price * share, 2)
    products = pd.DataFrame(
        {
            "product_id": np.arange(1, N_PRODUCTS + 1),
            "sku": [f"SKU-{i:05d}" for i in range(1, N_PRODUCTS + 1)],
            "category": cats,
            "list_price": price,
            "unit_cost": cost,
        }
    )
    missing = rng.choice(N_PRODUCTS, size=int(N_PRODUCTS * 0.05), replace=False)
    products["unit_cost"] = products["unit_cost"].astype("object")
    products.loc[missing, "unit_cost"] = None
    return products


def make_orders(rng):
    customer_weight = rng.pareto(1.5, N_CUSTOMERS) + 1
    customer_weight /= customer_weight.sum()
    customer_ids = rng.choice(np.arange(1, N_CUSTOMERS + 1), size=N_ORDERS, p=customer_weight)

    main_channel = rng.choice(CHANNELS.index, size=N_CUSTOMERS, p=CHANNELS["weight"])
    random_channel = rng.choice(CHANNELS.index, size=N_ORDERS, p=CHANNELS["weight"])
    keep_main = rng.random(N_ORDERS) < 0.7
    channel = np.where(keep_main, main_channel[customer_ids - 1], random_channel)

    days = pd.date_range(START, END, freq="D")
    t = np.arange(len(days)) / len(days)
    season = np.where(days.month.isin([11, 12]), 1.5, 1.0)
    day_weight = (1 + 0.6 * t) * season
    day_weight /= day_weight.sum()
    order_day = rng.choice(days, size=N_ORDERS, p=day_weight)
    seconds = rng.integers(8 * 3600, 24 * 3600, N_ORDERS)
    order_ts = pd.to_datetime(order_day) + pd.to_timedelta(seconds, unit="s")

    orders = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "channel": channel,
            "order_ts": order_ts,
            "status": np.where(rng.random(N_ORDERS) < 0.05, "cancelled", "delivered"),
        }
    ).sort_values("order_ts", ignore_index=True)
    orders.insert(0, "order_id", np.arange(100_001, 100_001 + N_ORDERS))
    return orders


def make_items(rng, orders, products):
    n_items = np.minimum(1 + rng.poisson(1.2, len(orders)), 5)
    items = pd.DataFrame({"order_id": np.repeat(orders["order_id"].to_numpy(), n_items)})
    items = items.merge(orders[["order_id", "channel"]], on="order_id")

    cats = rng.choice(CATEGORIES.index, size=len(items), p=CATEGORIES["weight"])
    by_cat = products.groupby("category")["product_id"].apply(np.array)
    items["product_id"] = [rng.choice(by_cat[c]) for c in cats]
    items = items.merge(products[["product_id", "category", "list_price"]], on="product_id")
    items = items.sort_values(["order_id"], kind="stable", ignore_index=True)

    items["quantity"] = rng.choice([1, 2, 3], size=len(items), p=[0.8, 0.15, 0.05])

    social = items["channel"].eq("social_ads").to_numpy()
    has_discount = rng.random(len(items)) < np.where(social, 0.85, 0.25)
    rate = np.where(social, rng.uniform(0.15, 0.35, len(items)), rng.uniform(0.10, 0.30, len(items)))
    line_gross = items["list_price"] * items["quantity"]
    items["discount_amount"] = np.round(np.where(has_discount, line_gross * rate, 0.0), 2)

    items.insert(0, "order_item_id", np.arange(1, len(items) + 1))
    return items


def add_order_money(rng, orders, items):
    line_net = items["list_price"] * items["quantity"] - items["discount_amount"]
    order_net = line_net.groupby(items["order_id"]).sum()
    net = orders["order_id"].map(order_net).to_numpy()

    has_coupon = rng.random(len(orders)) < 0.15
    coupon = np.minimum(rng.choice([5.0, 10.0, 15.0], len(orders)), np.round(net * 0.3, 2))
    orders["coupon_amount"] = np.where(has_coupon, coupon, 0.0)
    orders["shipping_fee"] = np.where(net - orders["coupon_amount"] >= FREE_SHIPPING_FROM, 0.0, SHIPPING_FEE)
    return orders


def make_returns(rng, orders, items):
    df = items.merge(orders[["order_id", "order_ts", "status", "coupon_amount"]], on="order_id")
    df["line_net"] = df["list_price"] * df["quantity"] - df["discount_amount"]
    order_net = df.groupby("order_id")["line_net"].transform("sum")
    df["coupon_alloc"] = df["coupon_amount"] * df["line_net"] / order_net
    df["unit_net"] = (df["line_net"] - df["coupon_alloc"]) / df["quantity"]

    other_mult = (1 - CHANNELS.loc["social_ads", "weight"] * SOCIAL_RETURN_MULT) / (
        1 - CHANNELS.loc["social_ads", "weight"]
    )
    mult = np.where(df["channel"].eq("social_ads"), SOCIAL_RETURN_MULT, other_mult)
    p = CATEGORIES.loc[df["category"], "return_rate"].to_numpy() * mult
    returned = (rng.random(len(df)) < p) & df["status"].eq("delivered").to_numpy()
    r = df[returned].copy()

    partial = (r["quantity"] > 1) & (rng.random(len(r)) < 0.5)
    partial_qty = np.floor(rng.random(len(r)) * (r["quantity"] - 1)).astype(int) + 1
    first_qty = np.where(partial, partial_qty, r["quantity"])
    r["returned_qty"] = first_qty
    r["days"] = np.round(rng.triangular(3, 10, 60, len(r))).astype(int)

    second = r[partial & (rng.random(len(r)) < 0.3)].copy()
    second["returned_qty"] = second["quantity"] - second["returned_qty"]
    second["days"] = np.minimum(second["days"] + rng.integers(3, 15, len(second)), 60)

    ret = pd.concat([r, second], ignore_index=True)
    ret["return_ts"] = ret["order_ts"].dt.normalize() + pd.to_timedelta(ret["days"], unit="D") + pd.to_timedelta(
        rng.integers(9 * 3600, 20 * 3600, len(ret)), unit="s"
    )
    ret = ret[ret["return_ts"] < SNAPSHOT]

    damaged_p = CATEGORIES.loc[ret["category"], "damaged_share"].to_numpy()
    ret["condition"] = np.where(rng.random(len(ret)) < damaged_p, "damaged", "restocked")
    ret["refund_amount"] = np.round(ret["unit_net"] * ret["returned_qty"], 2)
    ret["return_shipping_cost"] = RETURN_SHIPPING
    ret = ret.sort_values("return_ts", ignore_index=True)
    ret.insert(0, "return_id", np.arange(1, len(ret) + 1))
    return ret[
        ["return_id", "order_item_id", "return_ts", "returned_qty", "condition", "refund_amount", "return_shipping_cost"]
    ]


def make_customers(rng, orders):
    first = orders.groupby("customer_id")["order_ts"].min()
    ids = np.arange(1, N_CUSTOMERS + 1)
    random_signup = START + pd.to_timedelta(rng.integers(0, (END - START).days, N_CUSTOMERS), unit="D")
    signup = pd.Series(random_signup, index=ids)
    lag = pd.to_timedelta(rng.integers(0, 31, len(first)), unit="D")
    signup.loc[first.index] = (first.dt.normalize() - lag).to_numpy()
    regions = ["Moscow", "Saint Petersburg", "Kazan", "Novosibirsk", "Yekaterinburg", "Other"]
    return pd.DataFrame(
        {
            "customer_id": ids,
            "signup_date": signup.dt.strftime("%Y-%m-%d").to_numpy(),
            "region": rng.choice(regions, N_CUSTOMERS, p=[0.3, 0.15, 0.08, 0.07, 0.07, 0.33]),
        }
    )


def dirty_status(rng, status):
    variants = {
        "delivered": ["Delivered", " delivered", "DELIVERED ", "delivered "],
        "cancelled": ["Cancelled", " cancelled", "CANCELLED "],
    }
    out = status.astype(object).copy()
    mask = rng.random(len(out)) < 0.1
    out[mask] = [rng.choice(variants[s]) for s in out[mask]]
    return out


def add_duplicates(rng, df, share=0.01):
    dup = df.sample(frac=share, random_state=int(rng.integers(1_000_000)))
    return pd.concat([df, dup]).sample(frac=1, random_state=int(rng.integers(1_000_000))).reset_index(drop=True)


def summary(customers, products, orders, items, returns):
    print("Rows")
    for name, df in [("customers", customers), ("products", products), ("channels", CHANNELS),
                     ("orders", orders), ("order_items", items), ("returns", returns)]:
        print(f"  {name:<12} {len(df):>8}")
    print(f"Duplicates: orders {orders.duplicated().sum()}, order_items {items.duplicated().sum()}")

    o = orders.drop_duplicates().copy()
    o["status"] = o["status"].str.strip().str.lower()
    print(f"Cancelled orders: {o['status'].eq('cancelled').mean():.1%}")

    it = items.drop_duplicates().merge(o[["order_id", "status", "order_ts"]], on="order_id")
    it = it[it["status"] == "delivered"]
    it["returned"] = it["order_item_id"].isin(returns["order_item_id"])
    overall = it["returned"].mean()
    print(f"Returned items, overall: {overall:.1%}")
    print("Returned items by category:")
    print(it.groupby("category")["returned"].mean().map("{:.1%}".format).to_string())
    by_channel = it.groupby("channel")["returned"].mean()
    print("Returned items by channel:")
    print(by_channel.map("{:.1%}".format).to_string())
    print(f"social_ads vs overall: {by_channel['social_ads'] / overall:.2f}x")

    r = returns.merge(it[["order_item_id", "order_ts"]], on="order_item_id")
    other_month = (r["return_ts"].dt.to_period("M") != r["order_ts"].dt.to_period("M")).mean()
    print(f"Returns in a later month than the order: {other_month:.1%}")

    gross = it["list_price"] * it["quantity"]
    no_cost = it["product_id"].isin(products.loc[products["unit_cost"].isna(), "product_id"])
    print(f"Revenue of products without cost: {gross[no_cost].sum() / gross.sum():.1%}")


def main():
    rng = np.random.default_rng(SEED)
    products = make_products(rng)
    orders = make_orders(rng)
    items = make_items(rng, orders, products)
    orders = add_order_money(rng, orders, items)
    returns = make_returns(rng, orders, items)
    customers = make_customers(rng, orders)

    orders_raw = orders.copy()
    orders_raw["status"] = dirty_status(rng, orders_raw["status"].to_numpy())
    orders_raw = add_duplicates(rng, orders_raw)
    items_raw = add_duplicates(rng, items[["order_item_id", "order_id", "product_id", "quantity", "list_price", "discount_amount"]])

    check_items = items_raw.merge(products[["product_id", "category"]], on="product_id").merge(
        orders[["order_id", "channel"]], on="order_id"
    )
    summary(customers, products, orders_raw, check_items, returns)

    OUT.mkdir(parents=True, exist_ok=True)
    ts = "%Y-%m-%d %H:%M:%S"
    orders_raw["order_ts"] = orders_raw["order_ts"].dt.strftime(ts)
    returns_out = returns.assign(return_ts=returns["return_ts"].dt.strftime(ts))
    customers.to_csv(OUT / "customers.csv", index=False)
    products.to_csv(OUT / "products.csv", index=False)
    CHANNELS[["fee_pct"]].reset_index().to_csv(OUT / "channels.csv", index=False)
    orders_raw.to_csv(OUT / "orders.csv", index=False)
    items_raw.to_csv(OUT / "order_items.csv", index=False)
    returns_out.to_csv(OUT / "returns.csv", index=False)
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
