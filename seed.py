"""Seed the database with sample users and demonstration records."""
import datetime
import json
import random

from app import create_app, db
from app.models import (
    AccomplishmentReport,
    Activity,
    Beneficiary,
    BeneficiaryGroup,
    DataCollectionSurvey,
    Document,
    EvaluationItem,
    FinancialTransaction,
    MOA,
    Member,
    MemberContribution,
    Partner,
    Project,
    SurveyQuestion,
    SurveySubmission,
    User,
)


CATEGORIES = ["Community Outreach", "Livelihood", "Health", "Education", "Environment", "Technology"]
SEGMENTS = ["Youth", "Senior Citizens", "Farmers", "Women-led Households", "Indigenous Peoples", "PWD", "Students"]
STATUSES = ["Proposed", "Ongoing", "Completed"]
ACTIVITY_STATUSES = ["Scheduled", "Ongoing", "Completed"]
PARTNER_TYPES = ["LGU", "NGO", "Academic Institution", "Government Agency", "Private Sector"]

USERS = [
    ("admin", "admin@celmis.ph", "System Administrator", "Admin", "MIS Department"),
    ("director", "director@celmis.ph", "Dr. Elena Director", "Extension Director", "Community Extension Office"),
    ("linkages", "linkages@celmis.ph", "Linkages Coordinator", "Linkages Coordinator", "Linkages Office"),
    ("coordinator", "coordinator@celmis.ph", "Community Coordinator", "Extension Coordinator", "Community Extension Office"),
    ("dev", "dev@celmis.ph", "Program Developer", "Program Developer", "Community Extension Office"),
    ("faculty1", "faculty1@celmis.ph", "Juan Dela Cruz", "Faculty", "Teacher Education"),
    ("faculty2", "faculty2@celmis.ph", "Maria Santos", "Faculty", "Business Administration"),
]

PARTNERS = [
    ("Municipality of Subic", "LGU", "Active"),
    ("Barangay Wawandue Council", "LGU", "Active"),
    ("Simbahang Sambayanihan", "Church-Based", "Active"),
    ("DepEd Subic Division", "Government Agency", "Active"),
    ("Rotary Club of Subic", "NGO", "Active"),
]

PROJECTS = [
    ("Barangay Literacy Program", "Education", "Weekend literacy classes for out-of-school youth.", "Ongoing"),
    ("Community Health Caravan", "Health", "Free medical consultations and health screening for residents.", "Ongoing"),
    ("Digital Literacy for Seniors", "Technology", "Basic computer training for senior citizens.", "Ongoing"),
    ("Coastal Clean-Up Drive", "Environment", "Monthly coastal clean-up with barangay volunteers.", "Completed"),
    ("Micro-Business Training", "Livelihood", "Livelihood training for women-led households.", "Ongoing"),
    ("Tree Planting Initiative", "Environment", "Reforestation drive across partner municipalities.", "Completed"),
    ("Child Nutrition Program", "Health", "Nutrition assessment for malnourished children.", "Proposed"),
]

GROUP_NAMES = ["Out-of-School Youth", "Community Adults", "Women", "Senior Citizens", "Farmers"]

BENEFICIARY_NAMES = [
    "Ana Alvarez", "Benito Bautista", "Carla Cruz", "Diego Dizon", "Elena Eugenio",
    "Fredo Fernandez", "Gina Garcia", "Hector Hernandez", "Ivy Infante", "Joel Jimenez",
]

def infer_domain(content):
    """Best-effort keyword mapping of document content to a project domain for demo seeding."""
    t = (content or "").lower()
    if any(k in t for k in ("health", "medical", "clinic", "nutrition", "doctor", "nurse",
                            "immunization", "screening", "hygiene", "diabetes", "feeding")):
        return "Health"
    if any(k in t for k in ("livelihood", "income", "soap", "business", "skills training",
                            "entrepreneurship", "starter kit", "market", "fair", "micro")):
        return "Livelihood"
    if any(k in t for k in ("literacy", "reading", "teacher", "teaching", "learning", "tuition",
                            "scholarship", "school", "learner", "tutorial", "education")):
        return "Education"
    if any(k in t for k in ("coastal", "cleanup", "tree", "plant", "riverbank", "bamboo",
                            "environment", "seedling", "forest", "water access", "garden")):
        return "Environment"
    if any(k in t for k in ("municipal", "government", "council", "provincial", "governance",
                            "local government", "barangay council")):
        return "Governance"
    if any(k in t for k in ("computer", "digital", "technology", "internet", "software",
                            "tesda", "technical")):
        return "Technology"
    if any(k in t for k in ("research", "study", "baseline", "impact evalua")):
        return "Research"
    return "Community Outreach"


