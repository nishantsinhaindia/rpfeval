"""Generate 4 fictional supplier RFP responses (synthetic data only) into data/samples/."""
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "samples")
RFP = "Customer Service Platform Modernisation for Contoso Retail (fictional)"

SUPPLIERS = {
    "Apex_Systems": dict(
        summary="Apex Systems proposes a cloud-native, microservices-based customer service platform designed for 5x peak load with full API-first integration to the existing ERP, CRM and order management systems.",
        solution="Event-driven architecture on Kubernetes with an API gateway, 42 pre-built connectors (SAP, Salesforce, ServiceNow), autoscaling, multi-region active-active deployment and 99.95% availability target. Load tested to 20,000 concurrent agents.",
        timeline=[("Discovery & design", "Weeks 1-4"), ("Core build", "Weeks 5-14"), ("Integration & testing", "Weeks 15-20"), ("Go-live & hypercare", "Weeks 21-24")],
        team="Team of 14: solution architect, 2 security engineers, 8 developers, 2 QA, 1 delivery manager.",
        prices=[("Licences (3 yrs)", "$780,000"), ("Implementation", "$420,000"), ("Support (3 yrs)", "$150,000"), ("Total", "$1,350,000")],
        assumptions="Prices exclude client-side hardware; 10% contingency recommended.",
        security="ISO 27001 and SOC 2 Type II certified; encryption AES-256 at rest and TLS 1.3 in transit; GDPR DPA provided; quarterly penetration tests; immutable audit logs retained 7 years; role-based access with SSO/MFA.",
        risks="Risk register with 12 tracked risks; integration risk mitigated by connector library.",
        support="24x7 support with 1-hour P1 response; named technical account manager.",
        experience="11 similar deployments in retail; references: Northwind Stores (fictional), Fabrikam Outlets (fictional).",
    ),
    "BrightPath_Tech": dict(
        summary="BrightPath Tech offers a fast, low-cost deployment of our SaaS help-desk product to get Contoso live quickly.",
        solution="Standard SaaS help-desk with ticketing, chat and email channels. Integrations can be built on request using our REST API.",
        timeline=[("Setup", "Weeks 1-2"), ("Configuration", "Weeks 3-6"), ("Go-live", "Week 8")],
        team="Team of 4 consultants.",
        prices=[("Subscription (3 yrs)", "$310,000"), ("Implementation", "$90,000"), ("Total", "$400,000")],
        assumptions="Price assumes standard configuration only; custom integrations billed separately at $150/hour.",
        security="Data is hosted in a secure cloud. We follow industry best practices.",
        risks="Not provided.",
        support="Email support during business hours (9am-5pm).",
        experience="Company founded in 2022; 2 small customers to date; references available on request.",
    ),
    "NexaWorks": dict(
        summary="NexaWorks proposes a balanced, phased modernisation with a strong delivery and support model focused on adoption.",
        solution="Configurable omnichannel platform with native CRM integration and middleware for ERP; horizontal scaling to 3x current volume.",
        timeline=[("Mobilise & discovery", "Weeks 1-3"), ("Pilot (1 region)", "Weeks 4-10"), ("Phased rollout (3 waves)", "Weeks 11-20"), ("Stabilise & handover", "Weeks 21-22")],
        team="Team of 10 with dedicated change manager, trainer, PMO lead; RACI and weekly steering committee defined. Milestones tied to acceptance criteria and payment gates.",
        prices=[("Licences (3 yrs)", "$520,000"), ("Implementation", "$300,000"), ("Support (3 yrs)", "$130,000"), ("Total", "$950,000")],
        assumptions="Fixed price for scope described; change requests via agreed rate card.",
        security="SOC 2 Type II certified; encryption at rest and in transit; annual penetration test; GDPR compliant processing.",
        risks="Detailed risk plan with owners, mitigations and contingency for each phase; rollback plan for each wave.",
        support="24x7 follow-the-sun support, 30-minute P1 response, 99.9% SLA with service credits, dedicated customer success manager, quarterly business reviews.",
        experience="7 similar programmes; references: Tailspin Retail (fictional), Wide World Importers (fictional).",
    ),
    "Orbit_Digital": dict(
        summary="Orbit Digital brings 20 years of customer-service transformation experience across 30+ enterprise clients.",
        solution="Our proven platform will be integrated with Contoso systems as appropriate. Integration details will be finalised during discovery.",
        timeline=[("Discovery", "Weeks 1-6"), ("Build & integrate", "Weeks 7-22"), ("Go-live", "Week 26")],
        team="Team of 12 led by a senior programme director.",
        prices=[("Licences (3 yrs)", "$600,000"), ("Implementation", "$250,000"), ("Support (3 yrs)", "$120,000"), ("Total", "$970,000")],
        assumptions="Integration effort is estimated and may change after discovery.",
        security="ISO 27001 certified; encryption in transit; GDPR compliant.",
        risks="Standard project risk management applies.",
        support="24x7 support with 2-hour P1 response.",
        experience="34 similar projects; references: Adventure Works (fictional), Litware Retail (fictional), Proseware Group (fictional) — all available for calls.",
    ),
}


def build(name: str, d: dict) -> str:
    ss = getSampleStyleSheet()
    H, B = ss["Heading2"], ss["BodyText"]
    path = os.path.join(OUT, f"{name}.pdf")
    title = name.replace("_", " ")
    story = [Paragraph(f"{title} — RFP Response", ss["Title"]), Paragraph(RFP, B), Spacer(1, 12),
             Paragraph("1. Executive Summary & Understanding of Requirement", H), Paragraph(d["summary"], B),
             Paragraph("2. Proposed Solution & Implementation Approach", H), Paragraph(d["solution"], B),
             Paragraph("3. Timeline, Team Structure & Milestones", H),
             Table([("Milestone", "Timing")] + d["timeline"]), Spacer(1, 6), Paragraph(d["team"], B),
             PageBreak(),
             Paragraph("4. Pricing", H), Table([("Item", "Price")] + d["prices"]), Spacer(1, 6),
             Paragraph("Assumptions: " + d["assumptions"], B),
             Paragraph("5. Security, Compliance & Risk Controls", H), Paragraph(d["security"], B),
             Paragraph("Risk management: " + d["risks"], B),
             Paragraph("6. Support Model, Experience & References", H), Paragraph(d["support"], B),
             Paragraph(d["experience"], B), Spacer(1, 12),
             Paragraph("This is a fictional document created for a classroom exercise.", ss["Italic"])]
    SimpleDocTemplate(path, pagesize=A4, title=title).build(story)
    return path


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for n, d in SUPPLIERS.items():
        print(build(n, d))
