import streamlit as st
import pandas as pd

SAZBA_DANE = 0.15
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

    return trades.groupby("Year").agg(
        zisky_obchody=("zisky", "sum"),
        ztraty_obchody=("ztraty", "sum"),
        vysledek_obchody=("Gross P/L", "sum"),
        obrat=("Sale value", "sum"),
        pocet_obchodu=("Symbol", "count"),
    )


def process_dividends(dividends):
    dividends = dividends[dividends["Type"] == "DIVIDENT"].copy()
    dividends["Time"] = pd.to_datetime(dividends["Time"], dayfirst=True, errors="coerce")
    dividends["Year"] = dividends["Time"].dt.year
    dividends["Amount"] = pd.to_numeric(dividends["Amount"], errors="coerce")

    dividends["div_cista"] = dividends["Amount"]
    dividends["div_hruba"] = dividends["div_cista"] / (1 - SAZBA_ZAHRANICNI_DANE)
    dividends["zahranicni_dan"] = dividends["div_hruba"] * SAZBA_ZAHRANICNI_DANE

    return dividends.groupby("Year").agg(
        dividendy_ciste=("div_cista", "sum"),
        dividendy_hrube=("div_hruba", "sum"),
        zahranicni_dan=("zahranicni_dan", "sum"),
        pocet_vyplat=("Symbol", "count"),
    )


def main():
    st.title("📊 Výpočet základu daně – XTB broker")

    st.markdown(
        "Nahraj CSV soubory **xtb_o.csv** (obchody) a **xtb_dividendy.csv** (dividendy)."
    )

    trades_file = st.file_uploader("📁 Obchody (CSV)", type=["csv"])
    dividends_file = st.file_uploader("📁 Dividendy (CSV)", type=["csv"])

    if trades_file and dividends_file:
        try:
            trades = pd.read_csv(trades_file, sep=";", decimal=",", thousands=" ", encoding="utf-8")
            dividends = pd.read_csv(dividends_file, sep=";", decimal=",", encoding="utf-8")

            yearly = (
                process_trades(trades)
                .join(process_dividends(dividends), how="outer")
                .fillna(0)
                .round(2)
            )

            # Daňové výpočty
            yearly["danova_povinnost"] = yearly["obrat"].apply(
                lambda x: "ANO" if x > OBRAT_LIMIT else "NE"
            )

            yearly["dan_obchody"] = yearly["vysledek_obchody"].apply(
                lambda x: max(0, x * SAZBA_DANE)
            )

            yearly["dan_dividendy_cz"] = yearly["dividendy_hrube"] * SAZBA_DANE
            yearly["dan_dividendy_doplatek"] = (
                yearly["dan_dividendy_cz"] - yearly["zahranicni_dan"]
            ).apply(lambda x: max(0, x))

            yearly["dan_celkem"] = (
                yearly["dan_obchody"] + yearly["dan_dividendy_doplatek"]
            ).round(2)

            st.subheader("📅 Roční přehled")
            st.dataframe(yearly)

            st.subheader("💰 Odhad daně dle let")
            st.dataframe(
                yearly[
                    ["dan_obchody", "dan_dividendy_doplatek", "dan_celkem"]
                ].rename(columns={
                    "dan_obchody": "Daň z obchodů (§10)",
                    "dan_dividendy_doplatek": "Daň z dividend (§8)",
                    "dan_celkem": "Daň celkem",
                })
            )

            st.success(
                f"🧮 Odhad daně celkem: {yearly['dan_celkem'].sum():,.2f} Kč"
            )

            st.markdown("---")
            st.subheader("📄 Jak vyplnit daňové přiznání (ČR)")

            st.info(
                """
                **Obchody – Příloha č. 2 (§10)**
                - Řádek 207 – Obrat
                - Řádek 208 – Výdaje
                - Řádek 209 – Rozdíl
                """
            )

            st.info(
                """
                **Dividendy – Příloha č. 3 (§8)**
                - Řádek 38 – Hrubé dividendy
                - Řádek 43 – Zahraniční daň (zápočet)
                """
            )

            st.warning(
                "⚠️ Jedná se o orientační výpočet. Aplikace nenahrazuje daňového poradce."
            )

        except Exception as e:
            st.error(f"Chyba při zpracování souborů: {e}")

    st.markdown(
        """
        <hr>
        <div style="text-align:center; color:gray; font-size:0.9em;">
            © 2025 Luboš Binar
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
