import streamlit as st
import pandas as pd
from collections import defaultdict
from datetime import timedelta

# =====================
# KONSTANTY
# =====================
SAZBA_DANE = 0.15
SAZBA_ZAHRANICNI_DANE = 0.15
OBRAT_LIMIT = 100_000
TIME_TEST = timedelta(days=3 * 365)
EPS = 1e-9


# =====================
# NORMALIZACE XTB – CLOSED POSITIONS
# =====================
def normalize_trades(df):
    df = df.copy()

    # mapování názvů (CZ + EN)
    COLUMN_MAP = {
        "Symbol": "symbol",
        "Open time": "open_time",
        "Close time": "close_time",
        "Open price": "open_price",
        "Close price": "close_price",
        "Volume": "volume",
        "Commission": "commission",
        "Type": "type",
        "Category": "category",
    }
    df = df.rename(columns=COLUMN_MAP)

    required = ["symbol", "open_time", "close_time",
                "open_price", "close_price", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Chybí sloupce v CSV: {missing}")
        st.stop()

    # převody
    df["open_time"] = pd.to_datetime(df["open_time"], dayfirst=True, errors="coerce")
    df["close_time"] = pd.to_datetime(df["close_time"], dayfirst=True, errors="coerce")

    for col in ["volume", "open_price", "close_price", "commission"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # -----------------
    # FILTRACE CFD
    # -----------------
    if "category" in df.columns:
        df = df[~df["category"].str.contains("CFD", case=False, na=False)]
    elif "type" in df.columns:
        df = df[~df["type"].str.contains("CFD", case=False, na=False)]
    else:
        # fallback – CFD mají typicky .CFD
        df = df[~df["symbol"].str.contains("CFD", case=False, na=False)]

    # -----------------
    # ROZSEKÁNÍ NA BUY / SELL
    # -----------------
    buys = df.assign(
        Time=df["open_time"],
        Side="BUY",
        Price=df["open_price"],
        Volume=df["volume"],
        Commission=df.get("commission", 0),
        Symbol=df["symbol"],
    )

    sells = df.assign(
        Time=df["close_time"],
        Side="SELL",
        Price=df["close_price"],
        Volume=df["volume"],
        Commission=df.get("commission", 0),
        Symbol=df["symbol"],
    )

    normalized = pd.concat([buys, sells], ignore_index=True)
    return normalized.sort_values("Time")


# =====================
# FIFO ENGINE
# =====================
def apply_fifo(df):
    fifo = defaultdict(list)
    results = []

    for _, row in df.iterrows():
        symbol = row["Symbol"]
        side = row["Side"]
        qty = float(row["Volume"])
        price = float(row["Price"])
        time = row["Time"]
        commission = float(row["Commission"])

        if side == "BUY":
            fifo[symbol].append({
                "qty": qty,
                "price": price,
                "date": time,
                "comm_unit": commission / qty if qty else 0
            })

        elif side == "SELL":
            remaining = qty
            sell_comm_unit = commission / qty if qty else 0

            while remaining > EPS and fifo[symbol]:
                lot = fifo[symbol][0]
                used = min(remaining, lot["qty"])

                buy_cost = used * (lot["price"] + lot["comm_unit"])
                sell_value = used * (price - sell_comm_unit)

                profit = sell_value - buy_cost
                exempt = (time - lot["date"]) > TIME_TEST

                results.append({
                    "Symbol": symbol,
                    "Qty": used,
                    "Buy date": lot["date"],
                    "Sell date": time,
                    "Buy cost": buy_cost,
                    "Sell value": sell_value,
                    "Profit": 0 if exempt else profit,
                    "Exempt": exempt
                })

                lot["qty"] -= used
                remaining -= used

                if lot["qty"] <= EPS:
                    fifo[symbol].pop(0)

    return pd.DataFrame(results)


# =====================
# SOUHRN §10
# =====================
def summarize_fifo(fifo_df):
    fifo_df["Year"] = fifo_df["Sell date"].dt.year

    summary = fifo_df.groupby("Year").agg(
        prijmy=("Sell value", "sum"),
        vydaje=("Buy cost", "sum"),
        zaklad_dane=("Profit", "sum"),
    )

    summary["dan"] = summary["zaklad_dane"].apply(lambda x: max(0, x * SAZBA_DANE))
    summary["prekrocen_limit"] = summary["prijmy"] > OBRAT_LIMIT

    return summary.round(2)


# =====================
# STREAMLIT APP
# =====================
def main():
    st.set_page_config(page_title="FIFO daně – XTB", layout="wide")
    st.title("📊 Daňový výpočet FIFO – XTB (akcie + ETF)")

    trades_file = st.file_uploader("📁 XTB – Obchody (CSV)", type="csv")

    if trades_file:
        trades_raw = pd.read_csv(
            trades_file, sep=";", decimal=",", thousands=" ", encoding="utf-8"
        )

        trades = normalize_trades(trades_raw)
        fifo_df = apply_fifo(trades)
        summary = summarize_fifo(fifo_df)

        st.subheader("📅 §10 – Roční souhrn")
        st.dataframe(summary)

        st.subheader("🔍 Detail FIFO (kontrola FÚ)")
        st.dataframe(fifo_df.round(2))

    st.warning("⚠️ Technický výpočet – nenahrazuje daňového poradce.")


if __name__ == "__main__":
    main()

