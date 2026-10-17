select
    r.return_id,
    r.order_item_id,
    l.order_id,
    l.category,
    l.channel,
    r.return_ts::date as return_date,
    date_trunc('month', r.return_ts)::date as return_month,
    l.order_month,
    r.condition,
    r.returned_qty,
    l.net_unit_price * r.returned_qty as return_amount,
    r.refund_amount,
    l.has_cost,
    case
        when r.condition = 'restocked' then l.cost / l.quantity * r.returned_qty
        else 0
    end as cost_reversal,
    r.return_shipping_cost
from {{ ref('stg_returns') }} r
join {{ ref('fct_order_lines') }} l using (order_item_id)
