import pandas as pd
from dateutil import parser

def _try_parse_dt(x):
    try:
        return parser.parse(str(x))
    except Exception:
        return x

def clean_dataframe_basic(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    # Trim string columns
    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].astype(str).str.strip()
    # Parse common datetime columns
    for key in ["created_at", "date", "timestamp", "posted_at"]:
        if key in df.columns:
            df[key] = df[key].map(_try_parse_dt)
    # Numeric coercions
    for key in ["likes", "comments", "retweets", "replies", "views", "shares"]:
        if key in df.columns:
            df[key] = pd.to_numeric(df[key], errors='coerce')
    # Deduplicate and sort by date if present
    df = df.drop_duplicates()
    for key in ["created_at", "date", "timestamp", "posted_at"]:
        if key in df.columns:
            try:
                df = df.sort_values(by=key, ascending=True)
                break
            except Exception:
                pass
    return df.reset_index(drop=True)