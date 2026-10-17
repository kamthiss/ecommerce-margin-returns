with lines as (
    select
        order_month,
        category,
        channel,
        sum(net_sales) as net_sales,
        sum(cost) as cost,
        sum(commission) as commission
    from {{ ref('fct_order_lines') }}
    where not is_cancelled
    group by order_month, category, channel
)

select l.*, m.net_sales as mart_net_sales, m.cost as mart_cost, m.commission as mart_commission
from lines l
full join {{ ref('mart_category_channel_month') }} m using (order_month, category, channel)
where m.order_month is null
    or l.order_month is null
    or abs(l.net_sales - m.net_sales) > 0.01
    or abs(coalesce(l.cost, 0) - m.cost) > 0.01
    or abs(l.commission - m.commission) > 0.01
