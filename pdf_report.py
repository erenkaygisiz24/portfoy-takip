from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _register_font():
    try:
        pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
        return "Arial"
    except Exception:
        return "Helvetica"


def create_portfolio_pdf(valued_df, prices_df=None):
    buffer = BytesIO()
    font = _register_font()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    styles["Title"].fontName = font
    styles["Heading2"].fontName = font
    styles["Normal"].fontName = font

    story = []

    story.append(Paragraph("Finansal Portföy Raporu", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            f"Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 18))

    total_cost = float(valued_df["maliyet_degeri"].sum())
    total_value = float(valued_df["guncel_deger"].sum())
    pnl = total_value - total_cost
    pnl_pct = pnl / total_cost if total_cost > 0 else 0

    summary_data = [
        ["Toplam Maliyet", f"{total_cost:,.2f} TL"],
        ["Güncel Değer", f"{total_value:,.2f} TL"],
        ["Kar/Zarar", f"{pnl:+,.2f} TL"],
        ["Getiri", f"{pnl_pct:+.2%}"],
    ]

    summary_table = Table(summary_data, colWidths=[7 * cm, 7 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story.append(Paragraph("Portföy Özeti", styles["Heading2"]))
    story.append(summary_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Varlık Detayları", styles["Heading2"]))

    table_data = [
        [
            "Kod",
            "Tür",
            "Adet",
            "Maliyet",
            "Güncel Fiyat",
            "Güncel Değer",
            "K/Z",
            "Kaynak",
        ]
    ]

    for _, row in valued_df.iterrows():
        table_data.append(
            [
                str(row.get("kod_adi", "")),
                str(row.get("tur", "")),
                f"{float(row.get('adet', 0)):,.2f}",
                f"{float(row.get('maliyet', 0)):,.2f}",
                f"{float(row.get('price', 0)):,.2f}",
                f"{float(row.get('guncel_deger', 0)):,.2f}",
                f"{float(row.get('kar_zarar', 0)):+,.2f}",
                str(row.get("source", ""))[:18],
            ]
        )

    asset_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[2 * cm, 2.2 * cm, 1.8 * cm, 2 * cm, 2.2 * cm, 2.4 * cm, 2.2 * cm, 3 * cm],
    )

    asset_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(asset_table)
    story.append(Spacer(1, 18))

    if prices_df is not None and not prices_df.empty:
        story.append(Paragraph("Fiyat Kaynakları", styles["Heading2"]))

        price_data = [["Sembol", "Tür", "Fiyat", "Tarih", "Kaynak", "Durum"]]

        for _, row in prices_df.iterrows():
            price_data.append(
                [
                    str(row.get("symbol", "")),
                    str(row.get("asset_type", "")),
                    f"{float(row.get('price', 0)):,.4f}",
                    str(row.get("price_date", "")),
                    str(row.get("source", ""))[:20],
                    str(row.get("status", ""))[:20],
                ]
            )

        price_table = Table(
            price_data,
            repeatRows=1,
            colWidths=[2 * cm, 2.5 * cm, 2.2 * cm, 2.2 * cm, 3.5 * cm, 3.5 * cm],
        )

        price_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        story.append(price_table)

    doc.build(story)

    buffer.seek(0)
    return buffer