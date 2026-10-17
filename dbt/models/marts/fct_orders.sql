with lines as (
    select
        order_id,
        sum(net_sales) as net_sales
    from {{ ref('fct_order_lines') }}
    group by order_id
)

select
    o.order_id,
    o.customer_id,
    o.channel,
    o.status,
    o.status = 'cancelled' as is_cancelled,
    o.order_ts::date as order_date,
    date_trunc('month', o.order_ts)::date as order_month,
    o.coupon_amount,
    o.shipping_fee,
    l.net_sales,
    case
        when o.status <> 'cancelled' then
            row_number() over (
                partition by o.customer_id, o.status = 'cancelled'
                order by o.order_ts, o.order_id
            )
    end as customer_order_seq
from {{ ref('stg_orders') }} o
join lines l using (order_id)
