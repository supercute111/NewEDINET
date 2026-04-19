# =========================
# EDINET Finance Terminal
# Yahoo Finance-style with EDINET financials
# =========================
import os, re, time, zipfile, io
from datetime import date, timedelta

import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ.pop("CURL_CA_BUNDLE", None)

import pandas as pd
import requests
import streamlit as st
from pykakasi import kakasi
import yfinance as yf
import altair as alt

try:
    from rapidfuzz import process, fuzz
    HAVE_RF = True
except ImportError:
    HAVE_RF = False
    from difflib import SequenceMatcher
    def _difflib_extract(query, universe, limit=300):
        q = (query or "").casefold()
        scored = [(idx, SequenceMatcher(None, q, (t or "").casefold()).ratio()) for idx, t in universe.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [("", int(100*s), idx) for idx, s in scored[:limit]]

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from lxml import etree
    HAVE_LXML = True
except ImportError:
    HAVE_LXML = False

API_BASE = "https://api.edinet-fsa.go.jp/api/v2"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="EDINET Finance Terminal", layout="wide", initial_sidebar_state="collapsed")

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0a0a0f;
    color: #e8e8f0;
}
.main { background-color: #0a0a0f; }
.block-container { padding: 1.5rem 2rem 3rem 2rem; max-width: 1400px; }

/* Header */
.terminal-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: #4a9eff;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    border-bottom: 1px solid #1e1e2e;
    padding-bottom: 0.75rem;
    margin-bottom: 1.5rem;
}
.company-name {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.company-sub {
    font-size: 0.85rem;
    color: #6b6b8a;
    font-family: 'IBM Plex Mono', monospace;
    margin-top: 0.2rem;
}
.price-big {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 2.8rem;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: -0.02em;
}
.price-up { color: #00d395; }
.price-down { color: #ff4d6d; }
.price-change {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1rem;
    margin-top: 0.2rem;
}

/* Stat cards */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: #1e1e2e;
    border: 1px solid #1e1e2e;
    border-radius: 8px;
    overflow: hidden;
    margin: 1rem 0;
}
.stat-card {
    background: #0f0f1a;
    padding: 1rem 1.2rem;
}
.stat-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    color: #4a4a6a;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.3rem;
}
.stat-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1rem;
    font-weight: 600;
    color: #e8e8f0;
}

/* Section headers */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    color: #4a9eff;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    border-left: 2px solid #4a9eff;
    padding-left: 0.6rem;
    margin: 1.5rem 0 1rem 0;
}

