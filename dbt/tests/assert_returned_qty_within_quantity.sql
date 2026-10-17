select
    i.order_item_id,
    i.quantity,
    sum(r.returned_qty) as returned_qty
from {{ ref('stg_returns') }} r
join {{ ref('stg_order_items') }} i using (order_item_id)
group by i.order_item_id, i.quantity
having sum(r.returned_qty) > i.quantity
