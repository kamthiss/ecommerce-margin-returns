select
    product_id,
    sku,
    category,
    list_price,
    unit_cost,
    has_cost
from {{ ref('stg_products') }}
