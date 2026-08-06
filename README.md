# CELMIS — Community Extension Management Information System

An AI-driven, outcomes-based Management Information System built with **Python Flask + SQLAlchemy** for the **Community Extension Services and Linkages Office** of Kolehiyo ng Subic. This project implements the core MIS features described in the dissertation:

> *"Developing and Evaluating an AI-Driven Outcomes-Based Management Information System Using Natural Language Processing and Naïve Bayes Classification for Community Extension and Institutional Linkages"*

## Features

- **User Authentication & Roles** — Secure login (Flask-Login) with role-based access: Admin, Extension Director, Linkages Coordinator, Extension Coordinator, Program Developer, Faculty.
- **Information Management Dashboard** — KPIs (active projects, partners, beneficiaries, activities) with interactive **ApexCharts.js** visualizations (project status, category distribution, beneficiary segments, partner types, activity status).
- **Project Portfolio Module** — Create, categorize, monitor, and update extension projects (Proposed / Ongoing / Completed), with progress tracking and linked accomplishment reports.
- **Beneficiary Management** — Community profiles, beneficiary segments, groups, and project affiliation.
- **Partner & Linkages Module** — Institutional partners, partner types, engagement levels, and status.
- **Activity / Event Management** — Schedule, monitor, and record extension activities with participants.
- **MOA (Memorandum of Agreement)** — Manage partnership agreements with document upload.
- **Reports & Decision Support** — Printable institutional reports (Projects, Beneficiaries, Partners, Activities, MOAs, Accomplishments) plus a CSV summary export.
- **Machine Learning Lab** — NLP + Multinomial Naive Bayes document classification using **two independent classifiers**:
  - **Document Type** — Proposal, Activity Design, Accomplishment Report, M&amp;E Report, MOA, Stakeholder Feedback.
  - **Project Category / Domain** — Education, Livelihood, Governance, Environment, Health, Technology, etc.
  Upload labeled extension documents, train both models, and auto-classify new documents — the system returns both the document type and the project domain. Performance is evaluated using **accuracy, precision, recall, F1-score, and confusion matrices** (ApexCharts heatmaps).
- **ISO/IEC 25010 Evaluation** — Built-in questionnaire covering the 8 quality characteristics (Functional Suitability, Performance Efficiency, Compatibility, Usability, Reliability, Security, Maintainability, Safety) with automatic mean and overall score computation.
- **Contribution Funds** — Financial dashboard, transactions (contributions/expenses/allocations), and member contribution tracking.
- **MISP-A Data Collection** — Mobile-friendly field survey module. Create survey templates with scale, choice, number, and text questions; collect data from the field; and visualize average indicator scores and locations visited (ApexCharts).

## Tech Stack

- Backend: Python 3.14, Flask 3.x, Flask-SQLAlchemy, Flask-Login
- AI/ML: scikit-learn (TfidfVectorizer, MultinomialNB, classification metrics)
- Database: SQLite (default) — easily switchable to MySQL via `DATABASE_URL`
- Frontend: Bootstrap 5, Bootstrap Icons, ApexCharts.js, Jinja2

## Getting Started

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Seed the database (creates `celmis.db` with sample data)

```bash
python seed.py
```

> Default login: **admin / password**

### 3. Run the app

```bash
python run.py
```

Then open http://127.0.0.1:5000 in your browser.

## Default Users (all password = `password`)

| Username    | Role                   |
|-------------|------------------------|
| `admin`     | System Administrator  |
| `director`  | Extension Director      |
| `linkages`  | Linkages Coordinator    |
| `coordinator`| Extension Coordinator  |
| `dev`       | Program Developer      |
| `faculty1` / `faculty2` | Faculty |

## Switching to MySQL

Set the `DATABASE_URL` environment variable before running:

```powershell
$env:DATABASE_URL = "mysql+pymysql://user:password@localhost/celmis_db"
```

(Install `pymysql`: `python -m pip install pymysql` and create the database.)

## Project Structure

```
D:\Community_Extension\
├── run.py                 # App entry point
├── seed.py                # Seed/demo data
├── config.py              # Configuration (DB URI)
├── requirements.txt
└── app\
    ├── __init__.py         # create_app factory
    ├── models.py           # SQLAlchemy models & roles
    ├── routes\            # Blueprints (auth, dashboard, projects, ...)
    ├── templates\         # Jinja2 templates
    └── static\             # CSS/JS
    └── static\uploads\     # Uploaded MOA files
```

## Notes

The seeded demo data includes 62 labeled extension documents (6 document types, 7 project domains) so you can immediately train both Naive Bayes models and view meaningful accuracy, precision, recall, F1, and confusion-matrix results. Trained models are persisted under `app/ml/models/` and loaded automatically when classifying new documents.