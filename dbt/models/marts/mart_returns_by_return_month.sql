select
    return_month,
    category,
    channel,
    count(*) as returns_count,
    sum(returned_qty) as returned_qty,
    sum(return_amount) as returns_amount,
    sum(refund_amount) as refund_amount,
    sum(cost_reversal) as cost_reversal,
    sum(return_shipping_cost) as return_shipping
from {{ ref('fct_returns') }}
group by return_month, category, channel
