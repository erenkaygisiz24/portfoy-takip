from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from technical_analysis import get_asset_history
from analytics import analytics_from_portfolio
from database import add_asset, delete_asset, get_cache_table, init_db, portfolio_df
from news_engine import get_portfolio_news
from pdf_report import create_portfolio_pdf
from performance_tracker import load_snapshots, save_daily_snapshot
from portfolio_advisor import ai_portfolio_advisor, calculate_risk_score, generate_alerts
from technical_analysis import (
    analyze_portfolio_technical,
    build_technical_figures,
    get_technical_chart_data,
    technical_comment,
    technical_comment_with_gemini,
)
from valuation_engine import rebalance_table, value_portfolio


st.set_page_config(page_title="Portföy Takip", page_icon="📈", layout="wide")
init_db()

st.title("📈 Finansal Portföy Takip Sistemi")
st.caption("Asset Management Platform | TEFAS + BIST + Döviz + Emtia + AI + Teknik Analiz")


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("Varlık Ekle")
    tur = st.selectbox("Tür", ["Fon", "Hisse Senedi", "Döviz", "Emtia"])
    kategori = st.selectbox(
        "Kategori",
        ["BIST", "Teknoloji", "Yabancı Hisse", "Para Piyasası", "Altın/Emtia", "Diğer"],
    )
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

with st.spinner("Fiyatlar çekiliyor ve portföy değerleniyor..."):
    valued, prices = value_portfolio(raw)


# =========================
# KPI
# =========================
total_cost = float(valued["maliyet_degeri"].sum())
total_value = float(valued["guncel_deger"].sum())
pnl = total_value - total_cost
pnl_pct = pnl / total_cost if total_cost > 0 else 0
save_daily_snapshot(total_cost, total_value, pnl, pnl_pct)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam Maliyet", f"{total_cost:,.2f} ₺")
c2.metric("Güncel Değer", f"{total_value:,.2f} ₺")
c3.metric("Kâr/Zarar", f"{pnl:+,.2f} ₺")
c4.metric("Getiri", f"{pnl_pct:+.2%}")


# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
    "Portföy",
    "Grafikler",
    "Rebalance",
    "Analiz",
    "Fiyat Kaynakları",
    "Haber & KAP",
    "PDF",
    "Sil",
    "Bildirimler",
    "AI Danışman",
    "Teknik Analiz",
    "Performans",
])


# =========================
# TAB 1 PORTFOLIO
# =========================
with tab1:
    show = valued.rename(columns={
        "tur": "Tür", "kategori": "Kategori", "kod_adi": "Kod", "adet": "Adet",
        "maliyet": "Maliyet", "price": "Güncel Fiyat", "price_date": "Fiyat Tarihi",
        "source": "Kaynak", "status": "Durum", "maliyet_degeri": "Maliyet Değeri",
        "guncel_deger": "Güncel Değer", "kar_zarar": "Kâr/Zarar",
        "kar_zarar_pct": "Kâr/Zarar %", "portfoy_orani": "Portföy Oranı",
        "ideal_oran": "İdeal Oran", "hedef_sapma": "Hedef Sapma",
    })
    cols = [
        "id", "Tür", "Kategori", "Kod", "Adet", "Maliyet", "Güncel Fiyat", "Fiyat Tarihi",
        "Kaynak", "Durum", "Maliyet Değeri", "Güncel Değer", "Kâr/Zarar",
        "Kâr/Zarar %", "Portföy Oranı", "İdeal Oran", "Hedef Sapma",
    ]
    st.dataframe(
        show[[c for c in cols if c in show.columns]].style.format({
            "Adet": "{:,.4f}", "Maliyet": "{:,.4f} ₺", "Güncel Fiyat": "{:,.4f} ₺",
            "Maliyet Değeri": "{:,.2f} ₺", "Güncel Değer": "{:,.2f} ₺",
            "Kâr/Zarar": "{:+,.2f} ₺", "Kâr/Zarar %": "{:+.2%}",
            "Portföy Oranı": "{:.2%}", "İdeal Oran": "{:.2%}", "Hedef Sapma": "{:+.2%}",
        }),
        width="stretch",
    )


