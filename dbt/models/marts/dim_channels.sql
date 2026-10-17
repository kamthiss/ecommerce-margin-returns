select
    channel,
    fee_pct
from {{ ref('stg_channels') }}
