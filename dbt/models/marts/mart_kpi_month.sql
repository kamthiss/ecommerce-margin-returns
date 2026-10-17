select
    order_month,
    count(*) filter (where not is_cancelled) as orders,
    count(*) filter (where is_cancelled) as cancelled_orders,
    sum(net_sales) filter (where not is_cancelled) as net_sales,
    sum(net_sales) filter (where not is_cancelled)
        / nullif(count(*) filter (where not is_cancelled), 0) as avg_order_value,
    sum(shipping_fee) filter (where not is_cancelled) as shipping_fee
from {{ ref('fct_orders') }}
group by order_month
