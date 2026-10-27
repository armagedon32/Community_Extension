import random
import textwrap
from datetime import datetime, timedelta

from app import create_app, db
from app.models import Document, User, DOCUMENT_CATEGORIES, PROJECT_CATEGORIES

random.seed(20251028)

app = create_app()
ctx = app.app_context()
ctx.push()

admin = User.query.filter_by(username='admin').first()
if not admin:
    raise SystemExit("Admin user not found!")

# Clear existing session
db.session.rollback()

# Balance across all document types
cats = list(DOCUMENT_CATEGORIES)
per_cat = 600 // len(cats)
rem = 600 % len(cats)

assignments = []
for i, c in enumerate(cats):
    count = per_cat + (1 if i < rem else 0)
    assignments.extend([c] * count)

random.shuffle(assignments)

# Domain pool
doms = list(PROJECT_CATEGORIES)

# Content templates per category
templates = {
    "Project Proposal": [
        "This project proposal aims to address the needs of the target beneficiaries through a community-based approach. Sa pamamagitan ng collaborative efforts with partner agencies, the proposed initiative seeks to promote sustainable development in the area.",
        "The project will focus on capacity building, resource mobilization, and knowledge sharing. Ang mga benepisyaryo ay mabibigyan ng sapat na pagsasanay upang mapanatili ang proyekto pagkatapos ng implementation period.",
        "Through this undertaking, the LGU and CELMIS aim to strengthen local participation, enhance service delivery, and create long-term impact. Ang proyekto rin ay nakabatay sa mga priority programs ng lokal na pamahalaan.",
        "With proper monitoring and evaluation mechanisms in place, the team ensures transparency and accountability throughout the project lifecycle. Kaya't ang proponent ay humihingi ng suporta at pagkilala sa nais na programa."
    ],
    "Activity Design": [
        "This activity design outlines the objectives, scope, methodology, and expected outputs for the upcoming extension activity. Layunin ng aktibidad na ito na bigyang-diin ang kahalagahan ng participatory approach sa pagsasagawa ng programa.",
        "The activity will be conducted through lectures, workshops, group discussions, and hands-on exercises. Ang mga kalahok ay aktibong makilahok upang mas mapalawak ang kanilang kaalaman at kasanayan.",
        "Necessary resources, logistics, and personnel have been identified to ensure the smooth implementation of the activity. Kinakailangan din ang koordinasyon sa mga partner stakeholders upang maisakatuparan nang maayos ang gawain.",
        "Post-activity evaluation will be conducted to measure the effectiveness of the training and gather feedback from participants. Ang resulta nito ay magsisilbing basehan sa pagpapabuti ng mga susunod na aktibidad."
    ],
    "Accomplishment Report": [
        "This accomplishment report summarizes the activities conducted, outputs delivered, and milestones achieved for the covered period. Sa kabuuan, malaki ang progress na natamo ng proyekto kumpara sa nakatakdang timeline.",
        "A total of qualified beneficiaries were served through various interventions implemented by the project team. Ang mga pagsasanay, distribution ng inputs, at technical assistance ay naisagawa nang maayos at on-schedule.",
        "Despite minor challenges encountered during implementation, the team was able to adapt and find alternative solutions. Ang patuloy na pakikipagtulungan ng mga stakeholders ay malaking tulong sa tagumpay ng proyekto.",
        "Overall, the project remains on track to achieve its targets. Ang mga naipamigay na serbisyo ay malaki ang naitulong sa pagpapabuti ng kabuhayan at kalagayan ng mga benepisyaryo."
    ],
    "Monitoring and Evaluation Report": [
        "This Monitoring and Evaluation (M&E) report assesses the performance of the project based on its key indicators. Sinusuri sa ulat na ito ang antas ng accomplishment ng bawat target at ang bisa ng mga interbensyon na ipinatupad.",
        "Data gathered through field visits, interviews, and focus group discussions were analyzed and presented in this report. Ang mga natuklasan ay nagpapakita na karamihan sa mga indikator ay nasiyahan sa itinakdang quota o lampas pa dito.",
        "Some indicators, particularly those requiring behavioral change, show slower progress and need further follow-up. Kinakailangan pa ang mas masinsinang pagsubaybay upang matiyak na makakamit ang ninanais na outcome.",
        "Based on the findings, the team recommends intensifying coaching sessions, strengthening linkages, and ensuring timely submission of reports. Ang mga rekomendasyong ito ay inaasahan na makakatulong sa mas mabilis at epektibong pagsasakatuparan ng mga target."
    ],
    "Memorandum of Agreement": [
        "This Memorandum of Agreement (MOA) is entered into by and between the parties for the purpose of implementing a collaborative extension program. Ang nasabing kasunduan ay naglalayong pagsaluhan ang mga resources, kakayahan, at responsibilidad ng bawat panig.",
        "The responsibilities of each party are clearly defined to ensure effective coordination and proper implementation. Ang CELMIS ay magsasagawa ng technical assistance, training, at monitoring, samantalang ang partner agency naman ay magbibigay ng suporta sa logistics at identification of beneficiaries.",
        "Both parties agree to comply with existing policies, maintain proper documentation, and observe transparency throughout the duration of the agreement. Ang anumang pagbabago sa kasunduan ay kinakailangan ng pagsang-ayon ng magkabilang panig.",
        "This agreement shall take effect upon signing and remain in force for the period specified herein. Ang pagkakaugnay-ugnay na ito ay inaasahan na magbibigay-daan sa mas malawak at mas sustainable na serbisyo sa komunidad."
    ],
    "Stakeholder Feedback": [
        "This document compiles the feedback gathered from various stakeholders who participated in the implemented programs and activities. Karamihan sa mga tugon ay positibo, na nagpapahiwatig na ang mga serbisyo ng CELMIS ay kapaki-pakinabang at angkop sa pangangailangan ng komunidad.",
        "Beneficiaries expressed appreciation for the practical knowledge and skills they gained during the training sessions. Ayon sa kanila, ang mga natutunan nila ay agad na nagagamit sa kanilang araw-araw na gawain at sa kanilang mga kabuhayan.",
        "Some suggestions were raised regarding the duration of activities, venue accessibility, and provision of follow-up assistance. Malaki ang halaga ng mga suhestyon na ito sapagkat nagsisilbing gabay sa pagpapabuti ng mga susunod na programa.",
        "The project team takes these comments seriously and commits to address valid concerns in future implementation. Ang patuloy na pakikinig sa stakeholders ay isa sa mga pangunahing prinsipyo sa epektibong extension service delivery."
    ],
    "Other": [
        "This document pertains to ancillary extension-related matters that support the implementation of CELMIS programs. Kabilang dito ang mga coordination reports, courtesy visits, and other official correspondences relevant to partnership development.",
        "Various coordination meetings were conducted with local government units, academic institutions, and partner organizations. Ang mga pagpupulong na ito ay naglalayon na mapalawak ang network ng partnerships at mapalakas ang convergence of services.",
        "These engagements help facilitate resource sharing, avoid duplication of efforts, and maximize impact in the communities served. Sa pamamagitan ng mas malapit na koordinasyon, nagiging mas episyente ang daloy ng impormasyon at suporta.",
        "Documentation of these activities ensures proper tracking of commitments and follow-up actions. Ang mga rekord na ito ay mahalaga sa pagtiyak ng continuity ng partnerships at sa paghahanda para sa mga hinaharap na programa."
    ]
}

