with src as (
    select distinct * from {{ source('raw', 'returns') }}
)

select
    return_id::integer as return_id,
    order_item_id::integer as order_item_id,
    return_ts::timestamp as return_ts,
    returned_qty::integer as returned_qty,
    condition,
    refund_amount::numeric as refund_amount,
    return_shipping_cost::numeric as return_shipping_cost
from src
