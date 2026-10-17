with src as (
    select distinct * from {{ source('raw', 'channels') }}
)

select
    channel,
    fee_pct::numeric as fee_pct
from src
