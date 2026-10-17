select
    o.order_id,
    o.coupon_amount,
    sum(l.coupon_share) as coupon_share
from {{ ref('fct_orders') }} o
join {{ ref('fct_order_lines') }} l using (order_id)
group by o.order_id, o.coupon_amount
having abs(sum(l.coupon_share) - o.coupon_amount) > 0.01
