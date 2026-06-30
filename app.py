import plotly.express as px
import streamlit as st

from analytics import analytics_from_portfolio
from database import get_cache_table, init_db, portfolio_df, add_asset, delete_asset
from valuation_engine import rebalance_table, value_portfolio
from pdf_report import create_portfolio_pdf
from news_engine import get_portfolio_news
from datetime import date
import pandas as pd
from portfolio_advisor import calculate_risk_score, generate_alerts, ai_portfolio_advisor
st.set_page_config(page_title="Portföy Takip", page_icon="📈", layout="wide")
init_db()

st.title("📈 Finansal Portföy Takip Sistemi")
st.caption("v1.2 Batch Provider Engine | Time-Tolerance + SQLite Cache + Analytics")

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

with st.spinner("Batch Provider Engine fiyatları çekiyor..."):
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

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "Portföy",
    "Grafikler",
    "Rebalance",
    "Analiz",
    "Fiyat Kaynakları",
    "Haber & KAP",
    "PDF",
    "Sil",
    "Bildirimler",
    "AI Danışman"
])

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
    fig = px.pie(valued, names="kod_adi", values="guncel_deger", title="Portföy Dağılımı")
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.treemap(valued, path=["tur", "kategori", "kod_adi"], values="guncel_deger", title="Treemap")
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    rb = rebalance_table(valued)
    st.dataframe(
        rb[["kod_adi", "guncel_deger", "ideal_oran", "hedef_tutar", "alim_satim_tutari", "tahmini_adet"]]
        .rename(columns={
            "kod_adi": "Kod",
            "guncel_deger": "Mevcut Tutar",
            "ideal_oran": "Hedef Oran",
            "hedef_tutar": "Hedef Tutar",
            "alim_satim_tutari": "Al/Sat Tutarı",
            "tahmini_adet": "Tahmini Adet",
        })
        .style.format({
            "Mevcut Tutar": "{:,.2f} ₺",
            "Hedef Oran": "{:.2%}",
            "Hedef Tutar": "{:,.2f} ₺",
            "Al/Sat Tutarı": "{:+,.2f} ₺",
            "Tahmini Adet": "{:+,.4f}",
        }),
        use_container_width=True
    )

with tab4:
    corr, summary, hist = analytics_from_portfolio(raw)

    if hist.empty:
        st.info("Tarihsel veri bulunamadı.")
    else:
        st.line_chart(hist)

    if corr is not None:
        st.subheader("Korelasyon Matrisi")
        st.dataframe(
            corr.style.background_gradient(axis=None),
            use_container_width=True
        )

    if summary is not None:
        st.subheader("Risk / Getiri Özeti")
        st.dataframe(
            summary.style.format({
                "Yıllık Getiri": "{:+.2%}",
                "Yıllık Volatilite": "{:.2%}",
                "Son Fiyat": "{:,.4f}",
            }),
            use_container_width=True
        )

        optimal = summary.attrs.get("optimal")

        if optimal is not None:
            st.subheader("Sharpe Optimizasyonu")
            st.dataframe(
                optimal.style.format({
                    "Optimal Ağırlık": "{:.2%}"
                }),
                use_container_width=True
            )

with tab5:
    st.subheader("Bu değerlemede kullanılan fiyatlar")
    st.dataframe(prices, use_container_width=True)
    st.subheader("SQLite son fiyat cache")
    st.dataframe(get_cache_table(), use_container_width=True)
with tab6:
    st.subheader("Haber & KAP Takibi")

    with st.spinner("Haberler getiriliyor..."):
        news_df, summaries = get_portfolio_news(raw)

    if not news_df.empty:
        news_df["published"] = (
            pd.to_datetime(news_df["published"], errors="coerce")
            .dt.strftime("%d.%m.%Y %H:%M")
        )

    st.markdown("### AI Özetleri")

    for item in summaries:
        summary_text = item.get("summary", "-")

        if isinstance(summary_text, dict):
            summary_text = summary_text.get("summary", "-")

        with st.container(border=True):
            st.markdown(f"### 🤖 AI Haber Analizi — {item.get('symbol', '-')}")
            st.markdown(summary_text)

    st.markdown("### Haber Listesi")

    if news_df.empty:
        st.warning("Haber bulunamadı.")
    else:
        st.dataframe(
            news_df[["source", "symbol", "title", "published", "type"]],
            use_container_width=True
        )

        for _, row in news_df.head(10).iterrows():
            if row["link"]:
                st.link_button(f"📰 {row['title']}", row["link"])
with tab7:
    st.subheader("PDF Rapor Oluştur")

    pdf_file = create_portfolio_pdf(valued, prices)

    st.download_button(
        label="PDF Raporu İndir",
        data=pdf_file,
        file_name="portfoy_raporu.pdf",
        mime="application/pdf",
        type="primary"
    )

with tab8:
    labels = {
        f"#{int(r['id'])} | {r['kod_adi']} | {r['tur']} | {r['adet']} adet": int(r["id"])
        for _, r in raw.iterrows()
    }
    selected = st.selectbox("Silinecek kayıt", list(labels.keys()))
    if st.button("Seçili Varlığı Sil"):
        delete_asset(labels[selected])
        st.rerun()
with tab9:
    news_df, _ = get_portfolio_news(raw)
    st.subheader("🔔 Bildirim Merkezi")

    if raw.empty:
        st.info("Portföy boş.")

    else:

        if (valued["kar_zarar"] > 0).any():
            st.success("🟢 Karlı pozisyon mevcut.")

        if (valued["kar_zarar"] < 0).any():
            st.error("🔴 Zararda pozisyon mevcut.")

        high = valued[valued["hedef_sapma"].abs() > 20]

        if not high.empty:
            st.warning("⚠️ Yeniden dengeleme öneriliyor.")

            st.dataframe(
                high[[
                    "kod_adi",
                    "portfoy_orani",
                    "ideal_oran",
                    "hedef_sapma"
                ]],
                use_container_width=True
            )

        today_news = len(news_df)

        if today_news > 0:
            st.info(f"📰 {today_news} yeni haber bulundu.")

        if today_news == 0:
            st.success("Bugün yeni haber yok.")
with tab10:
    st.subheader("🤖 AI Portföy Danışmanı")

    risk_score, risk_reasons = calculate_risk_score(valued)
    alerts = generate_alerts(valued)

    c1, c2 = st.columns(2)

    with c1:
        st.metric("Risk Skoru", f"{risk_score}/100")

    with c2:
        if risk_score >= 70:
            st.error("Risk Seviyesi: Yüksek")
        elif risk_score >= 40:
            st.warning("Risk Seviyesi: Orta")
        else:
            st.success("Risk Seviyesi: Düşük")

    st.markdown("### 🎯 Risk Nedenleri")
    for reason in risk_reasons:
        st.write(f"- {reason}")

    st.markdown("### 🔔 Alarmlar")
    for alert in alerts:
        st.write(alert)

    st.markdown("### 🧠 AI Yorumu")
    comment = ai_portfolio_advisor(valued)
    st.info(comment)