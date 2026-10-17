with lines as (
    select sum(net_sales) as net_sales
    from {{ ref('fct_order_lines') }}
    where not is_cancelled
),

marts as (
    select 'mart_category_month' as mart, sum(net_sales) as net_sales
    from {{ ref('mart_category_month') }}
    union all
    select 'mart_channel_month', sum(net_sales)
    from {{ ref('mart_channel_month') }}
)

select m.mart, m.net_sales, l.net_sales as lines_net_sales
from marts m, lines l
where abs(m.net_sales - l.net_sales) > 0.01