# =========================
# TAB 2 CHARTS
# =========================
with tab2:
    fig = px.pie(valued, names="kod_adi", values="guncel_deger", title="Portföy Dağılımı")
    st.plotly_chart(fig, width="stretch")

    fig2 = px.treemap(valued, path=["tur", "kategori", "kod_adi"], values="guncel_deger", title="Treemap")
    st.plotly_chart(fig2, width="stretch")


# =========================
# TAB 3 REBALANCE
# =========================
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
        width="stretch",
    )


# =========================
# TAB 4 ANALYSIS
# =========================
with tab4:
    st.subheader("📊 Risk / Getiri Analizi")

    hist_data = {}

    for _, row in raw.iterrows():
        kod = row["kod_adi"]
        tur = row["tur"]

        series = get_asset_history(kod, tur, days=180)

        if series is not None and not series.empty:
            hist_data[kod] = series

    if not hist_data:
        st.warning("Tarihsel veri bulunamadı.")
    else:
        hist = pd.DataFrame(hist_data).sort_index().ffill().dropna()

        st.markdown("### 📈 Tarihsel Fiyat Grafiği")
        st.line_chart(hist, width="stretch")

        returns = hist.pct_change().dropna()

        if returns.empty:
            st.warning("Getiri hesaplamak için yeterli veri yok.")
        else:
            summary_rows = []

            for col in returns.columns:
                first_price = hist[col].iloc[0]
                last_price = hist[col].iloc[-1]

                total_return = (last_price / first_price) - 1

                days_count = max((hist.index[-1] - hist.index[0]).days, 1)
                years = days_count / 365

                cagr = (last_price / first_price) ** (1 / years) - 1 if years > 0 else 0

                daily_return = returns[col].mean()
                daily_vol = returns[col].std()

                annual_return = daily_return * 252
                annual_vol = daily_vol * (252 ** 0.5)

                sharpe = annual_return / annual_vol if annual_vol != 0 else 0

                cumulative = (1 + returns[col]).cumprod()
                running_max = cumulative.cummax()
                drawdown = (cumulative / running_max) - 1
                max_drawdown = drawdown.min()

                if annual_vol >= 0.30 or max_drawdown <= -0.20:
                    risk_level = "🔴 Yüksek"
                elif annual_vol >= 0.15 or max_drawdown <= -0.10:
                    risk_level = "🟡 Orta"
                else:
                    risk_level = "🟢 Düşük"

                summary_rows.append({
                    "Kod": col,
                    "Toplam Getiri": total_return,
                    "CAGR": cagr,
                    "Yıllık Getiri": annual_return,
                    "Yıllık Volatilite": annual_vol,
                    "Sharpe": sharpe,
                    "Max Drawdown": max_drawdown,
                    "Risk Seviyesi": risk_level,
                    "Son Fiyat": last_price,
                })

            summary_df = pd.DataFrame(summary_rows)

            st.markdown("### 📌 Risk / Getiri Özeti")
            st.dataframe(
                summary_df.style.format({
                    "Toplam Getiri": "{:+.2%}",
                    "CAGR": "{:+.2%}",
                    "Yıllık Getiri": "{:+.2%}",
                    "Yıllık Volatilite": "{:.2%}",
                    "Sharpe": "{:.2f}",
                    "Max Drawdown": "{:.2%}",
                    "Son Fiyat": "{:,.4f}",
                }),
                width="stretch"
            )

            st.markdown("### 📉 Drawdown Grafiği")

            drawdown_df = pd.DataFrame(index=returns.index)

            for col in returns.columns:
                cumulative = (1 + returns[col]).cumprod()
                running_max = cumulative.cummax()
                drawdown_df[col] = (cumulative / running_max) - 1

            st.line_chart(drawdown_df, width="stretch")

            st.markdown("### 🤖 Risk Yorumu")

            first = summary_df.iloc[0]

            risk_comment = f"""
**{first['Kod']}** için son 180 günlük analiz:

- Toplam getiri: **{first['Toplam Getiri']:+.2%}**
- CAGR: **{first['CAGR']:+.2%}**
- Yıllık volatilite: **{first['Yıllık Volatilite']:.2%}**
- Sharpe oranı: **{first['Sharpe']:.2f}**
- Maksimum düşüş: **{first['Max Drawdown']:.2%}**
- Risk seviyesi: **{first['Risk Seviyesi']}**

Genel yorum: Sharpe oranı 1'in üzerindeyse risk/getiri dengesi olumlu kabul edilebilir. 
Max drawdown değeri, yatırımın seçilen dönemde yaşadığı en sert geri çekilmeyi gösterir.
"""

            st.info(risk_comment)

            if len(returns.columns) >= 2:
                st.markdown("### 🔗 Korelasyon Matrisi")
                corr = returns.corr()

                st.dataframe(
                    corr.style.format("{:.2f}").background_gradient(axis=None),
                    width="stretch"
                )
            else:
                st.info("Korelasyon için en az 2 varlık gerekiyor.")
