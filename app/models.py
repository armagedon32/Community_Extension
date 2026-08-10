from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

ROLES = [
    ("Admin", "System Administrator"),
    ("Extension Director", "Extension Director"),
    ("Linkages Coordinator", "Linkages Coordinator"),
    ("Extension Coordinator", "Extension Coordinator"),
    ("Program Developer", "Program Developer"),
    ("Faculty", "Faculty Member"),
]

PROJECT_STATUSES = ["Proposed", "Ongoing", "Completed"]
PROJECT_CATEGORIES = ["Community Outreach", "Livelihood", "Health", "Education", "Environment", "Governance", "Technology", "Research", "Other"]

PARTNER_TYPES = ["LGU", "NGO", "Academic Institution", "Government Agency", "Private Sector", "Community Organization", "Church-Based", "Other"]

SUPPORT_TYPES = ["Financial Support", "Manpower Support", "Both"]

BENEFICIARY_SEGMENTS = ["Youth", "Senior Citizens", "Farmers", "Women-led Households", "Indigenous Peoples", "PWD", "General Community", "Students"]

ACTIVITY_STATUSES = ["Scheduled", "Ongoing", "Completed", "Cancelled"]

MOA_STATUSES = ["Draft", "Pending", "Active", "Expired", "Terminated"]

DONATION_STATUSES = ["Active", "Inactive"]

DOCUMENT_CATEGORIES = [
    "Project Proposal",
    "Activity Design",
    "Accomplishment Report",
    "Monitoring and Evaluation Report",
    "Memorandum of Agreement",
    "Stakeholder Feedback",
    "Other",
]

TRANSACTION_TYPES = ["Contribution", "Expense", "Allocation"]
TRANSACTION_STATUSES = ["Active", "Inactive"]


