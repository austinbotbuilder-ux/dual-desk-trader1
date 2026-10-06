#!/usr/bin/env python3
"""
Mobile-Optimized Dual Paper Trading Desk
For Samsung S24 Ultra and other phones
$2000 max • 60/40 exits • Auto-exit on RUG enabled
"""

import streamlit as st
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import plotly.express as px

# -------------------------- Config --------------------------
MAX_CAPITAL = 2000.0
MAX_POSITION_PCT = 0.08
MAX_CONCURRENT = 4
DAILY_LOSS_HALT_PCT = 0.05

SOL_JOURNAL = Path("solana_paper_journal.jsonl")
SOL_PORTFOLIO = Path("solana_paper_portfolio.json")
XRPL_JOURNAL = Path("xrpl_paper_journal.jsonl")
XRPL_PORTFOLIO = Path("xrpl_paper_portfolio.json")

# -------------------------- Page Setup --------------------------
st.set_page_config(
    page_title="Dual Desk Trader",
    page_icon="📈",
    layout="centered",          # Better for mobile
    initial_sidebar_state="collapsed"
)

# Mobile-friendly dark theme
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .stButton > button {
        width: 100%;
        height: 3.2rem;
        font-size: 1.1rem;
        border-radius: 12px;
    }
    .stMetric {
        background-color: #1a1f2e;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 8px;
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; }
    .stExpander { border-radius: 12px; }
    .status-active { color: #00e676; font-weight: 700; font-size: 1.2rem; }
    .status-halted { color: #ff1744; font-weight: 700; font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# -------------------------- Helpers --------------------------
def utc_now():
    return datetime.now(timezone.utc).isoformat()

def load_json(path: Path, default: dict):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            return default
    return default

def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2))

def append_journal(path: Path, entry: dict):
    entry["timestamp"] = utc_now()
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")

def load_journal(path: Path, n=40):
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()[-n:]
    return [json.loads(l) for l in lines if l.strip()]

def journal_to_df(path: Path):
    data = load_journal(path, 150)
    return pd.DataFrame(data) if data else pd.DataFrame()

def sol_default():
    return {"cash_usd": MAX_CAPITAL, "positions": {}, "realised_pnl": 0.0,
            "starting_equity": MAX_CAPITAL, "halted": False}

def xrpl_default():
    return {"xrp_cash": MAX_CAPITAL, "positions": {}, "realised_pnl_xrp": 0.0,
            "starting_equity": MAX_CAPITAL, "halted": False}

def sol_equity(p):
    return p["cash_usd"] + sum(pos.get("entry_usd", 0) for pos in p["positions"].values())

def xrpl_equity(p):
    return p["xrp_cash"] + sum(pos.get("entry_xrp", 0) for pos in p["positions"].values())

# -------------------------- Sidebar --------------------------
with st.sidebar:
    st.title("Controls")
    st.write(f"**Max Capital:** ${MAX_CAPITAL}")
    st.write("**Exit:** 60% @ 2x + 40% moonbag")
    st.write("**RUG Auto-Exit:** ON")
    st.divider()

    if st.button("Reset Solana", use_container_width=True):
        save_json(SOL_PORTFOLIO, sol_default())
        st.rerun()
    if st.button("Reset XRPL", use_container_width=True):
        save_json(XRPL_PORTFOLIO, xrpl_default())
        st.rerun()

    st.divider()
    st.write("### Export")
    sol_df = journal_to_df(SOL_JOURNAL)
    xrpl_df = journal_to_df(XRPL_JOURNAL)

    if not sol_df.empty:
        st.download_button("Solana Journal CSV", sol_df.to_csv(index=False), "solana_journal.csv")
    if not xrpl_df.empty:
        st.download_button("XRPL Journal CSV", xrpl_df.to_csv(index=False), "xrpl_journal.csv")

# -------------------------- Main --------------------------
st.title("📈 Dual Desk Trader")
st.caption("Solana + XRPL • Mobile Optimized")

tab1, tab2, tab3 = st.tabs(["Solana", "XRPL", "Overview & Charts"])

