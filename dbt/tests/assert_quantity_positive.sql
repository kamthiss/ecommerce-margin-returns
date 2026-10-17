select *
from {{ ref('stg_order_items') }}
where quantity < 1