class Notification(db.Model):
    """In-app notification for a user, generated automatically by system events."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(20), nullable=False, default="info")  # info/warning/success/danger
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")

    def __repr__(self):
        return f"<Notification {self.id}: {self.message[:40]}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="Faculty")
    department = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    projects = db.relationship("Project", backref="leader", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles):
        return self.role in roles

    def __repr__(self):
        return f"<User {self.username}>"


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="Community Outreach")
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Proposed")
    leader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    progress = db.Column(db.Integer, default=0)
    budget = db.Column(db.Numeric(12, 2), default=0)
    location = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    beneficiaries = db.relationship("Beneficiary", backref="project", lazy=True, cascade="all, delete-orphan")
    activities = db.relationship("Activity", backref="project", lazy=True, cascade="all, delete-orphan")
    moas = db.relationship("MOA", backref="project", lazy=True)
    accomplishments = db.relationship("AccomplishmentReport", backref="project", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.title}>"


class BeneficiaryGroup(db.Model):
    __tablename__ = "beneficiary_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    segment = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    beneficiaries = db.relationship("Beneficiary", backref="group", lazy=True)


class Beneficiary(db.Model):
    __tablename__ = "beneficiaries"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey("beneficiary_groups.id"), nullable=True)
    full_name = db.Column(db.String(150), nullable=False)
    segment = db.Column(db.String(50), nullable=True)
    sex = db.Column(db.String(10), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    contact = db.Column(db.String(50), nullable=True)
    occupation = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Beneficiary {self.full_name}>"


class Partner(db.Model):
    __tablename__ = "partners"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    partner_type = db.Column(db.String(50), nullable=False, default="LGU")
    support_type = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Active")
    engagement_level = db.Column(db.String(20), nullable=True)
    contact_person = db.Column(db.String(150), nullable=True)
    contact_number = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    contribution = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    moas = db.relationship("MOA", backref="partner", lazy=True)
    donations = db.relationship("Donation", backref="partner", lazy=True)

    def __repr__(self):
        return f"<Partner {self.name}>"


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    schedule_date = db.Column(db.Date, nullable=True)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Scheduled")
    participants = db.Column(db.Integer, default=0)
    contact_person = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Activity {self.title}>"


class MOA(db.Model):
    __tablename__ = "moas"

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Draft")
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MOA {self.title}>"


class AccomplishmentReport(db.Model):
    __tablename__ = "accomplishment_reports"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    beneficiaries_served = db.Column(db.Integer, default=0)
    volunteers = db.Column(db.Integer, default=0)
    accomplishments = db.Column(db.Text, nullable=True)
    lessons_learned = db.Column(db.Text, nullable=True)
    report_date = db.Column(db.Date, default=datetime.utcnow)
    submitted_by = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AccomplishmentReport {self.title}>"


class Document(db.Model):
    """Extension document to be automatically classified by the NLP + Naive Bayes engine."""
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=True)  # labeled document type (training) or None
    predicted_category = db.Column(db.String(50), nullable=True)
    domain = db.Column(db.String(50), nullable=True)  # labeled project category/domain (training) or None
    predicted_domain = db.Column(db.String(50), nullable=True)
    is_training = db.Column(db.Boolean, default=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User", backref="documents")

    def __repr__(self):
        return f"<Document {self.title}>"


class MLModel(db.Model):
    """Tracks trained Naive Bayes models and their evaluation metrics."""
    __tablename__ = "ml_models"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    model_type = db.Column(db.String(50), nullable=False, default="Multinomial Naive Bayes")
    status = db.Column(db.String(20), nullable=False, default="Trained")
    accuracy = db.Column(db.Float, nullable=True)
    precision = db.Column(db.Float, nullable=True)
    recall = db.Column(db.Float, nullable=True)
    f1 = db.Column(db.Float, nullable=True)
    samples = db.Column(db.Integer, default=0)
    classes = db.Column(db.String(255), nullable=True)
    metrics_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MLModel {self.name}>"


class FinancialTransaction(db.Model):
    """Financial record for contribution funds (income / expense / allocation)."""
    __tablename__ = "financial_transactions"

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False, default="Contribution")
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    transaction_date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="Active")
    remarks = db.Column(db.Text, nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", backref="financial_transactions")
    recorder = db.relationship("User", backref="financial_transactions")

    def __repr__(self):
        return f"<FinancialTransaction {self.description} {self.amount}>"


class Donation(db.Model):
    """Individual stakeholder (partner) donation record."""
    __tablename__ = "donations"

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    payment_date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="Active")
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Donation {self.partner_id}:{self.amount}>"


# MISP-A data-collection survey module

SURVEY_STATUSES = ["Active", "Closed"]
QUESTION_TYPES = ["scale", "choice", "text", "number"]
SCALE_OPTIONS = ["1", "2", "3", "4", "5"]


class DataCollectionSurvey(db.Model):
    """MISP-A data collection survey template (mobile-friendly collection mode)."""
    __tablename__ = "surveys"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="Community Outreach")
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Active")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship("SurveyQuestion", backref="survey", lazy=True,
                                cascade="all, delete-orphan", order_by="SurveyQuestion.position")
    submissions = db.relationship("SurveySubmission", backref="survey", lazy=True,
                                  cascade="all, delete-orphan")
    creator = db.relationship("User", backref="surveys")

    def __repr__(self):
        return f"<DataCollectionSurvey {self.title}>"


class SurveyQuestion(db.Model):
    """A single question inside a data collection survey."""
    __tablename__ = "survey_questions"

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("surveys.id"), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    question_type = db.Column(db.String(20), nullable=False, default="scale")
    required = db.Column(db.Boolean, default=True)
    position = db.Column(db.Integer, default=0)
    options = db.Column(db.String(500), nullable=True)  # comma-separated choices for "choice"
    scale_min = db.Column(db.Integer, default=1)
    scale_max = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def option_list(self):
        if not self.options:
            return []
        return [o.strip() for o in self.options.split(",") if o.strip()]

    def __repr__(self):
        return f"<SurveyQuestion {self.id}: {self.question_text[:40]}>"


class SurveySubmission(db.Model):
    """A single filled-out data collection record from the field."""
    __tablename__ = "survey_submissions"

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("surveys.id"), nullable=False)
    respondent_name = db.Column(db.String(150), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    contact = db.Column(db.String(50), nullable=True)
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    answers = db.Column(db.Text, nullable=True)  # JSON {question_id: value}
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    submitter = db.relationship("User", backref="survey_submissions")

    def __repr__(self):
        return f"<SurveySubmission {self.id} survey={self.survey_id}>"
