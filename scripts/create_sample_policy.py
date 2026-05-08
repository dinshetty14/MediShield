#!/usr/bin/env python
"""Create a sample health insurance policy PDF for testing."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


def create_sample_policy():
    """Create a sample health insurance policy PDF."""
    policies_dir = Path(__file__).parent.parent / "policies"
    policies_dir.mkdir(exist_ok=True)

    output_path = policies_dir / "MediShield_Gold_Policy_2024.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
    )
    body_style = styles['Normal']

    story = []

    # Title
    story.append(Paragraph("MediShield Gold Health Insurance Policy", title_style))
    story.append(Paragraph("Policy Document 2024", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))

    # Section 1: Coverage Overview
    story.append(Paragraph("1. Coverage Overview", heading_style))
    story.append(Paragraph("""
    This MediShield Gold Policy provides comprehensive health insurance coverage for hospitalization,
    medical treatments, surgeries, and related expenses. The policy covers the insured member and
    eligible dependents as listed in the policy schedule.
    """, body_style))
    story.append(Spacer(1, 0.2*inch))

    # Section 2: Covered Procedures
    story.append(Paragraph("2. Covered Medical Procedures", heading_style))
    story.append(Paragraph("""
    The following medical procedures and treatments are covered under this policy:
    """, body_style))

    covered_items = [
        ["Category", "Coverage", "Sub-Limit"],
        ["Hospitalization (ICD-10: A00-Z99)", "100%", "Up to Sum Insured"],
        ["Surgical Procedures (CPT: 10000-69999)", "100%", "Up to Sum Insured"],
        ["Diagnostic Tests (CPT: 70000-89999)", "100%", "Rs. 50,000 per year"],
        ["Emergency Room Visits", "100%", "Rs. 25,000 per visit"],
        ["ICU Charges", "100%", "Rs. 10,000 per day"],
        ["Room Rent", "100%", "Rs. 5,000 per day"],
        ["Pre-hospitalization (30 days)", "100%", "Included"],
        ["Post-hospitalization (60 days)", "100%", "Included"],
    ]

    table = Table(covered_items, colWidths=[2.5*inch, 1.5*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*inch))

    # Section 3: Specific Disease Coverage
    story.append(Paragraph("3. Specific Disease Coverage", heading_style))
    story.append(Paragraph("""
    <b>Cardiovascular Conditions (ICD-10: I00-I99)</b><br/>
    Full coverage for heart-related conditions including myocardial infarction (I21),
    angina pectoris (I20), heart failure (I50), and cardiac arrhythmias (I49).
    Cardiac surgeries including CABG, angioplasty, and pacemaker implantation are covered.
    """, body_style))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("""
    <b>Respiratory Conditions (ICD-10: J00-J99)</b><br/>
    Coverage for pneumonia (J18), bronchitis (J20-J21), asthma (J45), and COPD (J44).
    Includes ventilator support and oxygen therapy during hospitalization.
    """, body_style))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("""
    <b>Digestive System Conditions (ICD-10: K00-K95)</b><br/>
    Coverage for appendicitis (K35-K37), cholecystitis (K81), gastric ulcers (K25-K28),
    and intestinal conditions requiring surgical intervention.
    """, body_style))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("""
    <b>Orthopedic Conditions (ICD-10: M00-M99, S00-T98)</b><br/>
    Coverage for fractures, joint replacements, spinal surgeries, and trauma care.
    Includes physiotherapy during hospitalization.
    """, body_style))
    story.append(Spacer(1, 0.3*inch))

    # Section 4: Exclusions
    story.append(Paragraph("4. Exclusions", heading_style))
    story.append(Paragraph("""
    The following conditions and treatments are NOT covered under this policy:
    """, body_style))

    exclusions = [
        "Cosmetic or aesthetic procedures unless medically necessary",
        "Self-inflicted injuries or injuries from hazardous activities",
        "Treatment for alcohol or drug abuse",
        "Dental treatments (unless due to accident)",
        "Vision correction surgery (LASIK, PRK)",
        "Infertility treatments and IVF procedures",
        "Experimental or unproven treatments",
        "War, terrorism, or nuclear-related injuries",
        "Alternative medicine (Ayurveda, Homeopathy) unless approved",
    ]

    for excl in exclusions:
        story.append(Paragraph(f"• {excl}", body_style))
    story.append(Spacer(1, 0.3*inch))

    # Section 5: Waiting Periods
    story.append(Paragraph("5. Waiting Periods", heading_style))
    story.append(Paragraph("""
    <b>Initial Waiting Period:</b> 30 days from policy start date for all non-emergency claims.<br/><br/>
    <b>Pre-existing Conditions:</b> 48 months waiting period for conditions existing before policy inception.<br/><br/>
    <b>Specific Conditions (24 months):</b> Cataract, hernia, fistula, piles, sinusitis, joint replacement,
    kidney stones, gallbladder stones.<br/><br/>
    <b>Maternity:</b> 9 months waiting period for normal delivery, 12 months for C-section.
    """, body_style))
    story.append(Spacer(1, 0.3*inch))

    # Section 6: Claim Process
    story.append(Paragraph("6. Claim Process", heading_style))
    story.append(Paragraph("""
    <b>Cashless Claims:</b> Available at network hospitals. Pre-authorization required for planned hospitalization.
    Show your health card at the hospital TPA desk.<br/><br/>
    <b>Reimbursement Claims:</b> Submit claim form within 15 days of discharge with original bills,
    discharge summary, and medical reports. Processing time: 7-14 working days.<br/><br/>
    <b>Required Documents:</b> Claim form, hospital bills (original), discharge summary,
    investigation reports, prescription copies, KYC documents.
    """, body_style))
    story.append(Spacer(1, 0.3*inch))

    # Section 7: Co-payment
    story.append(Paragraph("7. Co-payment and Deductibles", heading_style))
    story.append(Paragraph("""
    <b>Co-payment:</b> Nil for policyholders below 60 years. 10% co-payment for policyholders aged 60-70 years.
    20% co-payment for policyholders above 70 years.<br/><br/>
    <b>Deductible:</b> No deductible applies to this Gold policy variant.<br/><br/>
    <b>Room Rent Capping:</b> If actual room rent exceeds Rs. 5,000/day, proportionate deduction applies
    to all other charges.
    """, body_style))

    # Build PDF
    doc.build(story)
    print(f"Created sample policy: {output_path}")
    return output_path


if __name__ == "__main__":
    create_sample_policy()