/* Financial table */
.fin-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
}
.fin-table th {
    text-align: right;
    padding: 0.5rem 0.8rem;
    color: #4a4a6a;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border-bottom: 1px solid #1e1e2e;
    font-weight: 400;
}
.fin-table th:first-child { text-align: left; }
.fin-table td {
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid #0f0f1a;
    text-align: right;
    color: #c8c8d8;
}
.fin-table td:first-child {
    text-align: left;
    color: #8888aa;
    padding-left: 0;
}
.fin-table tr:hover td { background: #0f0f1a; }
.fin-table .row-header td {
    color: #e8e8f0;
    font-weight: 600;
    background: #0f0f1a;
    padding-top: 0.8rem;
}
.fin-table .positive { color: #00d395; }
.fin-table .negative { color: #ff4d6d; }

/* Tabs override */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid #1e1e2e;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #4a4a6a;
    background: transparent;
    border: none;
    padding: 0.6rem 1.2rem;
}
.stTabs [aria-selected="true"] {
    color: #4a9eff !important;
    border-bottom: 2px solid #4a9eff !important;
    background: transparent !important;
}

/* Search */
.stTextInput input {
    background: #0f0f1a !important;
    border: 1px solid #1e1e2e !important;
    color: #e8e8f0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.9rem !important;
    border-radius: 4px !important;
}
.stTextInput input:focus {
    border-color: #4a9eff !important;
    box-shadow: 0 0 0 1px #4a9eff22 !important;
}

/* Buttons */
.stButton button {
    background: #0f0f1a !important;
    border: 1px solid #1e1e2e !important;
    color: #4a9eff !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.05em !important;
    border-radius: 4px !important;
    padding: 0.3rem 0.8rem !important;
}
.stButton button:hover {
    border-color: #4a9eff !important;
    background: #0a1628 !important;
}

/* Metrics */
[data-testid="metric-container"] {
    background: #0f0f1a;
    border: 1px solid #1e1e2e;
    border-radius: 6px;
    padding: 0.8rem 1rem;
}
[data-testid="metric-container"] label {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.65rem !important;
    color: #4a4a6a !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.2rem !important;
    color: #e8e8f0 !important;
}

/* Radio / selectbox */
.stRadio label, .stSelectbox label {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.72rem !important;
    color: #4a4a6a !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.stRadio [data-baseweb="radio"] span { border-color: #1e1e2e !important; }
.stRadio [aria-checked="true"] span { border-color: #4a9eff !important; background: #4a9eff !important; }

/* DataEditor */
[data-testid="stDataFrame"] { border: 1px solid #1e1e2e !important; border-radius: 6px; overflow: hidden; }

/* Divider */
hr { border-color: #1e1e2e !important; }

/* Info / warning */
.stAlert { background: #0f0f1a !important; border-color: #1e1e2e !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.8rem !important; }

/* Ticker pill */
.ticker-pill {
    display: inline-block;
    background: #0f1e3a;
    border: 1px solid #4a9eff44;
    color: #4a9eff;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    padding: 0.15rem 0.6rem;
    border-radius: 3px;
    letter-spacing: 0.05em;
    margin-left: 0.5rem;
    vertical-align: middle;
}
.edinet-pill {
    display: inline-block;
    background: #1a0f2e;
    border: 1px solid #7c3aed44;
    color: #a78bfa;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    padding: 0.15rem 0.6rem;
    border-radius: 3px;
    letter-spacing: 0.05em;
    margin-left: 0.4rem;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)

# ── API key ───────────────────────────────────────────────────────────────────
def get_api_key():
    key = os.getenv("EDINET_API_KEY")
    try:
        key = key or st.secrets.get("EDINET_API_KEY")
    except Exception:
        pass
    return key

API_KEY = get_api_key()

# ── Codebook ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_codebook(path="edinet_codes.csv"):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        last_err, df = None, None
        for enc in ("cp932", "shift_jis", "utf-8-sig", "utf-16"):
            try:
                df = pd.read_csv(path, dtype=str, encoding=enc, header=1)
                break
            except UnicodeDecodeError as e:
                last_err = e
            except Exception:
                try:
                    tmp = pd.read_csv(path, dtype=str, encoding=enc, header=0)
                    if "ダウンロード実行日" in tmp.columns:
                        df = pd.read_csv(path, dtype=str, encoding=enc, header=1)
                    else:
                        df = tmp
                    break
                except Exception as e2:
                    last_err = e2
        if df is None:
            raise last_err
    df.columns = [c.strip() for c in df.columns]
    for c in ["ＥＤＩＮＥＴコード","提出者名","証券コード","提出者名（カナ）","提出者名（ヨミ）"]:
        if c not in df.columns:
            df[c] = ""
    def norm_sec(s):
        s = re.sub(r"\D","", (s or "").strip())
        return s[:-1] if len(s)==5 and s.endswith("0") else s
    df["証券コード"] = df["証券コード"].fillna("").astype(str)
    df["証券コード4"] = df["証券コード"].apply(norm_sec)
    df["提出者名"] = df["提出者名"].fillna("").astype(str)
    kks = kakasi(); kks.setMode("H","a"); kks.setMode("K","a"); kks.setMode("J","a")
    conv = kks.getConverter()
    df["romaji"] = df["提出者名"].apply(lambda s: conv.do(s) if s else s)
    code_for_label = df["証券コード4"].where(df["証券コード4"] != "", df["ＥＤＩＮＥＴコード"])
    df["label"] = (code_for_label + " " + df["提出者名"]).str.strip()
    return df.drop_duplicates(subset=["ＥＤＩＮＥＴコード"]).reset_index(drop=True)

try:
    codes = load_codebook("edinet_codes.csv")
except FileNotFoundError:
    st.error("Put **edinet_codes.csv** in the repo root.")
    st.stop()

HAS_SECURITIES = codes["証券コード4"].str.contains(r"\d", regex=True, na=False).any()

# ── Fuzzy search ──────────────────────────────────────────────────────────────
def fuzzy_suggest(df, query, limit=15):
    q = (query or "").strip()
    if not q:
        return df.head(limit)
    starts = df[df["証券コード4"].str.startswith(q, na=False)] if HAS_SECURITIES else pd.DataFrame()
    def row_text(row):
        parts = [row["提出者名"], row["romaji"], row["ＥＤＩＮＥＴコード"]]
        if HAS_SECURITIES: parts.append(row["証券コード4"])
        return " ".join(p for p in parts if p)
    universe = {i: row_text(row) for i, row in df.iterrows()}
    if HAVE_RF:
        matches = process.extract(q, universe, scorer=fuzz.WRatio, limit=300)
    else:
        matches = _difflib_extract(q, universe, limit=300)
    idx = [k for (_,score,k) in matches if score >= 60][:limit]
    return pd.concat([starts, df.loc[idx]]).drop_duplicates(subset=["ＥＤＩＮＥＴコード"]).head(limit)

# ── EDINET API helpers ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_list_for_date(date_str, api_key):
    r = requests.get(f"{API_BASE}/documents.json",
                     params={"date": date_str, "type": "2", "Subscription-Key": api_key},
                     headers={"X-API-KEY": api_key}, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=24*3600, show_spinner="Downloading document…")
def fetch_doc_bytes(doc_id, kind, api_key):
    type_param = "2" if kind.upper() == "PDF" else "1"
    r = requests.get(f"{API_BASE}/documents/{doc_id}",
                     params={"type": type_param, "Subscription-Key": api_key},
                     headers={"X-API-KEY": api_key}, timeout=120)
    r.raise_for_status()
    return r.content

@st.cache_data(show_spinner=False)
def list_filings(edicode, sec4, start, end, api_key, delay=0.25):
    rows, d = [], start
    while d <= end:
        try:
            js = fetch_list_for_date(d.strftime("%Y-%m-%d"), api_key)
            for item in js.get("results", []):
                cond = item.get("edinetCode") == edicode
                if HAS_SECURITIES and sec4:
                    cond = cond or str(item.get("securitiesCode","")) == str(sec4)
                if cond:
                    rows.append({"date": js.get("date"), "docID": item.get("docID"),
                                 "filerName": item.get("filerName"),
                                 "title": item.get("docDescription") or item.get("documentName"),
                                 "ordinanceCode": item.get("ordinanceCode"),
                                 "formCode": item.get("formCode")})
        except Exception as e:
            rows.append({"date": d.strftime("%Y-%m-%d"), "docID": "", "filerName": "",
                         "title": f"ERROR: {e}", "ordinanceCode": "", "formCode": ""})
        d += timedelta(days=1)
        time.sleep(delay)
    return pd.DataFrame(rows)

# ── XBRL parser ───────────────────────────────────────────────────────────────
XBRL_NS = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "jppfs_cor": "http://xbrl.ifrs.or.jp/taxonomy/2023-03-31/jppfs_cor",
}

# Mappings: (label, list of possible XBRL tag suffixes)
PL_ITEMS = [
    ("Net Sales / Revenue",             ["NetSales","Revenue","Revenues"]),
    ("Cost of Sales",                   ["CostOfSales","CostOfRevenue"]),
    ("Gross Profit",                    ["GrossProfit"]),
    ("SG&A Expenses",                   ["SellingGeneralAndAdministrativeExpenses","SGAExpenses"]),
    ("Operating Income",                ["OperatingIncome","OperatingProfit","ProfitLoss"]),
    ("EBITDA (approx)",                 ["__EBITDA__"]),
    ("Non-Operating Income",            ["NonOperatingIncome"]),
    ("Non-Operating Expenses",          ["NonOperatingExpenses"]),
    ("Ordinary Income",                 ["OrdinaryIncome","OrdinaryProfit"]),
    ("Income Before Tax",               ["IncomeBeforeTax","ProfitLossBeforeTax","IncomeLossBeforeIncomeTaxes"]),
    ("Income Tax",                      ["IncomeTaxes","IncomeTaxExpense"]),
    ("Net Income",                      ["NetIncome","ProfitLoss","NetIncomeLoss","NetProfitLoss"]),
    ("EPS (Basic)",                     ["BasicEarningsLossPerShare","EarningsPerShare"]),
]
BS_ITEMS = [
    ("── ASSETS ──",                    []),
    ("Cash & Equivalents",              ["CashAndCashEquivalents","CashAndDeposits"]),
    ("Accounts Receivable",             ["NotesAndAccountsReceivableTrade","AccountsReceivableTrade"]),
    ("Inventories",                     ["Inventories"]),
    ("Other Current Assets",            ["OtherCurrentAssets"]),
    ("Total Current Assets",            ["TotalCurrentAssets","CurrentAssets"]),
    ("PP&E (net)",                      ["PropertyPlantAndEquipmentNet","PropertyPlantAndEquipment"]),
    ("Intangible Assets",               ["IntangibleAssets"]),
    ("Investments",                     ["InvestmentSecurities","Investments"]),
    ("Total Non-Current Assets",        ["TotalNoncurrentAssets","NoncurrentAssets"]),
    ("Total Assets",                    ["TotalAssets","Assets"]),
    ("── LIABILITIES ──",               []),
    ("Accounts Payable",                ["AccountsPayableTrade","NotesAndAccountsPayableTrade"]),
    ("Short-term Debt",                 ["ShortTermLoansPayable","ShortTermBorrowings"]),
    ("Total Current Liabilities",       ["TotalCurrentLiabilities","CurrentLiabilities"]),
    ("Long-term Debt",                  ["LongTermLoansPayable","LongTermDebt","LongTermBorrowings"]),
    ("Total Non-Current Liabilities",   ["TotalNoncurrentLiabilities","NoncurrentLiabilities"]),
    ("Total Liabilities",               ["TotalLiabilities","Liabilities"]),
    ("── EQUITY ──",                    []),
    ("Common Stock",                    ["CapitalStock","CommonStock"]),
    ("Retained Earnings",               ["RetainedEarnings"]),
    ("Total Equity",                    ["TotalEquity","NetAssets","Equity"]),
]
CF_ITEMS = [
    ("Operating Cash Flow",             ["NetCashProvidedByUsedInOperatingActivities","CashFlowsFromOperatingActivities"]),
    ("Capital Expenditures",            ["PurchaseOfPropertyPlantAndEquipment","CapitalExpenditures"]),
    ("Free Cash Flow (approx)",         ["__FCF__"]),
    ("Investing Cash Flow",             ["NetCashProvidedByUsedInInvestingActivities","CashFlowsFromInvestingActivities"]),
    ("Financing Cash Flow",             ["NetCashProvidedByUsedInFinancingActivities","CashFlowsFromFinancingActivities"]),
    ("Net Change in Cash",              ["NetIncreaseDecreaseInCashAndCashEquivalents","NetChangeInCashAndCashEquivalents"]),
]

def parse_xbrl_zip(zip_bytes):
    """Extract financial data from XBRL ZIP. Returns dict of {tag: value}"""
    data = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xbrl_files = [n for n in zf.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
            if not xbrl_files:
                xbrl_files = [n for n in zf.namelist() if n.endswith(".xbrl")]
            if not xbrl_files:
                return data
            # pick the main instance document (usually largest)
            xbrl_files.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
            with zf.open(xbrl_files[0]) as f:
                content = f.read()
            if HAVE_LXML:
                root = etree.fromstring(content)
            else:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(content)
            for elem in root.iter():
                tag = elem.tag
                if "}" in tag:
                    tag = tag.split("}")[1]
                if elem.text and elem.text.strip():
                    try:
                        val = float(elem.text.strip().replace(",",""))
                        # store latest (contextRef containing CurrentYear or ending)
                        ctx = elem.get("contextRef","")
                        if tag not in data:
                            data[tag] = {}
                        data[tag][ctx] = val
                    except (ValueError, AttributeError):
                        pass
    except Exception:
        pass
    return data

def pick_value(data, tags):
    """Pick best value for a list of possible tag names"""
    for tag in tags:
        if tag in data:
            vals = data[tag]
            # prefer context with "Current" or "Consolidated" or most recent
            for ctx, v in vals.items():
                if any(k in ctx for k in ["CurrentYear","Current","Consolidated","FilingDate"]):
                    return v
            # fallback: first value
            return next(iter(vals.values()))
    return None

def build_fin_df(data, items):
    """Build a single-period financial dataframe from parsed XBRL"""
    rows = []
    op_cf, capex = None, None
    op_inc, dep = None, None
    for label, tags in items:
        if not tags:
            rows.append({"Item": label, "Value": None, "_header": True})
            continue
        if tags[0] == "__FCF__":
            val = (op_cf + capex) if (op_cf is not None and capex is not None) else None
        elif tags[0] == "__EBITDA__":
            val = (op_inc + dep) if (op_inc is not None and dep is not None) else None
        else:
            val = pick_value(data, tags)
            if label == "Operating Cash Flow": op_cf = val
            if label == "Capital Expenditures": capex = (-abs(val) if val is not None else None)
            if label == "Operating Income": op_inc = val
        rows.append({"Item": label, "Value": val, "_header": False})
    return pd.DataFrame(rows)

def fmt_val(v, is_per_share=False):
    if v is None:
        return "—"
    if is_per_share or abs(v) < 1000:
        return f"{v:,.2f}"
    if abs(v) >= 1e12:
        return f"¥{v/1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"¥{v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"¥{v/1e6:.2f}M"
    return f"¥{v:,.0f}"

def render_fin_table(df_fin):
    rows_html = ""
    for _, row in df_fin.iterrows():
        if row.get("_header"):
            rows_html += f'<tr class="row-header"><td colspan="2">{row["Item"]}</td></tr>'
            continue
        is_eps = "EPS" in row["Item"] or "per share" in row["Item"].lower()
        val_str = fmt_val(row["Value"], is_per_share=is_eps)
        val_class = ""
        if row["Value"] is not None:
            val_class = "positive" if row["Value"] > 0 else "negative"
        rows_html += f'<tr><td>{row["Item"]}</td><td class="{val_class}">{val_str}</td></tr>'
    return f'<table class="fin-table"><thead><tr><th>Item</th><th>Value</th></tr></thead><tbody>{rows_html}</tbody></table>'

# ── yfinance ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=15*60, show_spinner=False)
def yf_history(symbol, period):
    intervals = {"1d":["2m","5m"],"5d":["15m","30m"],"1mo":["1d"],"3mo":["1d"],
                 "6mo":["1d","5d"],"1y":["1wk"],"2y":["1wk"],"5y":["1mo"],"10y":["1mo"],"20y":["3mo"]}
    tk = yf.Ticker(symbol)
    for itv in intervals.get(period, ["1d"]):
        h = tk.history(period=period, interval=itv, auto_adjust=False)
        if not h.empty:
            h = h.reset_index().rename(columns={"Date":"date","Datetime":"date"})
            h["date"] = pd.to_datetime(h["date"])
            h["Close"] = pd.to_numeric(h["Close"], errors="coerce")
            h = h.dropna(subset=["Close"])
            if not h.empty:
                return h, itv
    return pd.DataFrame(), "1d"

@st.cache_data(ttl=15*60, show_spinner=False)
def yf_info(symbol):
    try:
        return yf.Ticker(symbol).info
    except Exception:
        return {}

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown('<div class="terminal-header">▸ EDINET Finance Terminal &nbsp;|&nbsp; Japan Equities &amp; Filings</div>', unsafe_allow_html=True)

# ── SEARCH ───────────────────────────────────────────────────────────────────
query = st.text_input("", placeholder="Search by ticker (7203), company name, romaji, or EDINET code…", label_visibility="collapsed")
sug = fuzzy_suggest(codes, query, limit=15).reset_index(drop=True)

result_cols = (["証券コード4","提出者名","ＥＤＩＮＥＴコード"] if HAS_SECURITIES
               else ["提出者名","ＥＤＩＮＥＴコード"])

picked_rows = []
if not sug.empty:
    pick_df = sug[result_cols + ["label"]].copy()
    pick_df.insert(0, "✓", False)
    edited = st.data_editor(
        pick_df, hide_index=True, use_container_width=True,
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", width="small"),
            "label": st.column_config.TextColumn("label", disabled=True),
        },
        disabled=[c for c in pick_df.columns if c != "✓"],
        key=f"pick_{hash(query) % 1_000_000}",
    )
    picked_rows = edited.index[edited["✓"] == True].tolist()

# ── MAIN VIEW ─────────────────────────────────────────────────────────────────
if len(picked_rows) == 1:
    sel       = sug.iloc[picked_rows[0]]
    edicode   = sel["ＥＤＩＮＥＴコード"]
    sec4      = sel.get("証券コード4","") if HAS_SECURITIES else ""
    yf_symbol = f"{sec4}.T" if sec4 else None
    company   = sel["提出者名"]

    # ── Company header ────────────────────────────────────────────────────────
    info = yf_info(yf_symbol) if yf_symbol else {}
    eng_name = info.get("longName","") or info.get("shortName","")

    st.markdown(f"""
    <div style="margin: 1rem 0 0.5rem 0;">
        <div class="company-name">{company}
            {'<span class="ticker-pill">'+sec4+'.T</span>' if sec4 else ''}
            <span class="edinet-pill">{edicode}</span>
        </div>
        {f'<div class="company-sub">{eng_name}</div>' if eng_name else ''}
    </div>
    """, unsafe_allow_html=True)

    # ── Price hero ────────────────────────────────────────────────────────────
    if yf_symbol:
        hist_1d, _ = yf_history(yf_symbol, "5d")
        if not hist_1d.empty:
            last_close = float(hist_1d["Close"].iloc[-1])
            prev_close = float(hist_1d["Close"].iloc[-2]) if len(hist_1d) > 1 else last_close
            delta      = last_close - prev_close
            pct        = (delta / prev_close * 100) if prev_close else 0
            chg_class  = "price-up" if delta >= 0 else "price-down"
            arrow      = "▲" if delta >= 0 else "▼"
            st.markdown(f"""
            <div class="price-big">{last_close:,.2f} <span style="font-size:1rem;color:#4a4a6a;">JPY</span></div>
            <div class="price-change {chg_class}">{arrow} {delta:+.2f} ({pct:+.2f}%) &nbsp;<span style="color:#4a4a6a;font-size:0.75rem;">prev close</span></div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Key stats row ─────────────────────────────────────────────────────────
    if info:
        def fmt_info(k, div=1, suffix="", fmt=".2f"):
            v = info.get(k)
            if v is None or v == "N/A": return "—"
            try:
                return f"{float(v)/div:{fmt}}{suffix}"
            except Exception:
                return str(v)

        mktcap = info.get("marketCap")
        mktcap_str = (f"¥{mktcap/1e12:.2f}T" if mktcap and mktcap>=1e12
                      else f"¥{mktcap/1e9:.1f}B" if mktcap else "—")

        st.markdown(f"""
        <div class="stat-grid">
            <div class="stat-card"><div class="stat-label">Market Cap</div><div class="stat-value">{mktcap_str}</div></div>
            <div class="stat-card"><div class="stat-label">P/E Ratio</div><div class="stat-value">{fmt_info("trailingPE")}</div></div>
            <div class="stat-card"><div class="stat-label">P/B Ratio</div><div class="stat-value">{fmt_info("priceToBook")}</div></div>
            <div class="stat-card"><div class="stat-label">ROE</div><div class="stat-value">{fmt_info("returnOnEquity", div=0.01, suffix="%")}</div></div>
            <div class="stat-card"><div class="stat-label">EPS (TTM)</div><div class="stat-value">{fmt_info("trailingEps")}</div></div>
            <div class="stat-card"><div class="stat-label">Div Yield</div><div class="stat-value">{fmt_info("dividendYield", div=0.01, suffix="%")}</div></div>
            <div class="stat-card"><div class="stat-label">52W High</div><div class="stat-value">{fmt_info("fiftyTwoWeekHigh")}</div></div>
            <div class="stat-card"><div class="stat-label">52W Low</div><div class="stat-value">{fmt_info("fiftyTwoWeekLow")}</div></div>
        </div>
        """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_chart, tab_fin, tab_filings = st.tabs(["📈  Chart", "📊  Financials (EDINET)", "📄  Filings"])

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1 — CHART
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_chart:
        if yf_symbol:
            period_map = {"1D":"1d","5D":"5d","1M":"1mo","3M":"3mo","6M":"6mo",
                          "1Y":"1y","2Y":"2y","5Y":"5y","10Y":"10y","20Y":"20y"}
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                period_label = st.radio("", list(period_map.keys()), horizontal=True,
                                        index=5, label_visibility="collapsed")
            with c2:
                scale = st.selectbox("Scale", ["Price","% Change","Indexed to 100"], label_visibility="collapsed")
            with c3:
                chart_type = st.selectbox("Type", ["Line","Area"], label_visibility="collapsed")

            period = period_map[period_label]
            hist, used_itv = yf_history(yf_symbol, period)

            if not hist.empty:
                plot = hist[["date","Close","Open","High","Low","Volume"]].copy()
                first_val = float(plot["Close"].iloc[0])
                if scale == "% Change":
                    plot["value"] = (plot["Close"]/first_val - 1) * 100
                    y_title = "% Change"
                elif scale == "Indexed to 100":
                    plot["value"] = plot["Close"]/first_val * 100
                    y_title = "Index (100 = start)"
                else:
                    plot["value"] = plot["Close"]
                    y_title = "Price (JPY)"

                is_up = float(plot["value"].iloc[-1]) >= float(plot["value"].iloc[0])
                line_color = "#00d395" if is_up else "#ff4d6d"

                base = alt.Chart(plot).encode(
                    x=alt.X("date:T", title=None, axis=alt.Axis(labelColor="#4a4a6a", gridColor="#0f0f1a", domainColor="#1e1e2e", tickColor="#1e1e2e")),
                    y=alt.Y("value:Q", title=y_title, scale=alt.Scale(zero=False),
                            axis=alt.Axis(labelColor="#4a4a6a", gridColor="#1e1e2e", domainColor="#1e1e2e", tickColor="#1e1e2e", format=",.1f")),
                    tooltip=[alt.Tooltip("date:T",title="Date"),
                             alt.Tooltip("Close:Q",title="Close",format=",.2f"),
                             alt.Tooltip("value:Q",title=y_title,format=",.2f"),
                             alt.Tooltip("Volume:Q",title="Volume",format=",")]
                )

                if chart_type == "Area":
                    line_layer = base.mark_area(
                        line={"color": line_color, "strokeWidth": 1.5},
                        color=alt.Gradient("linear", stops=[
                            alt.GradientStop(color=line_color+"55", offset=0),
                            alt.GradientStop(color=line_color+"00", offset=1)
                        ], x1=1, x2=1, y1=1, y2=0)
                    )
                else:
                    line_layer = base.mark_line(color=line_color, strokeWidth=1.5)

                chart = (line_layer
                         .properties(height=300, background="#0a0a0f")
                         .configure_view(strokeOpacity=0)
                         .configure(background="#0a0a0f")
                         .interactive())

                st.altair_chart(chart, use_container_width=True)
                st.markdown(f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.65rem;color:#4a4a6a;">Interval: {used_itv} &nbsp;|&nbsp; Source: Yahoo Finance</div>', unsafe_allow_html=True)

                # Volume bar
                vol_chart = (alt.Chart(plot)
                    .mark_bar(color="#1e1e2e", opacity=0.8)
                    .encode(x=alt.X("date:T",title=None,axis=alt.Axis(labels=False,ticks=False,domain=False,grid=False)),
                            y=alt.Y("Volume:Q",title="Volume",axis=alt.Axis(labelColor="#4a4a6a",gridColor="#1e1e2e",format="~s")),
                            tooltip=[alt.Tooltip("date:T"),alt.Tooltip("Volume:Q",format=",")])
                    .properties(height=60, background="#0a0a0f")
                    .configure_view(strokeOpacity=0)
                    .configure(background="#0a0a0f"))
                st.altair_chart(vol_chart, use_container_width=True)

                csv_bytes = hist.to_csv(index=False).encode("utf-8-sig")
                st.download_button("⬇ Download OHLCV (CSV)", data=csv_bytes,
                                   file_name=f"{yf_symbol}_{period}.csv", mime="text/csv")
            else:
                st.info("No price data found.")
        else:
            st.info("No securities code — chart unavailable.")

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2 — FINANCIALS (EDINET XBRL)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_fin:
        if not API_KEY:
            st.warning("Set EDINET_API_KEY to load financials.")
        else:
            st.markdown('<div class="section-label">Pull financials from EDINET XBRL</div>', unsafe_allow_html=True)
            st.caption("Fetches the most recent 有価証券報告書 and parses it directly from XBRL — more accurate than scraped data.")

            col_s, col_e = st.columns(2)
            with col_s:
                fin_start = st.date_input("Search from", value=date.today()-timedelta(days=365), key="fin_start")
            with col_e:
                fin_end = st.date_input("Search to", value=date.today(), key="fin_end")

            if st.button("🔍 Find Annual Reports (有価証券報告書)"):
                with st.spinner("Searching filings…"):
                    df_all = list_filings(edicode, sec4, fin_start, fin_end, API_KEY)
                    yukas = df_all[df_all["formCode"] == "030000"].reset_index(drop=True)
                    st.session_state["yukas"] = yukas

            yukas = st.session_state.get("yukas", pd.DataFrame())
            if not yukas.empty:
                yuka_labels = [f"{r['date']} — {r['title']}" for _, r in yukas.iterrows()]
                chosen_idx = st.selectbox("Select filing to parse", range(len(yuka_labels)),
                                          format_func=lambda i: yuka_labels[i])
                chosen_doc_id = yukas.iloc[chosen_idx]["docID"]

                if st.button("📥 Load & Parse XBRL"):
                    with st.spinner("Downloading XBRL ZIP…"):
                        try:
                            zip_bytes = fetch_doc_bytes(chosen_doc_id, "ZIP", API_KEY)
                            xbrl_data = parse_xbrl_zip(zip_bytes)
                            st.session_state["xbrl_data"] = xbrl_data
                            st.success(f"Parsed {len(xbrl_data)} XBRL elements.")
                        except Exception as e:
                            st.error(f"Failed: {e}")

            xbrl_data = st.session_state.get("xbrl_data", {})
            if xbrl_data:
                fin_tab1, fin_tab2, fin_tab3, fin_tab4 = st.tabs(["P&L", "Balance Sheet", "Cash Flow", "Key Ratios"])

                with fin_tab1:
                    st.markdown('<div class="section-label">Income Statement (損益計算書)</div>', unsafe_allow_html=True)
                    df_pl = build_fin_df(xbrl_data, PL_ITEMS)
                    st.markdown(render_fin_table(df_pl), unsafe_allow_html=True)

                with fin_tab2:
                    st.markdown('<div class="section-label">Balance Sheet (貸借対照表)</div>', unsafe_allow_html=True)
                    df_bs = build_fin_df(xbrl_data, BS_ITEMS)
                    st.markdown(render_fin_table(df_bs), unsafe_allow_html=True)

                with fin_tab3:
                    st.markdown('<div class="section-label">Cash Flow Statement (キャッシュフロー計算書)</div>', unsafe_allow_html=True)
                    df_cf = build_fin_df(xbrl_data, CF_ITEMS)
                    st.markdown(render_fin_table(df_cf), unsafe_allow_html=True)

                with fin_tab4:
                    st.markdown('<div class="section-label">Key Ratios</div>', unsafe_allow_html=True)
                    # Compute ratios from XBRL + yfinance
                    def gv(tags): return pick_value(xbrl_data, tags)
                    net_inc  = gv(["NetIncome","ProfitLoss","NetIncomeLoss"])
                    equity   = gv(["TotalEquity","NetAssets","Equity"])
                    assets   = gv(["TotalAssets","Assets"])
                    sales    = gv(["NetSales","Revenue","Revenues"])
                    op_inc   = gv(["OperatingIncome","OperatingProfit"])
                    op_cf    = gv(["NetCashProvidedByUsedInOperatingActivities","CashFlowsFromOperatingActivities"])
                    capex_r  = gv(["PurchaseOfPropertyPlantAndEquipment","CapitalExpenditures"])
                    debt     = gv(["LongTermLoansPayable","LongTermDebt"])
                    cash     = gv(["CashAndCashEquivalents","CashAndDeposits"])
                    mktcap_v = info.get("marketCap")

                    def ratio(num, den, pct=False, prefix=""):
                        if num is None or den is None or den == 0: return "—"
                        v = num/den
                        if pct: return f"{v*100:.1f}%"
                        return f"{prefix}{v:.2f}"

                    ratios = [
                        ("ROE (Net Inc / Equity)",       ratio(net_inc, equity, pct=True)),
                        ("ROA (Net Inc / Assets)",       ratio(net_inc, assets, pct=True)),
                        ("Operating Margin",             ratio(op_inc, sales, pct=True)),
                        ("Net Margin",                   ratio(net_inc, sales, pct=True)),
                        ("Asset Turnover",               ratio(sales, assets)),
                        ("Equity Ratio (Equity/Assets)", ratio(equity, assets, pct=True)),
                        ("Debt-to-Equity",               ratio(debt, equity) if debt else "—"),
                        ("Free Cash Flow",               fmt_val((op_cf + (-abs(capex_r) if capex_r else 0)) if op_cf else None)),
                        ("P/E (from market)",            f"{info.get('trailingPE','—'):.2f}" if isinstance(info.get('trailingPE'), float) else "—"),
                        ("P/B (from market)",            f"{info.get('priceToBook','—'):.2f}" if isinstance(info.get('priceToBook'), float) else "—"),
                        ("EV/EBITDA (from market)",      f"{info.get('enterpriseToEbitda','—'):.2f}" if isinstance(info.get('enterpriseToEbitda'), float) else "—"),
                        ("Market Cap",                   fmt_val(mktcap_v) if mktcap_v else "—"),
                    ]
                    rows_html = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in ratios)
                    st.markdown(f'<table class="fin-table"><thead><tr><th>Ratio</th><th>Value</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)

                # Download
                st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)
                if st.button("⬇ Export Financials to Excel"):
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
                        build_fin_df(xbrl_data, PL_ITEMS)[["Item","Value"]].to_excel(xw, sheet_name="P&L", index=False)
                        build_fin_df(xbrl_data, BS_ITEMS)[["Item","Value"]].to_excel(xw, sheet_name="Balance Sheet", index=False)
                        build_fin_df(xbrl_data, CF_ITEMS)[["Item","Value"]].to_excel(xw, sheet_name="Cash Flow", index=False)
                    st.download_button("⬇ Download Excel", data=buf.getvalue(),
                                       file_name=f"{edicode}_financials.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            elif not yukas.empty:
                st.caption("Click 'Load & Parse XBRL' above to see financials.")
            else:
                st.caption("Click 'Find Annual Reports' to search for filings first.")

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 3 — FILINGS
    # ═══════════════════════════════════════════════════════════════════════════
    with tab_filings:
        if not API_KEY:
            st.warning("Set EDINET_API_KEY to browse filings.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                start = st.date_input("From", value=date.today()-timedelta(days=30), key="fil_start")
            with c2:
                end = st.date_input("To", value=date.today(), key="fil_end")

            only_yuka = st.checkbox("Show only 有価証券報告書 (formCode 030000)")

            if st.button("Search Filings"):
                st.session_state["filings_df"] = list_filings(edicode, sec4, start, end, API_KEY)

            df_fil = st.session_state.get("filings_df", pd.DataFrame())
            if not df_fil.empty:
                df_view = df_fil[df_fil["formCode"]=="030000"] if only_yuka else df_fil
                if not df_view.empty:
                    show_cols = ["docID","title","filerName","formCode","date"]
                    sel_df = df_view[show_cols].copy().reset_index(drop=True)
                    sel_df.insert(0,"✓",False)
                    edited_f = st.data_editor(
                        sel_df, hide_index=True, use_container_width=True,
                        column_config={"✓": st.column_config.CheckboxColumn("✓",width="small"),
                                       "title": st.column_config.TextColumn("title",width="large")},
                        disabled=[c for c in sel_df.columns if c != "✓"],
                        key=f"fil_{hash(edicode+str(start)+str(end)) % 1_000_000}",
                    )
                    sel_rows = edited_f.index[edited_f["✓"]==True].tolist()
                    kind = st.radio("Download as", ["PDF","XBRL ZIP"], horizontal=True)
                    if len(sel_rows)==1:
                        row = df_view.reset_index(drop=True).iloc[sel_rows[0]]
                        data_bytes = fetch_doc_bytes(row["docID"], "PDF" if kind=="PDF" else "ZIP", API_KEY)
                        mime = "application/pdf" if kind=="PDF" else "application/zip"
                        ext  = "pdf" if kind=="PDF" else "zip"
                        st.download_button(f"⬇ Download {kind}", data=data_bytes,
                                           file_name=f"{row['docID']}.{ext}", mime=mime, type="primary")
                    elif len(sel_rows)>1:
                        st.warning("Select one filing at a time.")
                else:
                    st.info("No filings found for this period.")

elif len(picked_rows) > 1:
    st.warning("Select one company at a time.")
else:
    st.markdown("""
    <div style="margin-top:3rem;text-align:center;color:#2a2a3a;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.8rem;letter-spacing:0.2em;">
            SEARCH FOR A COMPANY TO BEGIN
        </div>
        <div style="font-size:0.7rem;margin-top:0.5rem;color:#1e1e2e;">
            ticker · company name · romaji · EDINET code
        </div>
    </div>
    """, unsafe_allow_html=True)
