with by_order as (
    select sum(returns_amount) as returns_amount
    from {{ ref('mart_category_month') }}
),

by_return as (
    select sum(returns_amount) as returns_amount
    from {{ ref('mart_returns_by_return_month') }}
)

select o.returns_amount as by_order_month, r.returns_amount as by_return_month
from by_order o, by_return r
where abs(o.returns_amount - r.returns_amount) > 0.01
