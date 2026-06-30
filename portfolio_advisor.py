import os
from google import genai


def calculate_risk_score(valued):
    score = 0
    reasons = []

    if valued.empty:
        return 0, ["Portföy boş."]

    max_weight = valued["portfoy_orani"].max()

    if max_weight > 0.70:
        score += 35
        reasons.append("Tek varlık portföyün %70'inden fazla.")

    if max_weight > 0.40:
        score += 20
        reasons.append("Portföyde yoğunlaşma riski var.")

    if (valued["tur"] == "Fon").mean() > 0.80:
        score += 10
        reasons.append("Portföy fon ağırlıklı.")

    if (valued["kar_zarar_pct"] < -0.05).any():
        score += 15
        reasons.append("%5'ten fazla zararda pozisyon var.")

    if (valued["hedef_sapma"].abs() > 0.20).any():
        score += 20
        reasons.append("Hedef portföy oranlarından sapma var.")

    score = min(score, 100)

    if not reasons:
        reasons.append("Belirgin yüksek risk sinyali yok.")

    return score, reasons


def generate_alerts(valued):
    alerts = []

    if valued.empty:
        return ["Portföy boş."]

    for _, row in valued.iterrows():
        kod = row["kod_adi"]

        if row["kar_zarar_pct"] >= 0.10:
            alerts.append(f"🟢 {kod}: %10 üzeri kârda.")

        if row["kar_zarar_pct"] <= -0.05:
            alerts.append(f"🔴 {kod}: %5 üzeri zararda.")

        if abs(row["hedef_sapma"]) >= 0.20:
            alerts.append(f"⚠️ {kod}: hedef portföy oranından ciddi sapmış.")

        if row.get("hedef_fiyat", 0) > 0 and row["price"] >= row["hedef_fiyat"]:
            alerts.append(f"🎯 {kod}: hedef fiyata ulaşmış.")

    if not alerts:
        alerts.append("Bugün kritik alarm yok.")

    return alerts


def fallback_portfolio_commentary(valued, risk_score, reasons):
    total_value = valued["guncel_deger"].sum()
    top = valued.sort_values("portfoy_orani", ascending=False).iloc[0]

    return f"""
Portföy toplam değeri yaklaşık {total_value:,.2f} TL.

En büyük pozisyon {top['kod_adi']} ve portföyün {top['portfoy_orani']:.2%} kısmını oluşturuyor.

Risk skoru: {risk_score}/100.

Öne çıkan riskler:
- """ + "\n- ".join(reasons) + """

Genel yorum:
Portföyde yoğunlaşma varsa yeniden dengeleme değerlendirilebilir.
Bu yorum yatırım tavsiyesi değildir.
"""


def ai_portfolio_advisor(valued):
    risk_score, reasons = calculate_risk_score(valued)

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return fallback_portfolio_commentary(valued, risk_score, reasons)

    try:
        client = genai.Client(api_key=api_key)

        rows = []
        for _, r in valued.iterrows():
            rows.append(
                f"{r['kod_adi']} | Tür: {r['tur']} | Oran: {r['portfoy_orani']:.2%} | "
                f"K/Z: {r['kar_zarar_pct']:.2%} | Sapma: {r['hedef_sapma']:.2%}"
            )

        prompt = f"""
Sen profesyonel bir portföy analiz asistanısın.

Aşağıdaki portföyü kısa ve net analiz et.

Portföy:
{chr(10).join(rows)}

Risk skoru: {risk_score}/100
Risk nedenleri:
{chr(10).join("- " + x for x in reasons)}

Kurallar:
- Yatırım tavsiyesi verme.
- Al/sat emri verme.
- En fazla 150 kelime yaz.
- Güçlü yönler, riskler ve izlenecek noktaları belirt.

Format:
Genel Değerlendirme:
Riskler:
İzlenecek Noktalar:
"""

        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=prompt,
        )

        return response.text.strip()

    except Exception:
        return fallback_portfolio_commentary(valued, risk_score, reasons)