# =========================
# TAB 5 PRICE SOURCES
# =========================
with tab5:
    st.subheader("Bu değerlemede kullanılan fiyatlar")
    st.dataframe(prices, width="stretch")
    st.subheader("SQLite son fiyat cache")
    st.dataframe(get_cache_table(), width="stretch")


# =========================
# TAB 6 NEWS
# =========================
with tab6:
    st.subheader("Haber & KAP Takibi")

    period_label = st.radio(
        "Haber periyodu",
        ["Son 7 gün", "Son 30 gün", "Tüm zamanlar"],
        horizontal=True
    )

    if period_label == "Son 7 gün":
        period = 7
    elif period_label == "Son 30 gün":
        period = 30
    else:
        period = 3650

    with st.spinner("Haberler getiriliyor..."):
        news_df, summaries = get_portfolio_news(raw, days=period)

    if not news_df.empty and "published" in news_df.columns:
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
        visible_cols = ["source", "symbol", "title", "published", "type"]
        st.dataframe(
            news_df[[c for c in visible_cols if c in news_df.columns]],
            width="stretch"
        )

        for _, row in news_df.head(10).iterrows():
            if row.get("link"):
                st.link_button(f"📰 {row['title']}", row["link"])

# =========================
# TAB 7 PDF
# =========================
with tab7:
    st.subheader("PDF Rapor Oluştur")
    pdf_file = create_portfolio_pdf(valued, prices)
    st.download_button(
        label="PDF Raporu İndir",
        data=pdf_file,
        file_name="portfoy_raporu.pdf",
        mime="application/pdf",
        type="primary",
    )


# =========================
# TAB 8 DELETE
# =========================
with tab8:
    labels = {
        f"#{int(r['id'])} | {r['kod_adi']} | {r['tur']} | {r['adet']} adet": int(r["id"])
        for _, r in raw.iterrows()
    }
    selected = st.selectbox("Silinecek kayıt", list(labels.keys()))
    if st.button("Seçili Varlığı Sil"):
        delete_asset(labels[selected])
        st.rerun()


# =========================
# TAB 9 ALERTS
# =========================
with tab9:
    st.subheader("🔔 Bildirim Merkezi")
    alerts = generate_alerts(valued)

    if (valued["kar_zarar"] > 0).any():
        st.success("🟢 Karlı pozisyon mevcut.")
    if (valued["kar_zarar"] < 0).any():
        st.error("🔴 Zararda pozisyon mevcut.")

    high = valued[valued["hedef_sapma"].abs() > 0.20]
    if not high.empty:
        st.warning("⚠️ Yeniden dengeleme öneriliyor.")
        st.dataframe(high[["kod_adi", "portfoy_orani", "ideal_oran", "hedef_sapma"]], width="stretch")

    for alert in alerts:
        st.write(alert)