# Explicit domain overrides for demo seeding where keyword inference is ambiguous.
DOMAIN_OVERRIDES = {
    "MOA with Municipal LGU": "Governance",
    "MOA with Provincial Government": "Governance",
    "MOA with Municipal LGU for Community Development": "Governance",
    "MOA with DepEd for Literacy Program": "Education",
    "Community Medical Mission MOA": "Health",
    "Livelihood Cooperative MOA": "Livelihood",
    "Compliance Monitoring Report": "Governance",
    "MOA for Training Partnership": "Education",
    "MOA for Teacher Training": "Education",
    "MOA with DepEd Learning Center": "Education",
    "MOA for Medical Outreach": "Health",
    "MOA for Coastal Program": "Environment",
    "Partnership MOA for Seed Funding": "Livelihood",
    "End of Year Accomplishment Report": "Education",
    "Q1 Accomplishment Report": "Education",
    "Quarterly Monitoring Report": "Education",
    "Outreach Orientation Activity Design": "Community Outreach",
    "Process Evaluation of Outreach": "Community Outreach",
    "Volunteer Feedback Form": "Community Outreach",
}


def run_seed(reset=True, app=None):
    if app is None:
        app = create_app()
    with app.app_context():
        if reset:
            db.drop_all()
            db.create_all()
            print("Database recreated.")
        else:
            db.create_all()
    
        users = []
        for username, email, full_name, role, dept in USERS:
            u = User(username=username, email=email, full_name=full_name, role=role, department=dept)
            u.set_password("password")
            db.session.add(u)
            users.append(u)
        db.session.commit()
    
        groups = []
        for gname in GROUP_NAMES:
            bg = BeneficiaryGroup(name=gname)
            db.session.add(bg)
            groups.append(bg)
        db.session.commit()
    
        partners = []
        for pname, ptype, st in PARTNERS:
            p = Partner(
                name=pname,
                partner_type=ptype,
                status=st,
                engagement_level=random.choice(["Low", "Medium", "High"]),
                contact_person=f"{pname} Contact",
                contact_number="0917" + str(1000000 + random.randint(0, 999999)),
                email=pname.lower().replace(" ", "") + "@example.ph",
                address="Subic, Zambales",
                contribution="Financial, logistical, and manpower support",
            )
            db.session.add(p)
            partners.append(p)
        db.session.commit()
    
        projects = []
        for i, (title, cat, desc, _) in enumerate(PROJECTS):
            status = STATUSES[i % len(STATUSES)]
            proj = Project(
                title=title,
                category=cat,
                description=desc,
                status=status,
                leader_id=users[i % len(users)].id,
                start_date=datetime.date.today() - datetime.timedelta(days=random.randint(30, 180)),
                end_date=datetime.date.today() + datetime.timedelta(days=random.randint(30, 180)),
                progress=random.randint(10, 100),
                budget=random.randint(10000, 500000),
                location=f"Subic, Zambales Area {i + 1}",
            )
            db.session.add(proj)
            projects.append(proj)
        db.session.commit()
    
        for i, bname in enumerate(BENEFICIARY_NAMES):
            b = Beneficiary(
                project_id=projects[i % len(projects)].id,
                group_id=groups[i % len(groups)].id,
                full_name=bname,
                segment=SEGMENTS[i % len(SEGMENTS)],
                sex="Female" if i % 2 == 0 else "Male",
                age=random.randint(18, 70),
                address=f"Barangay {i % 5 + 1}, Subic, Zambales",
                contact="0917" + str(1000000 + i * 99999),
                occupation=f"Resident",
            )
            db.session.add(b)
        db.session.commit()
    
        for pci, proj in enumerate(projects):
            act = Activity(
                project_id=proj.id,
                title=f"{proj.title} - Session {pci + 1}",
                description="Extension activity implementation",
                schedule_date=datetime.date.today() + datetime.timedelta(days=(pci * 7) % 30),
                start_time=datetime.time(9, 0) if pci % 2 == 0 else datetime.time(13, 0),
                end_time=datetime.time(12, 0) if pci % 2 == 0 else datetime.time(16, 0),
                location=proj.location,
                status=ACTIVITY_STATUSES[pci % len(ACTIVITY_STATUSES)],
                participants=random.randint(20, 120),
                contact_person=users[pci % len(users)].full_name,
            )
            db.session.add(act)
        db.session.commit()
    
        for mi, part in enumerate(partners[:4]):
            m = MOA(
                partner_id=part.id,
                project_id=projects[mi % len(projects)].id,
                title=f"MOA with {part.name}",
                description="Partnership agreement for community extension initiatives",
                status=["Pending", "Active", "Active", "Expired"][mi],
                start_date=datetime.date.today() - datetime.timedelta(days=60),
                end_date=datetime.date.today() + datetime.timedelta(days=300),
                notes="Renewable upon mutual agreement",
            )
            db.session.add(m)
        db.session.commit()
    
        for ri, proj in enumerate(projects[:5]):
            rep = AccomplishmentReport(
                project_id=proj.id,
                title=f"Accomplishment Report - {proj.title}",
                summary="Completion of key deliverables",
                beneficiaries_served=random.randint(30, 200),
                volunteers=random.randint(5, 30),
                accomplishments="Conducted activities as scheduled",
                lessons_learned="Strong community engagement required",
                report_date=datetime.date.today() - datetime.timedelta(days=ri * 5),
                submitted_by=users[ri % len(users)].full_name,
            )
            db.session.add(rep)
        db.session.commit()
    
        # Labeled training documents for the Naive Bayes model
        labeled_docs = [
            ("Literacy Outreach Proposal", "Project Proposal",
             "This project proposal seeks funding for a literacy program targeting out-of-school youth in coastal barangays. The program will conduct weekly reading classes, distribute learning modules, and train volunteer teachers. Expected beneficiaries include elementary pupils and out-of-school youth. The extension office will submit the proposal to the barangay council for approval."),
            ("Community Health Caravan Design", "Activity Design",
             "The activity design outlines a one-day community health caravan offering free medical consultations, blood pressure screening, dental checkups, and health education seminars. The event will be held at the barangay covered court with volunteer physicians and nurses. Target participants are 200 residents including elderly and children."),
            ("Q1 Accomplishment Report", "Accomplishment Report",
             "This accomplishment report documents the completed extension activities for the first quarter. The office conducted three outreach programs, two training sessions, and one community assembly. A total of 450 beneficiaries were served by 60 faculty volunteers. All scheduled activities were accomplished within the approved budget."),
            ("M&E Report for Nutrition Program", "Monitoring and Evaluation Report",
             "The monitoring and evaluation report assesses the implementation of the child nutrition program. Baseline data was collected from 120 children in the first month. Follow-up measurements show improvement in weight-for-age indicators. The evaluation recommends extending the feeding program for another six months to sustain gains."),
            ("MOA with Municipal LGU", "Memorandum of Agreement",
             "This memorandum of agreement establishes a partnership between the university and the municipal government for community extension collaboration. The parties agree to jointly implement livelihood training, share resources and facilities, and conduct joint monitoring of extension programs. The agreement is effective for two years from signing."),
            ("Community Feedback Survey", "Stakeholder Feedback",
             "Respondents expressed satisfaction with the extension programs conducted in their community. They requested more frequent health services and additional livelihood training opportunities. Several beneficiaries suggested extending the literacy program to evening sessions to accommodate working parents. Overall feedback was positive."),
            ("Livelihood Training Proposal", "Project Proposal",
             "This proposal requests support for a livelihood training program for women-led households. The training covers soap making, candle production, and basic entrepreneurship. Each participant will receive starter kits after completing the sessions. The project aims to provide alternative income sources for 80 women in the community."),
            ("Tree Planting Activity Report", "Accomplishment Report",
             "The tree planting activity was conducted along the riverbank with 150 participants including students, faculty, and barangay residents. A total of 500 seedlings were planted. The activity also included a short seminar on environmental conservation. The event was supported by the municipal environment office."),
            ("Health Outreach Activity Design", "Activity Design",
             "This activity design presents the schedule and logistics for the barangay health outreach. Free vitamin supplementation, blood sugar testing, and child immunization will be provided. The design specifies the venue, staffing requirements, and health protocols. The activity will run from 8 AM to 4 PM."),
            ("Feedback from Partner NGO", "Stakeholder Feedback",
             "The partner NGO provided feedback on the joint livelihood program. They noted strong community participation and effective coordination by the extension. They recommended improving the reporting system to track individual beneficiary progress and suggested quarterly review meetings to align program targets."),
            # ---- Expanded corpus for a meaningful 80/20 train/test split ----
            ("Livelihood Skills Training Proposal", "Project Proposal",
             "This proposal requests funding to establish a livelihood skills training center serving rural households. The center will offer courses in basic bookkeeping, food packaging, handicrafts, and small business management. A feasibility study and budget breakdown are attached. The expected outcome is to reduce poverty indicators among member households within twelve months."),
            ("Water Access Project Proposal", "Project Proposal",
             "The proposed water access project aims to install community water stations serving three remote barangays. Funding will cover pipeline materials, storage tanks, and training for a local maintenance committee. The proposal includes a request for technical assistance from the provincial engineering office and a sustainability plan."),
            ("Vulnerable Sectors Assistance Proposal", "Project Proposal",
             "This extended proposal seeks support for educational assistance to vulnerable learners affected by displacement. Scholarships, school supplies, and transportation subsidies are outlined for two hundred students. Scholarships will be monitored through a partnership with local public schools. The proposal requests endorsement from the regional department office."),
            ("Bamboo Plantation Proposal", "Project Proposal",
             "The proposal outlines a bamboo plantation project for riverbank stabilization and livelihood generation. It requests saplings, planting tools, and a training fund. Revenue sharing and environmental targets are described. The university extension unit will cooperate with the environment office during implementation."),
            ("TESDA Skills Proposal", "Project Proposal",
             "This project proposal addresses youth unemployment through a TESDA office certification program. Training modules on food processing and tour guiding are described with projected enrollment and a financial planning summary. The proposed budget includes training fees, facility use, and feeding support for participants."),
            ("Proposal for Community Learning", "Project Proposal",
             "This proposal is submitted for a community learning project offering remedial instruction for dropout learners. It outlines lesson resource development and volunteer training requirements. Weekly reports and a program evaluation framework are described in the proposal document."),
            ("Health Caravan Activity Design", "Activity Design",
             "The activity design schedules a mobile health clinic in five barangays. Services include flu vaccination, diabetes screening, and maternal health awareness. The design details the staffing matrix, medicine list, and activity timeline for volunteer nurses. Health risk protocols and referral pathways are also defined in the activity design."),
            ("Literacy Day Activity Design", "Activity Design",
             "This activity design describes a literacy day celebration with reading tents, storytelling, and a book donation drive. The activity design includes the venue map, volunteer roster, and a schedule of reading games for children. Interaction and participation of parents are encouraged throughout the activity design."),
            ("Outreach Orientation Activity Design", "Activity Design",
             "The activity design presents an orientation session for new outreach volunteers. It covers the project scope, safety orientation, and reporting responsibilities. The activity design includes an agenda with training facilitators and a volunteer kit checklist. Responsibilities and contact points are contained within the activity design."),
            ("Vegetable Gardening Activity Design", "Activity Design",
             "This activity design organizes container gardening demos for residents. It includes seed distribution, soil preparation, and planting activity steps. The activity design lists the facilitators, materials, and a follow-up activity plan. Training method and scheduling are described in the activity design."),
            ("Coastal Cleanup Activity Design", "Activity Design",
             "The activity design plans a coastal cleanup along the shoreline. It outlines the coastline zones, safety briefing, and cleanup groups. The activity design allocates materials, scheduling, and reporting personnel. A celebration activity will recognize participants and partners inside the activity design."),
            ("Hygiene Seminar Activity Design", "Activity Design",
             "This activity design schedules a community hygiene seminar covering handwashing and water sanitation. The activity design includes seminar materials, demonstration session, and quiz activity for participants. Supplies and facilitator assignments are outlined in the activity design."),
            ("Second Quarter Accomplishment Report", "Accomplishment Report",
             "This accomplishment report covers the second quarter extension operations. The office delivered digital literacy sessions, healing, and community assemblies. A total of three hundred volunteers were mobilized. All targets noted in the accomplishment report were achieved under the approved timeline."),
            ("End of Year Accomplishment Report", "Accomplishment Report",
             "The annual accomplishment report details the extension activities implemented for the academic year. It consolidates data on beneficiaries, activities, and volunteers served. Recommendations and accomplishments are summarized in the report. This accomplishment report supports allocation for the following year."),
            ("Seminar Accomplishment Report", "Accomplishment Report",
             "This accomplishment report covers the parent leadership seminar. Attendance and evaluation results are included. The seminars reached parents and school staff. Lessons and areas for improvement are noted in this accomplishment report for future sessions."),
            ("Backyard Gardening Accomplishment Report", "Accomplishment Report",
             "This accomplishment report summarizes the household gardening program. The report shows the number of households, harvest quantity, and training attendance. Support and partnerships extended the program. Community interest and activity is described in the accomplishment report."),
            ("Feeding Program Accomplishment Report", "Accomplishment Report",
             "The accomplishment report documents the school feeding program. Nutritional status and attendance are reported. The report lists food vendors and supervision. Outcomes from the feeding program are measured and included in this accomplishment report."),
            ("Reading Remediation Accomplishment Report", "Accomplishment Report",
             "This accomplishment report describes the reading remediation initiative. Learners, tutors, and comprehension results are examined. The report validates the tutoring model and success steps. A continuing plan is stated in the accomplishment report."),
            ("M&E Report on Livelihood Outcomes", "Monitoring and Evaluation Report",
             "The monitoring and evaluation report reviews livelihood program outcomes after six months. It documents income changes, participant retention, and product sales. The evaluation report recommends follow-up training and market support. Findings in this monitoring and evaluation report guide program planning."),
            ("Process Evaluation of Outreach", "Monitoring and Evaluation Report",
             "This monitoring and evaluation report assesses the outreach process and delivery. It reviews the number served, referral completion, and bottlenecks. The evaluation report proposes scheduling adjustments. Actions from this M&E report will improve future outreach."),
            ("Impact Evaluation Report", "Monitoring and Evaluation Report",
             "The impact evaluation report examines long-term benefits of the employment program. It compares employment and skills outcomes against baseline. The evaluation report and its findings support the sustainability plan. Decisions from the monitoring and evaluation report inform fund allocation."),
            ("Quarterly Monitoring Report", "Monitoring and Evaluation Report",
             "This quarterly monitoring report tracks extension performance indicators. It notes achievement, data gaps, and remedial measures. The monitoring report recommends additional resources. Lessons from this quarterly monitoring and evaluation report guide the next cycle."),
            ("Compliance Monitoring Report", "Monitoring and Evaluation Report",
             "The compliance monitoring report validates that activities adhered to approved plans and good practice. The evaluation report cross-checks attendance and expenditure. Non-compliance and corrective actions are documented in the monitoring report for management attention."),
            ("Baseline Study Report", "Monitoring and Evaluation Report",
             "This baseline study report consolidates pre-project data on the community. The evaluation report establishes control group data to compare outcomes later. Design and data are documented in this monitoring report. The baseline serves the eventual impact evaluation report."),
            ("MOA for Training Partnership", "Memorandum of Agreement",
             "This memorandum of agreement is entered into by the university, institute, and center for faculty training. The parties shall jointly design and deliver capacity building. Responsibilities and a transparency mechanism are fixed in this agreement. This MOA shall take effect upon signing."),
            ("MOA with Provincial Government", "Memorandum of Agreement",
             "This memorandum of agreement formalizes the collaboration between the university and the provincial government. Cooperation covers data sharing, resource pooling, and joint monitoring. The agreement validity period is three years. Both parties execute the memorandum in good faith."),
            ("MOA for Medical Outreach", "Memorandum of Agreement",
             "Under this memorandum of agreement, the health group and the university commit to a medical outreach partnership. The agreement commits volunteers, supplies, and reimbursement terms. Obligations on both parties are written in this memorandum. The agreement shall be governed accordingly."),
            ("MOA with DepEd Learning Center", "Memorandum of Agreement",
             "This memorandum of agreement between the university and the education division supports tutorial. It provides scope, school cooperation, and teacher supervision. Both parties signed this agreement to govern implementation. The memorandum shall be renewed annually."),
            ("MOA for Coastal Program", "Memorandum of Agreement",
             "This memorandum of agreement covers the coastal management program. The parties, a local resource group, and the university commit to cleanup and monitoring. The agreement states the schedule and equipment provided. Disputes under this memorandum shall be resolved by both signatories."),
            ("Partnership MOA for Seed Funding", "Memorandum of Agreement",
             "This memorandum of agreement provides the framework for seed funding and the community bank. It establishes loan terms, repayment, and financial management. The agreement is executed with full consent of the parties. This memorandum of agreement is part of the project."),
            ("MOA for Teacher Training", "Memorandum of Agreement",
             "This memorandum of agreement arranges teacher training with the professional development center. The teacher training program, faculty, and venue are agreed. The parties execute this memorandum as a formal instrument of partnership. Renewal is subject to mutual approval."),
            ("MOA with Municipal LGU for Community Development", "Memorandum of Agreement",
             "KNOW ALL MEN BY THESE PRESENTS: This Memorandum of Agreement made and entered into by and between the LOCAL COLLEGE, a tertiary institution created under Sangguniang Bayan Resolution, represented by its College President, hereinafter referred to as the FIRST PARTY, and the MUNICIPALITY, a Local Government Unit, represented by its Municipal Mayor, hereinafter referred to as the SECOND PARTY. WITNESSETH: whereas the FIRST PARTY, being a service institution, and the SECOND PARTY share the common goal of community development and extension service; whereas the parties wish to formalize their partnership for community extension collaboration. NOW, THEREFORE, for and in consideration of the foregoing premises, the parties mutually covenant and agree upon the following: to jointly implement community development programs, share resources and facilities, provide technical assistance, and conduct joint monitoring and evaluation. This agreement shall take effect upon the execution hereof and shall remain in full force and effect for a period of two years unless earlier terminated by mutual consent of the parties. IN WITNESS WHEREOF, the parties have hereunto set their hands on the date above written. Signed in the presence of witnesses. The first party certifies readiness of the college to undertake the project."),
            ("MOA with DepEd for Literacy Program", "Memorandum of Agreement",
             "This Memorandum of Agreement is made and entered into by and between the LOCAL COLLEGE, hereinafter referred to as the FIRST PARTY, and the SCHOOLS DIVISION, hereinafter referred to as the SECOND PARTY. WITNESSETH: WHEREAS the FIRST PARTY is an academic institution engaged in instruction, research and extension; WHEREAS the parties desire to pool their resources for a literacy and tutorial program. NOW THEREFORE the parties agree as follows: undertake reading remediation, coordinate schedules, provide learning materials, and assign teaching interns. This Agreement is executed upon signing and remains in effect for the entire duration of the program. IN WITNESS WHEREOF the parties hereunto affix their signatures this day of the execution. This memorandum sets the scope and cooperation between the university and the education division."),
            ("Community Medical Mission MOA", "Memorandum of Agreement",
             "KNOW ALL MEN BY THESE PRESENTS: This Memorandum of Agreement executed by and between the COLLEGE, represented by its President as the FIRST PARTY, and the HEALTH TEAM, represented by its Coordinator as the SECOND PARTY for a free community medical mission. WHEREAS the parties intend to deliver health services, medical consultation, and free medicines to the community. NOW THEREFORE the parties covenant to provide volunteers, medical supplies, equipment, and the venue; free medical services shall be given to the recipient communities. The Agreement binds the parties to conduct the medical mission within the agreed schedule and to cover authorized officers for the outreach. Signed by the parties and attested by witnesses. The memorandum sets the obligations on both parties regarding the health outreach. Any provision of the agreement shall be enforced with the applicable rules."),
    ("Livelihood Cooperative MOA", "Memorandum of Agreement",
     "This Memorandum of Agreement is entered into by and between the LOCAL COLLEERATED the FIRST PARTY and the LIVELIHOOD COOPERATIVE as the SECOND PARTY for the establishment of a livelihood and seed capital program. WHEREAS the parties wish to extend financial assistance to community members, THIS AGREEMENT provides the framework for seed funding, establishes loan terms, repayment schedules, and financial management systems. The parties shall assist with capacity building and monitoring. Effective upon execution and for the term of the lending window. In witness whereof the sworn undersigned signatories execute this instrument to govern their collaboration."),
            ("Resident Survey Feedback", "Stakeholder Feedback",
             "Residents responded to the feedback form on their health outreach. They appreciated scheduling and vaccination but requested longer clinic hours and more supplies. Feedback responses will be consolidated for the next cycle of delivery and reporting."),
            ("Barangay Council Feedback", "Stakeholder Feedback",
             "The barangay council gave feedback on the literacy access program. The council supported the reading sessions and suggested involving more families. This feedback helps the office refine scheduling for the program. Additional meeting and service times were requested."),
            ("Student Feedback on Training", "Stakeholder Feedback",
             "Students submitted feedback about the skills training. They found the modules practical and the training room comfortable. Feedback pointed out the need for more practice materials and longer sessions. The student feedback will drive the next cohort design."),
            ("Volunteer Feedback Form", "Stakeholder Feedback",
             "Volunteers shared feedback on the outreach logistics. They appreciated good coordination but recommended clearer task assignments and earlier communication. The volunteer feedback responses are summarized for the operations report and future improvements."),
            ("Bayang Feedback on Gardening", "Stakeholder Feedback",
             "Feedback from the gardeners praised the container gardening help and the seed donation. They requested more variety of seeds and an additional planting demonstration. This feedback affirms the community demand for continued backyard agriculture support."),
            ("Teacher Feedback on Tutoring", "Stakeholder Feedback",
             "Teachers responded that the tutoring visits improved learner confidence. They gave feedback that tutoring should continue during review months. Feedback also emphasized the value and the need for more tutors. This teacher input guides the tutoring schedule."),
            # ---- Domain-specific corpus: clear Education / Livelihood / Governance / Environment / Health vocabulary ----
            ("Reading Curriculum Enhancement Design", "Activity Design",
             "The activity design proposes a reading curriculum enhancement for grade school classrooms. It covers lesson planning, reading comprehension drills, and teacher coaching. Teachers will use phonics and guided reading techniques. The curriculum plan is aligned with the education department standards for literacy."),
            ("Science Education Outreach Proposal", "Project Proposal",
             "This proposal requests support for a science education outreach in public schools. It will set up classroom science kits, conduct laboratory demonstrations, and train science teachers. Students will engage in inquiry-based learning projects. The proposal targets schools with limited laboratory equipment."),
            ("Teacher Training Accomplishment Report", "Accomplishment Report",
             "The accomplishment report covers the teacher training program for effective reading instruction. Forty teachers attended the workshops on lesson planning and comprehension strategies. Training materials were distributed to all participants. This report documents the completion of the education capacity building sessions."),
            ("Savings Cooperative Proposal", "Project Proposal",
             "The proposal establishes a savings cooperative for micro-entrepreneurs. It provides for capital build-up, group savings, and small loans. Members will learn bookkeeping and financial management. The cooperative aims to increase household income and savings among vendors."),
            ("Market Linkage Training Activity Design", "Activity Design",
             "This activity design organizes market linkage training for farmer entrepreneurs. Sessions cover product pricing, sales channels, and packaging for market access. Participants will be linked to buyers and local fairs. The activity aims to boost income from agricultural products."),
            ("Microfinance Feedback Report", "Stakeholder Feedback",
             "Microfinance clients gave feedback on the loan program. They reported higher income from their small businesses and easier capital access. Some clients requested longer repayment periods. This feedback on the microfinance scheme will refine lending terms and support."),
            ("Barangay Governance Forum Proposal", "Project Proposal",
             "This proposal plans a barangay governance forum to strengthen transparency and accountability. It includes public hearings, citizen scorecards, and community assemblies. Local government officials and residents will jointly review budgets. The forum promotes participatory governance and citizen engagement."),
            ("Citizen Participation Activity Design", "Activity Design",
             "The activity design schedules citizen participation workshops on local government planning. Residents will map community needs and propose projects for the barangay budget. The design includes facilitated sessions on good governance and accountability. Public officials will respond to the assembled proposals."),
            ("LGU Coordination Accomplishment Report", "Accomplishment Report",
             "This accomplishment report documents the local government coordination meetings for extension projects. Municipal officials, barangay captains, and department heads participated. Joint resolutions were approved to align programs with the local development plan. The report covers governance collaboration and follow-up actions."),
            ("Waste Segregation Program Proposal", "Project Proposal",
             "The proposal launches a barangay waste segregation and recycling program. It requests segregation bins, a materials recovery facility, and eco-brick training. Households will sort biodegradable and recyclable waste. The program reduces pollution and promotes environmental sustainability."),
            ("Watershed Protection Activity Design", "Activity Design",
             "This activity design schedules watershed protection and tree growing activities. Volunteers will plant native trees along the watershed and monitor stream health. The design includes conservation lectures and water quality testing. The activity supports environmental conservation in the upland communities."),
            ("Coastal Reforestation Feedback", "Stakeholder Feedback",
             "Residents shared feedback on the mangrove reforestation effort. They observed increased fish catch and healthier shoreline vegetation. Feedback requested continued planting of mangroves and coastal cleanups. The environmental conservation feedback supports expanding the reforestation area."),
            ("Maternal Health Program Proposal", "Project Proposal",
             "The proposal seeks funding for a maternal health program in rural barangays. Services include prenatal checkups, immunization, and nutrition counseling. Midwives will conduct home visits and sanitation education. The program aims to reduce maternal risks and improve child health."),
            ("First Aid Training Activity Design", "Activity Design",
             "The activity design outlines first aid and hygiene training for community health workers. Sessions cover wound care, sanitation, and emergency response drills. Participants will receive basic first aid kits. The design follows the health department protocols for community training."),
            ("Immunization Drive Accomplishment Report", "Accomplishment Report",
             "The accomplishment report documents the immunization drive for children. Vaccines for measles and polio were administered by licensed health staff. Coverage reached target rates across the barangays. This report records the health program achievements and referrals made."),
        ]
        for doc_title, doc_cat, doc_content in labeled_docs:
            db.session.add(Document(
                title=doc_title,
                category=doc_cat,
                domain=DOMAIN_OVERRIDES.get(doc_title, infer_domain(doc_content)),
                content=doc_content,
                is_training=True,
                uploaded_by=users[0].id,
            ))
        db.session.commit()
    
        # Evaluation items (ISO/IEC 25010 questionnaire)
        evaluation_items = {
            "Functional Suitability": [
                "The system provides all essential features for managing community extension programs.",
                "The classification results are accurate and appropriate.",
                "The system generates complete and correct analytics and reports.",
                "All core processes function as intended.",
            ],
            "Performance Efficiency": [
                "The system loads and responds quickly.",
                "The system remains responsive during simultaneous processes.",
                "The system shortens the time required to process documents and reports.",
                "System outputs are generated promptly.",
            ],
            "Compatibility": [
                "The system works properly on different devices (desktop, laptop, tablet).",
                "The system functions across various browsers and operating systems.",
                "The system interface displays correctly on all supported platforms.",
            ],
            "Usability": [
                "The system is easy to learn for first-time users.",
                "Navigation and layout are clear and user-friendly.",
                "Instructions, buttons, and labels are easy to understand.",
                "Users can efficiently complete tasks.",
            ],
            "Reliability": [
                "The system operates smoothly without crashing or interruption.",
                "The system performs consistently even during heavy use.",
                "Data is stored and retrieved accurately.",
                "The system produces consistent results.",
            ],
            "Security": [
                "User data is protected from unauthorized access.",
                "Login authentication and account management are secure.",
                "Sensitive data is securely stored and transmitted.",
            ],
            "Maintainability": [
                "The system's code and architecture are organized and easy to update.",
                "Components are modular, allowing efficient maintenance.",
                "Errors can be fixed without disrupting other functionalities.",
                "Documentation is sufficient for ongoing maintenance.",
            ],
            "Safety": [
                "The system maintains data integrity and prevents errors.",
                "The system protects against risks associated with incorrect data handling.",
                "System operations do not cause harm or disadvantage to stakeholders.",
            ],
        }
        for char, indicators in evaluation_items.items():
            for indicator in indicators:
                db.session.add(EvaluationItem(characteristic=char, indicator=indicator))
        db.session.commit()
    
        # Financial seed data
        members = []
        for mname in ["John Reyes", "Sarah Lim", "Mike Tan", "Anna Cruz"]:
            m = Member(name=mname, employee_id=f"KNS-{len(members)+1:03d}", department="Academic Affairs")
            db.session.add(m)
            members.append(m)
        db.session.commit()
    
        for idx, m in enumerate(members):
            amt = random.randint(200, 1500)
            c = MemberContribution(member_id=m.id, amount=amt,
                                   payment_date=datetime.date.today() - datetime.timedelta(days=idx * 15))
            db.session.add(c)
            db.session.add(FinancialTransaction(
                description=f"Member contribution — {m.name}",
                transaction_type="Contribution",
                amount=amt,
                project_id=projects[idx % len(projects)].id,
                transaction_date=datetime.date.today() - datetime.timedelta(days=idx * 15),
                recorded_by=users[0].id,
            ))
        db.session.add(FinancialTransaction(
            description="Outreach supplies for Community Health Caravan",
            transaction_type="Expense",
            amount=random.randint(5000, 20000),
            project_id=projects[1].id,
            transaction_date=datetime.date.today() - datetime.timedelta(days=10),
            recorded_by=users[0].id,
        ))
        db.session.add(FinancialTransaction(
            description="Fund allocation for Literacy Program",
            transaction_type="Allocation",
            amount=random.randint(10000, 30000),
            project_id=projects[0].id,
            transaction_date=datetime.date.today() - datetime.timedelta(days=20),
            recorded_by=users[0].id,
        ))
        db.session.commit()
    
        # MISP-A data collection surveys
        survey_data = [
            {
                "title": "Outreach Satisfaction Survey",
                "category": "Community Outreach",
                "description": "Field survey to measure community satisfaction with extension outreach services.",
                "questions": [
                    {"name": "How do you rate the quality of the outreach services?", "type": "scale"},
                    {"name": "How helpful were the activities to your community?", "type": "scale"},
                    {"name": "How likely are you to recommend similar programs?", "type": "scale"},
                    {"name": "Which outreach service did you benefit from most?",
                     "type": "choice", "options": "Health,Education,Livelihood,Environment,Technology"},
                    {"name": "Number of family members served", "type": "number"},
                    {"name": "Additional comments or suggestions", "type": "text"},
                ],
            },
            {
                "title": "Livelihood Program Monitoring",
                "category": "Livelihood",
                "description": "MISP-A collection for monitoring livelihood training outcomes.",
                "questions": [
                    {"name": "Rate the usefulness of the training content.", "type": "scale"},
                    {"name": "Did training skills translate into income?", "type": "choice", "options": "Yes,Partially,Not yet"},
                    {"name": "Current average monthly income from the venture.", "type": "number"},
                    {"name": "Suggestions for improving the livelihood program.", "type": "text"},
                ],
            },
        ]
    
        QUESTION_DEFS = {}
        for sidx, sv in enumerate(survey_data):
            survey = DataCollectionSurvey(
                title=sv["title"],
                category=sv["category"],
                description=sv.get("description"),
                status="Active",
                created_by=users[0].id,
            )
            db.session.add(survey)
            db.session.flush()
            for qidx, q in enumerate(sv["questions"]):
                db.session.add(SurveyQuestion(
                    survey_id=survey.id,
                    question_text=q["name"],
                    question_type=q.get("type", "scale"),
                    required=True,
                    position=qidx,
                    options=q.get("options"),
                ))
            QUESTION_DEFS[sidx] = survey.id
    
        db.session.commit()
    
        # Sample survey submissions
        sample_answers = [
            (0, "Maria Dela Cruz", "Barangay 1, Subic", {"0": "4", "1": "5", "2": "5", "3": "Health", "4": "4", "5": "Very helpful, thank you."}),
            (0, "Jose Ramos", "Barangay 2, Subic", {"0": "3", "1": "4", "2": "4", "3": "Education", "4": "3", "5": "Please add more evening sessions."}),
            (0, "Liza Mendoza", "Barangay 3, Subic", {"0": "5", "1": "5", "2": "4", "3": "Livelihood", "4": "5", "5": "Great experience overall."}),
            (0, "Pedro Aquino", "Barangay 1, Subic", {"0": "4", "1": "4", "2": "5", "3": "Health", "4": "2", "5": ""}),
            (1, "Carmen Bautista", "Barangay 4, Subic", {"0": "4", "1": "Partially", "2": "12000", "3": "Need more product samples."}),
            (1, "Nestor Lim", "Barangay 5, Subic", {"0": "5", "1": "Yes", "2": "18000", "3": "Excellent program."}),
            (1, "Aileen Go", "Barangay 2, Subic", {"0": "3", "1": "Not yet", "2": "5000", "3": "Provide follow-up coaching."}),
        ]
    
        for sidx, name, loc, answers in sample_answers:
            survey_id = QUESTION_DEFS[sidx]
            qids = {q.position: q.id for q in SurveyQuestion.query.filter_by(survey_id=survey_id).all()}
            mapped = {str(qids.get(int(k), int(k))): v for k, v in answers.items()}
            db.session.add(SurveySubmission(
                survey_id=survey_id,
                respondent_name=name,
                location=loc,
                submitted_by=users[1].id,
                answers=json.dumps(mapped),
            ))
        db.session.commit()
    
        print("Seed data created successfully!")
        print("Default login: admin / password")

if __name__ == "__main__":
    run_seed()
