with sales as (
    select
        order_month,
        category,
        sum(net_sales) as net_sales,
        sum(net_sales) filter (where has_cost) as costed_net_sales,
        sum(cost) as cost,
        sum(commission) as commission,
        sum(commission) filter (where has_cost) as costed_commission
    from {{ ref('fct_order_lines') }}
    where not is_cancelled
    group by order_month, category
),

returns as (
    select
        order_month,
        category,
        sum(return_amount) as returns_amount,
        sum(return_amount) filter (where has_cost) as costed_returns_amount,
        sum(cost_reversal) as cost_reversal,
        sum(return_shipping_cost) as return_shipping,
        sum(return_shipping_cost) filter (where has_cost) as costed_return_shipping
    from {{ ref('fct_returns') }}
    group by order_month, category
),

joined as (
    select
        s.order_month,
        s.category,
        (s.order_month + interval '1 month - 1 day')::date + 60 <= date '2026-01-15' as is_mature,
        s.net_sales,
        coalesce(s.costed_net_sales, 0) as costed_net_sales,
        coalesce(r.returns_amount, 0) as returns_amount,
        coalesce(r.costed_returns_amount, 0) as costed_returns_amount,
        coalesce(s.cost, 0) as cost,
        coalesce(r.cost_reversal, 0) as cost_reversal,
        coalesce(r.return_shipping, 0) as return_shipping,
        coalesce(r.costed_return_shipping, 0) as costed_return_shipping,
        s.commission,
        coalesce(s.costed_commission, 0) as costed_commission
    from sales s
    left join returns r using (order_month, category)
),

margin as (
    select
        *,
        costed_net_sales - cost - costed_commission as margin_before_returns,
        costed_net_sales - costed_returns_amount - cost + cost_reversal
            - costed_return_shipping - costed_commission as margin_after_returns
    from joined
)

select
    *,
    margin_before_returns / nullif(costed_net_sales, 0) as margin_pct_before_returns,
    margin_after_returns / nullif(costed_net_sales - costed_returns_amount, 0) as margin_pct_after_returns,
    costed_net_sales / nullif(net_sales, 0) as cost_coverage
from margin
