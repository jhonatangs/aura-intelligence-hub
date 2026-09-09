"""Synthetic B2B partner invoice PDF generator using ReportLab.

Generates realistic commercial invoice PDFs in multiple distinct ERP formats
(Enterprise SAP, Legacy TOTVS, Modern DANFE/Cloud) containing Aura SKUs, batch
identifiers, partner metadata, and fiscal amounts.
"""

from datetime import date
from pathlib import Path
from typing import Literal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.ingestion.models.invoice import (
    InvoiceItem,
    InvoiceMetadata,
    RawInvoicePayload,
)

LayoutType = Literal["enterprise_sap", "legacy_totvs", "modern_danfe"]
AVAILABLE_LAYOUTS: list[LayoutType] = ["enterprise_sap", "legacy_totvs", "modern_danfe"]


def _build_sap_layout(
    story: list[object],
    payload: RawInvoicePayload,
    styles: dict[str, ParagraphStyle],
) -> None:
    """Construct corporate SAP S/4HANA invoice layout."""
    title = Paragraph(
        "<b>COMMERCIAL TAX INVOICE — SAP S/4HANA BILLING EXTRACT</b>",
        styles["Title"],
    )
    story.append(title)
    story.append(Spacer(1, 10))

    meta_data = [
        [
            Paragraph(
                f"<b>Distributor ID:</b> {payload.metadata.partner_id}<br/>"
                f"<b>Partner CNPJ:</b> {payload.metadata.partner_cnpj}<br/>"
                f"<b>Issuer Status:</b> Certified Partner Hub",
                styles["Normal"],
            ),
            Paragraph(
                f"<b>Invoice Number:</b> {payload.metadata.invoice_number}<br/>"
                f"<b>Issue Date:</b> {payload.metadata.issue_date}<br/>"
                "<b>Currency / Terms:</b> BRL / Net 30 Days",
                styles["Normal"],
            ),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 15))

    items_data = [
        ["SKU", "Description", "Batch", "Qty", "Unit Price (R$)", "Total (R$)"],
    ]
    for item in payload.items:
        items_data.append(
            [
                item.sku,
                item.description,
                item.batch_number,
                str(item.quantity),
                f"{item.unit_price:.2f}",
                f"{item.total_price:.2f}",
            ]
        )

    items_table = Table(items_data, colWidths=[90, 160, 85, 45, 70, 70])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 12))

    totals_data = [
        ["Subtotal:", f"R$ {payload.subtotal:.2f}"],
        ["Applicable Tax (ICMS/IPI):", f"R$ {payload.tax_amount:.2f}"],
        ["Total Payable Amount:", f"R$ {payload.total_amount:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[380, 140])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#1E3A8A")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 2), (1, 2), 1.5, colors.HexColor("#1E3A8A")),
            ]
        )
    )
    story.append(totals_table)


def _build_totvs_layout(
    story: list[object],
    payload: RawInvoicePayload,
    styles: dict[str, ParagraphStyle],
) -> None:
    """Construct dense legacy TOTVS Protheus ERP invoice layout."""
    title = Paragraph(
        "<b>SISTEMA INTEGRADO PROTHEUS / TOTVS ERP — NOTA FISCAL FATURA</b>",
        styles["Title"],
    )
    story.append(title)
    story.append(Spacer(1, 8))

    border_data = [
        [
            Paragraph(
                f"<b>EMITENTE / PARCEIRO:</b> {payload.metadata.partner_id}<br/>"
                f"<b>CNPJ:</b> {payload.metadata.partner_cnpj}<br/>"
                "<b>REGIME TRIBUTARIO:</b> LUCRO REAL",
                styles["Normal"],
            ),
            Paragraph(
                f"<b>NF-e NUMERO:</b> {payload.metadata.invoice_number}<br/>"
                f"<b>DATA EMISSAO:</b> {payload.metadata.issue_date}<br/>"
                "<b>CONDICAO PGTO:</b> A PRAZO 28 DDL",
                styles["Normal"],
            ),
        ]
    ]
    border_table = Table(border_data, colWidths=[260, 260])
    border_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.5, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(border_table)
    story.append(Spacer(1, 10))

    items_data = [
        ["CODIGO SKU", "DISCRIMINACAO", "LOTE", "QTD", "VL UNIT", "VL TOTAL"],
    ]
    for item in payload.items:
        items_data.append(
            [
                item.sku,
                item.description,
                item.batch_number,
                str(item.quantity),
                f"{item.unit_price:.2f}",
                f"{item.total_price:.2f}",
            ]
        )

    items_table = Table(items_data, colWidths=[95, 170, 75, 45, 65, 70])
    items_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 10))

    summary_data = [
        [
            "BASE DE CALCULO:",
            f"{payload.subtotal:.2f}",
            "TOTAL PRODUTOS:",
            f"{payload.subtotal:.2f}",
        ],
        [
            "VALOR DO IMPOSTO:",
            f"{payload.tax_amount:.2f}",
            "VALOR TOTAL DA NOTA:",
            f"{payload.total_amount:.2f}",
        ],
    ]
    summary_table = Table(summary_data, colWidths=[130, 130, 130, 130])
    summary_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary_table)