titles_by_cat = {
    "Project Proposal": ["Community Development Initiative Proposal", "Sustainable Livelihood Program Proposal", "Extension Program Project Proposal", "Barangay Empowerment Project Proposal"],
    "Activity Design": ["Skills Training Activity Design", "Capability Building Workshop Design", "Community Orientation Activity Plan", "Entrepreneurship Training Design"],
    "Accomplishment Report": ["Quarterly Accomplishment Report", "Semestral Accomplishment Report", "Program Implementation Accomplishment Report", "Extension Activities Accomplishment Report"],
    "Monitoring and Evaluation Report": ["Mid-Year M&E Report", "Annual Monitoring and Evaluation Report", "Field Monitoring Report", "Project Performance Review Report"],
    "Memorandum of Agreement": ["MOA on Extension Services Partnership", "MOA on Skills Training Collaboration", "MOA on Community Outreach Program", "MOA on Technical Assistance and Support"],
    "Stakeholder Feedback": ["Stakeholders' Feedback Report", "Beneficiaries' Satisfaction Survey Summary", "Community Feedback Consolidation Report", "Partners' Assessment and Feedback Report"],
    "Other": ["Coordination Meeting Report", "Courtesy Visit Documentation", "Partnership Development Report", "Inter-Agency Coordination Summary"]
}

added = 0
batch = []

for idx, cat in enumerate(assignments):
    dom = random.choice(doms)
    base_titles = titles_by_cat[cat]
    title = f"{random.choice(base_titles)} - Batch{idx//10:03d}-{idx%10:02d}"
    
    # Build medium content (3-6 paragraphs)
    paras = random.sample(templates[cat], k=random.randint(4, 4))  # use all 4 for consistency
    # Slight variation
    content_parts = []
    for p in paras:
        # Add slight variation
        if random.random() < 0.3:
            p = p.replace("CELMIS", "CELMIS Extension Services").replace("proyekto", "proyekto o programa")
        content_parts.append(p)
    
    content = "\n\n".join(content_parts)
    
    doc = Document(
        title=title,
        filename=f"{title.replace(' ', '_').lower()}.pdf",
        content=content,
        category=cat,
        domain=dom,
        predicted_category=None,
        predicted_domain=None,
        is_training=True,
        uploaded_by=admin.id,
        created_at=datetime.utcnow() - timedelta(days=random.randint(1, 365))
    )
    batch.append(doc)
    added += 1
    
    if len(batch) >= 50:
        db.session.bulk_save_objects(batch)
        db.session.commit()
        batch = []
        print(f"Added {added}/600...")

if batch:
    db.session.bulk_save_objects(batch)
    db.session.commit()

print(f"\nDONE! Added {added} training documents.")
print("Verifying distribution by category:")
from sqlalchemy import func
for c, cnt in db.session.query(Document.category, func.count(Document.id)).filter(Document.is_training==True).group_by(Document.category).order_by(Document.category).all():
    print(f"  {c}: {cnt}")
print("\nVerifying distribution by domain:")
for d, cnt in db.session.query(Document.domain, func.count(Document.id)).filter(Document.is_training==True).group_by(Document.domain).order_by(Document.domain).all():
    print(f"  {d}: {cnt}")

ctx.pop()
