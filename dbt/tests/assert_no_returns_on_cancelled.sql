select r.*
from {{ ref('stg_returns') }} r
join {{ ref('stg_order_items') }} i using (order_item_id)
join {{ ref('stg_orders') }} o using (order_id)
where o.status = 'cancelled'
