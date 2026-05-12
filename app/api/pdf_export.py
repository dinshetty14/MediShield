"""PDF Audit Report Generator for MediShield Cases."""

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_case_report(case: Any) -> bytes:
    """Generate a PDF audit report for a case.

    Args:
        case: Case ORM object with all agent outputs

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        textColor=colors.darkblue,
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.darkblue,
    )
    normal_style = styles['Normal']
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
    )

    # Header
    story.append(Paragraph("MediShield Insurance", title_style))
    story.append(Paragraph("Case Audit Report", styles['Heading2']))
    story.append(Spacer(1, 10))

    # Case Summary Table
    summary_data = [
        ["Case ID", case.id],
        ["Status", case.status.upper() if case.status else "N/A"],
        ["Document Type", case.doc_type or "Unknown"],
        ["Filename", case.filename or "N/A"],
        ["Created", case.created_at.strftime("%Y-%m-%d %H:%M:%S") if case.created_at else "N/A"],
        ["Processing Time", f"{case.processing_time_seconds:.2f}s" if case.processing_time_seconds else "N/A"],
    ]

    summary_table = Table(summary_data, colWidths=[2 * inch, 4.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Final Decision Section
    story.append(Paragraph("Final Decision", heading_style))

    decision_color = colors.green
    if case.decision:
        decision = case.decision.upper()
        if decision == "REJECT":
            decision_color = colors.red
        elif decision == "ESCALATE":
            decision_color = colors.orange
    else:
        decision = "PENDING"

    decision_style = ParagraphStyle(
        'Decision',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=decision_color,
        alignment=1,  # Center
    )
    story.append(Paragraph(decision, decision_style))

    if case.decision_confidence:
        confidence_text = f"Confidence: {case.decision_confidence:.0%}"
        story.append(Paragraph(confidence_text, ParagraphStyle(
            'Confidence', parent=normal_style, alignment=1, fontSize=12
        )))

    if case.decision_justification:
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"<b>Justification:</b> {case.decision_justification}", normal_style))

    story.append(Spacer(1, 20))

    # Classification Section
    story.append(Paragraph("Classification", heading_style))
    if case.classifier_output:
        import json
        classifier_data = json.loads(case.classifier_output) if isinstance(case.classifier_output, str) else case.classifier_output
        class_table_data = [
            ["Document Type", classifier_data.get("doc_type", "Unknown")],
            ["Confidence", f"{classifier_data.get('confidence', 0):.0%}"],
            ["Routing Tags", ", ".join(classifier_data.get("routing_tags", []))],
        ]
        class_table = Table(class_table_data, colWidths=[2 * inch, 4.5 * inch])
        class_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(class_table)
    else:
        story.append(Paragraph("No classification data available", normal_style))

    # KYC Section (if applicable)
    if case.kyc_output:
        story.append(Spacer(1, 15))
        story.append(Paragraph("KYC Verification", heading_style))
        import json
        kyc_data = json.loads(case.kyc_output) if isinstance(case.kyc_output, str) else case.kyc_output

        kyc_passed = kyc_data.get("kyc_passed", False)
        status_color = colors.green if kyc_passed else colors.red
        status_text = "PASSED" if kyc_passed else "FAILED"

        kyc_table_data = [
            ["Status", status_text],
            ["Confidence", f"{kyc_data.get('confidence', 0):.0%}"],
            ["Document Type", kyc_data.get("document_type", "N/A")],
            ["Expiry Status", kyc_data.get("expiry_status", "N/A")],
        ]

        if kyc_data.get("flags"):
            kyc_table_data.append(["Flags", ", ".join(kyc_data["flags"])])

        kyc_table = Table(kyc_table_data, colWidths=[2 * inch, 4.5 * inch])
        kyc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, 0), (1, 0), status_color),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(kyc_table)

    # Claims Section (if applicable)
    if case.claims_output:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Claims Extraction", heading_style))
        import json
        claims_data = json.loads(case.claims_output) if isinstance(case.claims_output, str) else case.claims_output

        claims_table_data = [
            ["Claim Amount", f"{claims_data.get('currency', 'INR')} {claims_data.get('claim_amount', 'N/A')}"],
            ["Provider", claims_data.get("provider_name", "N/A")],
            ["Service Date", claims_data.get("service_date", "N/A")],
            ["ICD-10 Codes", ", ".join(claims_data.get("icd_10_codes", [])) or "None"],
            ["CPT Codes", ", ".join(claims_data.get("cpt_codes", [])) or "None"],
            ["Schema Valid", "Yes" if claims_data.get("schema_valid", False) else "No"],
            ["Confidence", f"{claims_data.get('confidence', 0):.0%}"],
        ]

        claims_table = Table(claims_table_data, colWidths=[2 * inch, 4.5 * inch])
        claims_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(claims_table)

    # Policy Section (if applicable)
    if case.policy_output:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Policy Coverage", heading_style))
        import json
        policy_data = json.loads(case.policy_output) if isinstance(case.policy_output, str) else case.policy_output

        covered = policy_data.get("covered", False)
        coverage_color = colors.green if covered else colors.red

        policy_table_data = [
            ["Covered", "Yes" if covered else "No"],
            ["Coverage %", f"{policy_data.get('coverage_percentage', 0)}%"],
            ["Policy Clause", policy_data.get("policy_clause", "N/A")[:80] + "..." if policy_data.get("policy_clause", "") and len(policy_data.get("policy_clause", "")) > 80 else policy_data.get("policy_clause", "N/A")],
            ["Confidence", f"{policy_data.get('confidence', 0):.0%}"],
        ]

        if policy_data.get("exclusions"):
            policy_table_data.append(["Exclusions", ", ".join(policy_data["exclusions"][:3])])

        policy_table = Table(policy_table_data, colWidths=[2 * inch, 4.5 * inch])
        policy_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, 0), (1, 0), coverage_color),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(policy_table)

    # Fraud Section (if applicable)
    if case.fraud_output:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Fraud Detection", heading_style))
        import json
        fraud_data = json.loads(case.fraud_output) if isinstance(case.fraud_output, str) else case.fraud_output

        risk_level = fraud_data.get("risk_level", "LOW")
        risk_color = colors.green
        if risk_level == "HIGH":
            risk_color = colors.red
        elif risk_level == "MEDIUM":
            risk_color = colors.orange

        fraud_table_data = [
            ["Risk Level", risk_level],
            ["Fraud Score", f"{fraud_data.get('fraud_score', 0):.2f}"],
            ["Duplicate Detected", "Yes" if fraud_data.get("duplicate_claim_detected", False) else "No"],
            ["Frequency Anomaly", "Yes" if fraud_data.get("frequency_anomaly", False) else "No"],
        ]

        if fraud_data.get("anomalies"):
            for i, anomaly in enumerate(fraud_data["anomalies"][:3]):
                fraud_table_data.append([f"Anomaly {i+1}", anomaly[:60] + "..." if len(anomaly) > 60 else anomaly])

        fraud_table = Table(fraud_table_data, colWidths=[2 * inch, 4.5 * inch])
        fraud_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, 0), (1, 0), risk_color),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(fraud_table)

    # Override Section (if applicable)
    if case.override_by:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Human Override", heading_style))
        override_table_data = [
            ["Override By", case.override_by],
            ["New Decision", case.override_decision.upper() if case.override_decision else "N/A"],
            ["Reason", case.override_reason or "No reason provided"],
        ]
        override_table = Table(override_table_data, colWidths=[2 * inch, 4.5 * inch])
        override_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightyellow),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(override_table)

    # Footer
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by MediShield AI System",
        small_style
    ))
    story.append(Paragraph(
        "This is an automated audit report. For questions, contact operations@medishield.example.com",
        small_style
    ))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