def _build_danfe_layout(
    story: list[object],
    payload: RawInvoicePayload,
    styles: dict[str, ParagraphStyle],
) -> None:
    """Construct modern DANFE/Cloud distributor invoice layout."""
    title = Paragraph(
        "<b>DANFE SIMPLIFICADA — AURA CLOUD HUB DISTRIBUICAO</b>",
        styles["Title"],
    )
    story.append(title)
    story.append(Spacer(1, 10))

    badge_data = [
        [
            Paragraph(
                f"<font size=11><b>{payload.metadata.partner_id}</b></font><br/>"
                f"<font color='#4B5563'>CNPJ: {payload.metadata.partner_cnpj}</font><br/>"
                "<font color='#047857'><b>Status: Ingestao Autorizada</b></font>",
                styles["Normal"],
            ),
            Paragraph(
                f"<font size=11><b>NF-e: #{payload.metadata.invoice_number}</b></font><br/>"
                f"<font color='#4B5563'>Emissao: {payload.metadata.issue_date}</font><br/>"
                "<font color='#1F2937'>Operacao: Venda B2B Sell-Out</font>",
                styles["Normal"],
            ),
        ]
    ]
    badge_table = Table(badge_data, colWidths=[260, 260])
    badge_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF5")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#A7F3D0")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(badge_table)
    story.append(Spacer(1, 15))

    items_data = [
        ["SKU", "Produto", "Lote", "Quantidade", "Valor Unit.", "Total Item"],
    ]
    for item in payload.items:
        items_data.append(
            [
                item.sku,
                item.description,
                item.batch_number,
                str(item.quantity),
                f"R$ {item.unit_price:.2f}",
                f"R$ {item.total_price:.2f}",
            ]
        )

    items_table = Table(items_data, colWidths=[90, 160, 80, 55, 65, 70])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#065F46")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 15))

    totals_data = [
        ["Subtotal Bruto:", f"R$ {payload.subtotal:.2f}"],
        ["Impostos Retidos:", f"R$ {payload.tax_amount:.2f}"],
        ["Valor Total Faturado:", f"R$ {payload.total_amount:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[380, 140])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTSIZE", (0, 2), (-1, 2), 11),
                ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#065F46")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(totals_table)


def generate_invoice_pdf(
    payload: RawInvoicePayload,
    output_path: Path | str,
    layout: LayoutType = "enterprise_sap",
) -> Path:
    """Generate a formatted PDF invoice matching a specific ERP layout.

    Args:
        payload: Strongly-typed RawInvoicePayload data contract.
        output_path: File system destination path for the PDF.
        layout: ERP layout type ('enterprise_sap', 'legacy_totvs', 'modern_danfe').

    Returns:
        Path: Destination path to the written PDF.

    Raises:
        ValueError: If layout is unsupported.
    """
    if layout not in AVAILABLE_LAYOUTS:
        raise ValueError(
            f"Unsupported layout '{layout}'. Choose from: {', '.join(AVAILABLE_LAYOUTS)}"
        )

    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(target),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    base_styles = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {
        "Title": ParagraphStyle(
            "InvoiceTitle",
            parent=base_styles["Title"],
            fontSize=11,
            leading=14,
            alignment=1,
            textColor=colors.HexColor("#1F2937"),
        ),
        "Normal": ParagraphStyle(
            "InvoiceNormal",
            parent=base_styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#374151"),
        ),
    }

    story: list[object] = []
    if layout == "enterprise_sap":
        _build_sap_layout(story, payload, styles)
    elif layout == "legacy_totvs":
        _build_totvs_layout(story, payload, styles)
    elif layout == "modern_danfe":
        _build_danfe_layout(story, payload, styles)

    doc.build(story)
    return target


def generate_sample_invoices(
    output_dir: Path | str,
    count: int = 3,
) -> list[Path]:
    """Generate a deterministic batch of sample PDFs covering distinct layouts and Aura SKUs.

    Args:
        output_dir: Target directory where generated PDFs will be stored.
        count: Number of sample invoices to generate (defaults to 3).

    Returns:
        list[Path]: Paths to generated PDF invoices.
    """
    dest = Path(output_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    sample_configs: list[dict[str, object]] = [
        {
            "layout": "enterprise_sap",
            "filename": "invoice_sap_dist_sp.pdf",
            "metadata": InvoiceMetadata(
                invoice_number="SAP-2026-9011",
                partner_id="PARTNER_DIST_SP_01",
                partner_cnpj="00.000.000/0001-91",
                issue_date=date(2026, 9, 1),
            ),
            "items": [
                InvoiceItem(
                    sku="AURA_250ML",
                    description="Aura Original Energy Drink 250ml Can",
                    quantity=500,
                    unit_price=4.20,
                    total_price=2100.00,
                    batch_number="BATCH-SAP-2026A",
                ),
                InvoiceItem(
                    sku="AURA_ZERO_250ML",
                    description="Aura Zero Sugar Energy Drink 250ml Can",
                    quantity=250,
                    unit_price=4.50,
                    total_price=1125.00,
                    batch_number="BATCH-SAP-2026Z",
                ),
            ],
            "subtotal": 3225.00,
            "tax": 387.00,
            "total": 3612.00,
        },
        {
            "layout": "legacy_totvs",
            "filename": "invoice_totvs_dist_rj.pdf",
            "metadata": InvoiceMetadata(
                invoice_number="NF-TOTVS-44812",
                partner_id="PARTNER_DIST_RJ_02",
                partner_cnpj="11.222.333/0001-81",
                issue_date=date(2026, 9, 3),
            ),
            "items": [
                InvoiceItem(
                    sku="AURA_TROPICAL_473ML",
                    description="Aura Tropical Fusion Energy 473ml",
                    quantity=300,
                    unit_price=6.50,
                    total_price=1950.00,
                    batch_number="BATCH-TOTVS-TR01",
                ),
                InvoiceItem(
                    sku="AURA_250ML",
                    description="Aura Original Energy Drink 250ml Can",
                    quantity=400,
                    unit_price=4.15,
                    total_price=1660.00,
                    batch_number="BATCH-TOTVS-OR02",
                ),
            ],
            "subtotal": 3610.00,
            "tax": 433.20,
            "total": 4043.20,
        },
        {
            "layout": "modern_danfe",
            "filename": "invoice_danfe_dist_mg.pdf",
            "metadata": InvoiceMetadata(
                invoice_number="DANFE-2026-8819",
                partner_id="PARTNER_DIST_MG_03",
                partner_cnpj="33.000.167/0001-01",
                issue_date=date(2026, 9, 5),
            ),
            "items": [
                InvoiceItem(
                    sku="AURA_ZERO_250ML",
                    description="Aura Zero Sugar Energy Drink 250ml Can",
                    quantity=600,
                    unit_price=4.45,
                    total_price=2670.00,
                    batch_number="BATCH-DANFE-Z09",
                ),
                InvoiceItem(
                    sku="AURA_TROPICAL_473ML",
                    description="Aura Tropical Fusion Energy 473ml",
                    quantity=350,
                    unit_price=6.40,
                    total_price=2240.00,
                    batch_number="BATCH-DANFE-TR03",
                ),
            ],
            "subtotal": 4910.00,
            "tax": 589.20,
            "total": 5499.20,
        },
    ]

    generated: list[Path] = []
    for i in range(min(count, len(sample_configs))):
        cfg = sample_configs[i]
        payload = RawInvoicePayload(
            metadata=cfg["metadata"],  # type: ignore[arg-type]
            items=cfg["items"],  # type: ignore[arg-type]
            subtotal=float(cfg["subtotal"]),  # type: ignore[arg-type]
            tax_amount=float(cfg["tax"]),  # type: ignore[arg-type]
            total_amount=float(cfg["total"]),  # type: ignore[arg-type]
        )
        file_path = dest / str(cfg["filename"])
        layout_name = cfg["layout"]  # type: ignore[assignment]
        generate_invoice_pdf(payload, file_path, layout=layout_name)
        generated.append(file_path)

    return generated
