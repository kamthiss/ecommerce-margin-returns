with src as (
    select distinct * from {{ source('raw', 'products') }}
)

select
    product_id::integer as product_id,
    sku,
    category,
    list_price::numeric as list_price,
    nullif(trim(unit_cost), '')::numeric as unit_cost,
    nullif(trim(unit_cost), '') is not null as has_cost
from src
