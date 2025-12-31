import streamlit as st
import pandas as pd

SAZBA_ZAHRANICNI_DANE = 0.15
OBRAT_LIMIT = 100_000

def process_trades(trades):
    trades = trades[trades["Close time"].notna()].copy()
    trades["Close time"] = pd.to_datetime(trades["Close time"], dayfirst=True, errors="coerce")
    trades["Year"] = trades["Close time"].dt.year

    trades["Gross P/L"] = pd.to_numeric(trades["Gross P/L"], errors="coerce")
    trades["Sale value"] = pd.to_numeric(trades["Sale value"], errors="coerce")
    trades = trades[trades["Sale value"].notna()]

    trades["zisky"] = trades["Gross P/L"].where(trades["Gross P/L"] > 0, 0)
    trades["ztraty"] = trades["Gross P/L"].where(trades["Gross P/L"] < 0, 0)

    yearly_trades = trades.groupby("Year").agg(
        zisky_obchody=("zisky", "sum"),
        ztraty_obchody=("ztraty", "sum"),
        vysledek_obchody=("Gross P/L", "sum"),
        obrat=("Sale value", "sum"),
        pocet_obchodu=("Symbol", "count"),
    )

    return yearly_trades

def process_dividends(dividends):
    dividends = dividends[dividends["Type"] == "DIVIDENT"].copy()
    dividends["Time"] = pd.to_datetime(dividends["Time"], dayfirst=True, errors="coerce")
    dividends["Year"] = dividends["Time"].dt.year
    dividends["Amount"] = pd.to_numeric(dividends["Amount"], errors="coerce")

    dividends["div_cista"] = dividends["Amount"]
    dividends["div_hruba"] = dividends["div_cista"] / (1 - SAZBA_ZAHRANICNI_DANE)
    dividends["zahranicni_dan"] = dividends["div_hruba"] * SAZBA_ZAHRANICNI_DANE

    yearly_div = dividends.groupby("Year").agg(
        dividendy_ciste=("div_cista", "sum"),
        dividendy_hrube=("div_hruba", "sum"),
        zahranicni_dan=("zahranicni_dan", "sum"),
        pocet_vyplat=("Symbol", "count"),
    )
    return yearly_div

def main():
    st.title("Výpočet základu daně - XTB broker")

    st.markdown(
        """
        Nahraj CSV soubor s obchody (`xtb_o.csv`) a CSV soubor s dividendami (`xtb_dividendy.csv`).
        """
    )

    trades_file = st.file_uploader("Obchody (CSV)", type=["csv"])
    dividends_file = st.file_uploader("Dividendy (CSV)", type=["csv"])

    if trades_file and dividends_file:
        try:
            trades = pd.read_csv(trades_file, sep=";", decimal=",", thousands=" ", encoding="utf-8")
            dividends = pd.read_csv(dividends_file, sep=";", decimal=",", encoding="utf-8")

            yearly_trades = process_trades(trades)
            yearly_div = process_dividends(dividends)

            yearly = yearly_trades.join(yearly_div, how="outer").fillna(0).round(2)
            yearly["danova_povinnost"] = yearly["obrat"].apply(lambda x: "ANO" if x > OBRAT_LIMIT else "NE")

            st.subheader("Roční detail zisků a ztrát")
            st.dataframe(yearly)

            total = yearly.sum(numeric_only=True)

            st.subheader("Celkem za všechny roky")
            st.write(f"Zisky z obchodů: {total['zisky_obchody']:,.2f} Kč")
            st.write(f"Ztráty z obchodů: {total['ztraty_obchody']:,.2f} Kč")
            st.write(f"Výsledek obchodů: {total['vysledek_obchody']:,.2f} Kč")
            st.write(f"Hrubé dividendy: {total['dividendy_hrube']:,.2f} Kč")
            st.write(f"Zahraniční daň: {total['zahranicni_dan']:,.2f} Kč")

        except Exception as e:
            st.error(f"Chyba při zpracování souborů: {e}")

if __name__ == "__main__":
    st.markdown(
    """
    <hr>
    <div style="text-align: center; color: gray; font-size: 0.9em;">
        © 2025 Luboš Binar
    </div>
    """,
    unsafe_allow_html=True
)
    main()



