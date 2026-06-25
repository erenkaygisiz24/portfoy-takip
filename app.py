import streamlit as st

from database import init_db, portfolio_df, add_asset, delete_asset
from valuation_engine import value_portfolio

st.set_page_config(page_title="Portföy Takip", page_icon="📈", layout="wide")
init_db()

st.title("📈 Finansal Portföy Takip Sistemi")
st.caption("v1.1 Provider Engine | TEFAS + BIST + Döviz + Emtia | Time-Tolerance + SQLite Cache")

with st.sidebar:
    st.header("Varlık Ekle")
    tur = st.selectbox("Tür", ["Fon", "Hisse Senedi", "Döviz", "Emtia"])
    kategori = st.selectbox("Kategori", ["BIST", "Teknoloji", "Yabancı Hisse", "Para Piyasası", "Altın/Emtia", "Diğer"])
    kod = st.text_input("Kod", placeholder="YAY, THYAO, USD, EUR, GRAM ALTIN").strip().upper()
    adet = st.number_input("Adet", min_value=0.0, step=0.1)
    maliyet = st.number_input("Maliyet Fiyatı", min_value=0.0, step=0.1)
    hedef = st.number_input("Hedef Fiyat", min_value=0.0, step=0.1)
    ideal = st.slider("İdeal Oran (%)", 0, 100, 20) / 100

    if st.button("Kaydet", type="primary"):
        if kod and adet > 0 and maliyet > 0:
            add_asset(tur, kategori, kod, adet, maliyet, hedef, ideal)
            st.success("Kaydedildi.")
            st.rerun()
        else:
            st.error("Kod, adet ve maliyet gir.")

    if st.button("Streamlit Cache Temizle"):
        st.cache_data.clear()
        st.rerun()

raw = portfolio_df()

if raw.empty:
    st.info("Soldaki menüden ilk varlığını ekle.")
    st.stop()

with st.spinner("Provider Engine fiyatları çekiyor..."):
    valued, prices = value_portfolio(raw)

total_cost = float(valued["maliyet_degeri"].sum())
total_value = float(valued["guncel_deger"].sum())
pnl = total_value - total_cost
pnl_pct = pnl / total_cost if total_cost > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam Maliyet", f"{total_cost:,.2f} ₺")
c2.metric("Güncel Değer", f"{total_value:,.2f} ₺")
c3.metric("Kâr/Zarar", f"{pnl:+,.2f} ₺")
c4.metric("Getiri", f"{pnl_pct:+.2%}")

tab1, tab2, tab3 = st.tabs(["Portföy", "Fiyat Kaynakları", "Sil"])

with tab1:
    show = valued.rename(columns={
        "tur": "Tür", "kategori": "Kategori", "kod_adi": "Kod", "adet": "Adet",
        "maliyet": "Maliyet", "price": "Güncel Fiyat", "price_date": "Fiyat Tarihi",
        "source": "Kaynak", "status": "Durum", "maliyet_degeri": "Maliyet Değeri",
        "guncel_deger": "Güncel Değer", "kar_zarar": "Kâr/Zarar",
        "kar_zarar_pct": "Kâr/Zarar %", "portfoy_orani": "Portföy Oranı",
        "ideal_oran": "İdeal Oran", "hedef_sapma": "Hedef Sapma"
    })
    cols = ["id", "Tür", "Kategori", "Kod", "Adet", "Maliyet", "Güncel Fiyat", "Fiyat Tarihi", "Kaynak",
            "Durum", "Maliyet Değeri", "Güncel Değer", "Kâr/Zarar", "Kâr/Zarar %", "Portföy Oranı", "İdeal Oran", "Hedef Sapma"]
    st.dataframe(
        show[[c for c in cols if c in show.columns]].style.format({
            "Adet": "{:,.4f}", "Maliyet": "{:,.4f} ₺", "Güncel Fiyat": "{:,.4f} ₺",
            "Maliyet Değeri": "{:,.2f} ₺", "Güncel Değer": "{:,.2f} ₺",
            "Kâr/Zarar": "{:+,.2f} ₺", "Kâr/Zarar %": "{:+.2%}",
            "Portföy Oranı": "{:.2%}", "İdeal Oran": "{:.2%}", "Hedef Sapma": "{:+.2%}"
        }),
        use_container_width=True
    )

with tab2:
    st.dataframe(prices, use_container_width=True)

with tab3:
    labels = {
        f"#{int(r['id'])} | {r['kod_adi']} | {r['tur']} | {r['adet']} adet": int(r["id"])
        for _, r in raw.iterrows()
    }
    selected = st.selectbox("Silinecek kayıt", list(labels.keys()))
    if st.button("Seçili Varlığı Sil"):
        delete_asset(labels[selected])
        st.rerun()
