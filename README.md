# Spencer's Rewards — Intelligence Dashboard (Streamlit)

A full-featured loyalty analytics dashboard built with Python & Streamlit,
converted from the original HTML/JS single-page app.

## Features
- **Overview** — KPIs, insights, enrollment trend, shopper behaviour charts
- **Return Rate** — 9-month window analysis, region/cluster breakdown, store leaderboards
- **Customers** — Incremental sales, NOB analysis, new vs existing comparison
- **Stores** — Revenue rankings, format analysis, basket value
- **Cashback & Sales** — Redemption rates, city-level cashback analysis
- **Geography** — Region/city revenue and customer distribution
- **Lost Sales** — Not-shopped customers with past AMS, win-back potential
- **Data Explorer** — Paginated, filterable table with CSV download
- **AI Analyst** — Claude-powered chat analyst with full data context

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run locally
```bash
streamlit run app.py
```

### 3. Deploy to Streamlit Cloud
1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path** to `app.py`
5. Click **Deploy**

No additional secrets needed — the Anthropic API key is entered at runtime
inside the AI Analyst tab and is never stored server-side.

## CSV Format
Upload a CSV with these columns (extra columns are ignored):
| Column | Description |
|--------|-------------|
| `store_code` | Unique store identifier |
| `store_name` | Store display name |
| `customer_name` | Customer name |
| `region_name` | Regional grouping |
| `city_name` | City |
| `cluster_name` | Store cluster |
| `format_type` | Store format (Hypermarket, etc.) |
| `shopper_behaviour` | `Shopped` or `Not Shopped` |
| `customer_type` | `New Customer` or `Existing Customer` |
| `enroll_month` | e.g. `Jan-25` |
| `current_bill_value` | Revenue this month |
| `cashback_earned_current_month` | Cashback earned |
| `redemed_amount_current_month` | Cashback redeemed |
| `incremental_sales` | Current − baseline |
| `current_nob` | Number of bills this month |
| `past_six_months_average_nob` | Avg bills over past 6 months |
| `past_six_months_average_ams` | Avg monthly spend over past 6 months |
| `current_asp` | Average selling price |
| `current_ams_slab` | AMS slab label |
| `past_six_months_ams_slab` | Past AMS slab label |
| `bill_slab` | Bill value slab |
