select *
from {{ ref('fct_returns') }}
where abs(return_amount - refund_amount) > 0.01
