with orders as (
    select
        customer_id,
        min(order_ts)::date as first_order_date,
        count(*) as order_count
    from {{ ref('stg_orders') }}
    where status <> 'cancelled'
    group by customer_id
)

select
    c.customer_id,
    c.signup_date,
    c.region,
    o.first_order_date,
    coalesce(o.order_count, 0) as order_count,
    coalesce(o.order_count, 0) >= 2 as is_repeat
from {{ ref('stg_customers') }} c
left join orders o using (customer_id)