# =========================
# TAB 10 AI ADVISOR
# =========================
with tab10:
    st.subheader("🤖 AI Portföy Danışmanı")
    risk_score, risk_reasons = calculate_risk_score(valued)
    alerts = generate_alerts(valued)

    c1, c2 = st.columns(2)
    c1.metric("Risk Skoru", f"{risk_score}/100")

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
    st.info(ai_portfolio_advisor(valued))


# =========================
# TAB 11 TECHNICAL ANALYSIS
# =========================
with tab11:
    st.subheader("📈 Teknik Analiz")

    with st.spinner("Teknik analiz hesaplanıyor..."):
        tech = analyze_portfolio_technical(raw, days=180)

    if tech.empty:
        st.warning("Teknik analiz için yeterli veri yok.")
    else:
        avg_score = tech["Teknik Skor"].mean()
        c1, c2, c3 = st.columns(3)
        c1.metric("Ortalama Teknik Skor", f"{avg_score:.0f}/100")
        c2.metric("Pozitif Sinyal", int(tech["Teknik Sinyal"].str.contains("Al", na=False).sum()))
        c3.metric("Zayıf Sinyal", int(tech["Teknik Sinyal"].str.contains("Zayıf", na=False).sum()))

        if avg_score >= 70:
            st.success("🟢 Genel teknik görünüm güçlü.")
        elif avg_score >= 45:
            st.warning("🟡 Genel teknik görünüm nötr.")
        else:
            st.error("🔴 Genel teknik görünüm zayıf.")

        st.dataframe(
            tech.style.format({
                "Son Fiyat": "{:,.4f}",
                "RSI": "{:.2f}",
                "MACD": "{:.4f}",
                "MACD Sinyal": "{:.4f}",
                "SMA20": "{:.4f}",
                "SMA50": "{:.4f}",
                "EMA20": "{:.4f}",
                "EMA50": "{:.4f}",
                "Üst Bant": "{:.4f}",
                "Orta Bant": "{:.4f}",
                "Alt Bant": "{:.4f}",
                "Destek": "{:.4f}",
                "Direnç": "{:.4f}",
                "Teknik Skor": "{:.0f}",
            }),
            width="stretch",
        )

        st.markdown("## 📊 Teknik Grafikler")
        selected_symbol = st.selectbox("Grafik için varlık seç", tech["Kod"].tolist())
        selected_type = raw.loc[raw["kod_adi"] == selected_symbol, "tur"].iloc[0]

        chart_df = get_technical_chart_data(selected_symbol, selected_type, days=180)
        price_fig, rsi_fig, macd_fig = build_technical_figures(chart_df, selected_symbol)

        if price_fig is None:
            st.warning("Grafik oluşturulamadı.")
        else:
            st.plotly_chart(price_fig, width="stretch")
            st.plotly_chart(rsi_fig, width="stretch")
            st.plotly_chart(macd_fig, width="stretch")

        st.markdown("## 🤖 Teknik Yorum")
        selected_row = tech[tech["Kod"] == selected_symbol].iloc[0]
        st.info(technical_comment_with_gemini(selected_row.to_dict()))


# =========================
# TAB 12 PERFORMANCE
# =========================
with tab12:
    st.subheader("📊 Performans Takibi")
    snap = load_snapshots()
    if snap.empty:
        st.info("Henüz performans geçmişi yok. Bugünkü kayıt oluşturuldu; tekrar açtığında grafik oluşmaya başlayacak.")
    else:
        st.dataframe(snap, width="stretch")
        plot_df = snap.set_index("snapshot_date")[["total_value", "pnl"]]
        st.line_chart(plot_df, width="stretch")
