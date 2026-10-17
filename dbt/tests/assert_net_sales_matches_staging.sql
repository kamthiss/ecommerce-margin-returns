with expected as (
    select
        (select sum(i.list_price * i.quantity - i.discount_amount)
         from {{ ref('stg_order_items') }} i
         join {{ ref('stg_orders') }} o using (order_id)
         where o.status <> 'cancelled')
        - (select sum(coupon_amount)
           from {{ ref('stg_orders') }}
           where status <> 'cancelled') as net_sales
),

actual as (
    select sum(net_sales) as net_sales
    from {{ ref('fct_order_lines') }}
    where not is_cancelled
)

select e.net_sales as expected, a.net_sales as actual
from expected e, actual a
where abs(e.net_sales - a.net_sales) > 0.01
