with src as (
    select distinct * from {{ source('raw', 'customers') }}
)

select
    customer_id::integer as customer_id,
    signup_date::date as signup_date,
    region
from src
