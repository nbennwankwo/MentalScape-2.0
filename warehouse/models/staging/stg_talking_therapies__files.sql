-- The manifest of collected NHS Talking Therapies files, typed. One row per stored file and version.

select
    asset_name,
    kind,
    reporting_month,
    version,
    cast(revision as integer) as revision,
    source_url,
    page_url,
    card_title,
    original_filename,
    cast(original_bytes as bigint) as original_bytes,
    original_sha256,
    cast(stored_bytes as bigint) as stored_bytes,
    stored_sha256,
    downloaded_at_utc,
    is_preferred = 'True' as is_preferred
from {{ source('raw', 'talking_therapies_files') }}
