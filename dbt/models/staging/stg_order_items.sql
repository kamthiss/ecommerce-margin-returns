with src as (
    select distinct * from {{ source('raw', 'order_items') }}
)

select
    order_item_id::integer as order_item_id,
    order_id::integer as order_id,
    product_id::integer as product_id,
    quantity::integer as quantity,
    list_price::numeric as list_price,
    discount_amount::numeric as discount_amount
from src
