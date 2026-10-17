with lines as (
    select
        i.order_item_id,
        i.order_id,
        i.product_id,
        o.channel,
        p.category,
        o.status = 'cancelled' as is_cancelled,
        o.order_ts::date as order_date,
        date_trunc('month', o.order_ts)::date as order_month,
        i.quantity,
        i.list_price * i.quantity as gross_revenue,
        i.discount_amount,
        o.coupon_amount
            * (i.list_price * i.quantity - i.discount_amount)
            / sum(i.list_price * i.quantity - i.discount_amount) over (partition by i.order_id)
            as coupon_share,
        p.unit_cost,
        p.has_cost,
        c.fee_pct
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_orders') }} o using (order_id)
    join {{ ref('stg_products') }} p using (product_id)
    join {{ ref('stg_channels') }} c on c.channel = o.channel
),

net as (
    select
        *,
        gross_revenue - discount_amount - coupon_share as net_sales
    from lines
)

select
    order_item_id,
    order_id,
    product_id,
    category,
    channel,
    is_cancelled,
    order_date,
    order_month,
    quantity,
    gross_revenue,
    discount_amount,
    coupon_share,
    net_sales,
    net_sales / quantity as net_unit_price,
    unit_cost * quantity as cost,
    has_cost,
    net_sales * fee_pct / 100 as commission
from net