# ========== SOLANA TAB ==========
with tab1:
    p = load_json(SOL_PORTFOLIO, sol_default())
    halted = p.get("halted", False)

    st.metric("Cash", f"${p['cash_usd']:,.2f}")
    st.metric("Realised PnL", f"${p['realised_pnl']:,.2f}")
    st.metric("Positions", len(p["positions"]))
    st.markdown(f"**Status:** <span class='{'status-halted' if halted else 'status-active'}'>{'HALTED' if halted else 'ACTIVE'}</span>", unsafe_allow_html=True)

    if p["positions"]:
        st.dataframe(pd.DataFrame.from_dict(p["positions"], orient="index"), use_container_width=True)

    with st.expander("Buy", expanded=False):
        mint = st.text_input("Mint", key="s_mint")
        size = st.number_input("Size USD", min_value=1.0, value=50.0, key="s_size")
        price = st.number_input("Price", min_value=1e-9, value=1e-5, format="%.10f", key="s_price")
        ticket = st.text_input("Ticket ID", value=f"SOL-{datetime.now().strftime('%Y%m%d')}-001", key="s_ticket")
        if st.button("Execute Buy", key="s_buy", use_container_width=True):
            if not halted and size <= p["cash_usd"] and size <= sol_equity(p)*MAX_POSITION_PCT and len(p["positions"]) < MAX_CONCURRENT:
                tokens = size / price
                p["cash_usd"] -= size
                p["positions"][mint] = {"tokens": tokens, "entry_price": price, "entry_usd": size,
                                        "ticket_id": ticket, "moonbag_tokens": 0.0}
                save_json(SOL_PORTFOLIO, p)
                append_journal(SOL_JOURNAL, {"action": "BUY", "mint": mint, "size_usd": size, "price": price, "ticket_id": ticket})
                st.success("Buy done")
                st.rerun()
            else:
                st.error("Limits exceeded or halted")

    with st.expander("60/40 Exit"):
        mint_e = st.text_input("Mint to exit", key="s_exit")
        price_e = st.number_input("Current price", min_value=1e-9, value=2e-5, format="%.10f", key="s_exit_p")
        if st.button("Sell 60% / Keep 40%", key="s_60", use_container_width=True):
            if mint_e in p["positions"]:
                pos = p["positions"][mint_e]
                proceeds = pos["tokens"] * 0.60 * price_e
                pnl = proceeds - pos["entry_usd"] * 0.60
                p["cash_usd"] += proceeds
                p["realised_pnl"] += pnl
                pos["tokens"] *= 0.40
                pos["moonbag_tokens"] = pos["tokens"]
                pos["entry_usd"] *= 0.40
                save_json(SOL_PORTFOLIO, p)
                append_journal(SOL_JOURNAL, {"action": "SELL_60PCT", "mint": mint_e, "pnl_usd": pnl})
                st.success("60/40 done")
                st.rerun()

    with st.expander("RUG Auto-Exit (Enabled)"):
        mint_r = st.text_input("Mint", key="s_rug")
        price_r = st.number_input("Price", min_value=1e-9, value=1e-5, format="%.10f", key="s_rug_p")
        reason = st.text_input("Reason", value="LP pulled", key="s_rug_r")
        if st.button("AUTO EXIT RUG", key="s_rug_btn", use_container_width=True):
            if mint_r in p["positions"]:
                pos = p["positions"][mint_r]
                proceeds = pos["tokens"] * price_r
                pnl = proceeds - pos["entry_usd"]
                p["cash_usd"] += proceeds
                p["realised_pnl"] += pnl
                del p["positions"][mint_r]
                save_json(SOL_PORTFOLIO, p)
                append_journal(SOL_JOURNAL, {"action": "AUTO_EXIT_RUG", "mint": mint_r, "pnl_usd": pnl, "alert_reason": reason})
                st.warning("RUG auto-exit done")
                st.rerun()

    st.subheader("Journal")
    st.dataframe(journal_to_df(SOL_JOURNAL), use_container_width=True)

