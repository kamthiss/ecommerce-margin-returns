with src as (
    select distinct * from {{ source('raw', 'orders') }}
)

select
    order_id::integer as order_id,
    customer_id::integer as customer_id,
    channel,
    order_ts::timestamp as order_ts,
    lower(trim(status)) as status,
    coupon_amount::numeric as coupon_amount,
    shipping_fee::numeric as shipping_fee
from src