# ========== XRPL TAB ==========
with tab2:
    xp = load_json(XRPL_PORTFOLIO, xrpl_default())
    halted_x = xp.get("halted", False)

    st.metric("Cash XRP", f"{xp['xrp_cash']:,.2f}")
    st.metric("Realised PnL", f"{xp['realised_pnl_xrp']:,.2f}")
    st.metric("Positions", len(xp["positions"]))
    st.markdown(f"**Status:** <span class='{'status-halted' if halted_x else 'status-active'}'>{'HALTED' if halted_x else 'ACTIVE'}</span>", unsafe_allow_html=True)

    if xp["positions"]:
        st.dataframe(pd.DataFrame.from_dict(xp["positions"], orient="index"), use_container_width=True)

    with st.expander("Buy"):
        cur = st.text_input("Currency", value="SPY", key="x_cur")
        iss = st.text_input("Issuer", key="x_iss")
        size_x = st.number_input("Size XRP", min_value=1.0, value=50.0, key="x_size")
        price_x = st.number_input("Price XRP", min_value=1e-8, value=0.1, key="x_price")
        ticket_x = st.text_input("Ticket", value=f"XRPL-{datetime.now().strftime('%Y%m%d')}-001", key="x_ticket")
        if st.button("Execute Buy", key="x_buy", use_container_width=True):
            if not halted_x and size_x <= xp["xrp_cash"] and size_x <= xrpl_equity(xp)*MAX_POSITION_PCT and len(xp["positions"]) < MAX_CONCURRENT:
                key = f"{cur}:{iss}"
                tokens = size_x / price_x
                xp["xrp_cash"] -= size_x
                xp["positions"][key] = {"tokens": tokens, "entry_price_xrp": price_x, "entry_xrp": size_x,
                                        "ticket_id": ticket_x, "moonbag_tokens": 0.0}
                save_json(XRPL_PORTFOLIO, xp)
                append_journal(XRPL_JOURNAL, {"action": "BUY", "currency": cur, "issuer": iss, "size_xrp": size_x, "ticket_id": ticket_x})
                st.success("Buy done")
                st.rerun()
            else:
                st.error("Limits exceeded or halted")

    with st.expander("60/40 Exit"):
        key_e = st.text_input("Key (CURRENCY:issuer)", key="x_exit")
        price_e = st.number_input("Current price", min_value=1e-8, value=0.2, key="x_exit_p")
        if st.button("Sell 60% / Keep 40%", key="x_60", use_container_width=True):
            if key_e in xp["positions"]:
                pos = xp["positions"][key_e]
                proceeds = pos["tokens"] * 0.60 * price_e
                pnl = proceeds - pos["entry_xrp"] * 0.60
                xp["xrp_cash"] += proceeds
                xp["realised_pnl_xrp"] += pnl
                pos["tokens"] *= 0.40
                pos["moonbag_tokens"] = pos["tokens"]
                pos["entry_xrp"] *= 0.40
                save_json(XRPL_PORTFOLIO, xp)
                append_journal(XRPL_JOURNAL, {"action": "SELL_60PCT", "key": key_e, "pnl_xrp": pnl})
                st.success("60/40 done")
                st.rerun()

    with st.expander("RUG Auto-Exit (Enabled)"):
        key_r = st.text_input("Position key", key="x_rug")
        price_r = st.number_input("Price", min_value=1e-8, value=0.08, key="x_rug_p")
        reason_r = st.text_input("Reason", value="Issuer freeze", key="x_rug_r")
        if st.button("AUTO EXIT RUG", key="x_rug_btn", use_container_width=True):
            if key_r in xp["positions"]:
                pos = xp["positions"][key_r]
                proceeds = pos["tokens"] * price_r
                pnl = proceeds - pos["entry_xrp"]
                xp["xrp_cash"] += proceeds
                xp["realised_pnl_xrp"] += pnl
                del xp["positions"][key_r]
                save_json(XRPL_PORTFOLIO, xp)
                append_journal(XRPL_JOURNAL, {"action": "AUTO_EXIT_RUG", "key": key_r, "pnl_xrp": pnl, "alert_reason": reason_r})
                st.warning("RUG auto-exit done")
                st.rerun()

    st.subheader("Journal")
    st.dataframe(journal_to_df(XRPL_JOURNAL), use_container_width=True)

# ========== OVERVIEW & CHARTS ==========
with tab3:
    sp = load_json(SOL_PORTFOLIO, sol_default())
    xp = load_json(XRPL_PORTFOLIO, xrpl_default())

    st.subheader("Overview")
    st.write(f"**Solana Cash:** ${sp['cash_usd']:,.2f}  |  PnL: ${sp['realised_pnl']:,.2f}")
    st.write(f"**XRPL Cash:** {xp['xrp_cash']:,.2f} XRP  |  PnL: {xp['realised_pnl_xrp']:,.2f} XRP")

    st.subheader("Solana PnL Chart")
    sol_df = journal_to_df(SOL_JOURNAL)
    if not sol_df.empty and "pnl_usd" in sol_df.columns:
        closed = sol_df[sol_df["action"].isin(["SELL_60PCT", "AUTO_EXIT_RUG"])]
        if not closed.empty:
            closed = closed.copy()
            closed["cum"] = closed["pnl_usd"].cumsum()
            fig = px.line(closed, x="timestamp", y="cum", title="Cumulative PnL (USD)")
            fig.update_layout(template="plotly_dark", height=360)
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("XRPL PnL Chart")
    xrpl_df = journal_to_df(XRPL_JOURNAL)
    if not xrpl_df.empty and "pnl_xrp" in xrpl_df.columns:
        closed = xrpl_df[xrpl_df["action"].isin(["SELL_60PCT", "AUTO_EXIT_RUG"])]
        if not closed.empty:
            closed = closed.copy()
            closed["cum"] = closed["pnl_xrp"].cumsum()
            fig = px.line(closed, x="timestamp", y="cum", title="Cumulative PnL (XRP)")
            fig.update_layout(template="plotly_dark", height=360)
            st.plotly_chart(fig, use_container_width=True)

st.caption("Paper trading only • Not financial advice")