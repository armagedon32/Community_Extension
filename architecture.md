# System Architecture of the Proposed System (CELMIS)

## 1. Overview

The **Community Extension Management Information System (CELMIS)** is a web-based, modular management and decision-support platform built on the **Flask** micro-framework (Python). It integrates an **Artificial Intelligence sub-system** for the automatic classification of extension documents, **basic descriptive analytics** (percentages, distributions), and **database management** through SQLAlchemy ORM. The architecture follows a classic **three-tier (presentation - application - data)** pattern, extended with a dedicated **NLP/AI engine** and deployable via the **gunicorn** web server on Railway.

## 2. Architectural Diagram

```
+------------------------------------------------------------------------------------------+
|                            PRESENTATION TIER (Browser)                                    |
|  Bootstrap 5.3  -  Jinja2 Templates  -  ApexCharts (graphs/heatmaps)  -  Bootstrap Icons   |
|     Views: Login . Dashboard . Projects . Partners . MOA . Reports .                      |
|            Evaluations . Surveys . Finance . ML Lab . Documents                           |
+------------------------------------^-------------------------------------^---------------+
                                     |             HTTP/HTTPS (Flask routes)  |
+------------------------------------v-------------------------------------v---------------+
|                            APPLICATION TIER (Flask)                                       |
|                                                                                           |
|  +-------------------------------------------------------------------------------------+  |
|  |              Controllers (Blueprint modules under app/routes/)                      |  |
|  +----------+-----------+-----------+-----------+-----------+-----------+-------------+  |
|  |  auth    | projects  | partners  | activities|   moas   |  reports  |   surveys    |  |
|  |dashboard | beneficiari| finance  | evaluation|    ml    |  compose  |              |  |
|  +----^----------------------------------------------------------------------------+----+  |
|       |                                                                                     |
|  +----v-------------------------+          +--------------------------------------------+   |
|  |    AI / ML ENGINE (app/ml/)  |          |  File Extraction Service                   |   |
|  |  preprocess.py: tokenizer,   |          |  pypdf (PDF) -> text                       |   |
|  |  stop-word removal, TF-IDF   |          |  python-docx (DOCX) -> text                |   |
|  |  engine.py: Multinomial      |          +--------------------^-----------------------+   |
|  |  Naive Bayes classifiers     |                            |  reads uploaded files        |
|  |   - Document Type model      |  +---------------------+    |  app/static/uploads/        |
|  |   - Project Domain model     |  | Flask-Login /        |    |                           |
|  |   - objective extraction     |  | Flask-WTF security   |    |                           |
|  +----^-------------------------+  +----------^----------+    |                           |
|       |  trains / predicts on demand     ^                    |                           |
+-------v-----------------------------------v--------------------v---------------------------+
|                              DATA TIER (SQLAlchemy ORM)                                     |
|   Models: User . Project . Beneficiary . Partner . Activity . MOA . Document .             |
|           Achievement . EvaluationItem/Submission . Transaction . Survey                   |
|   Storage: SQLite (local) / PostgreSQL (Railway) via DATABASE_URL                         |
|   ML artifacts persisted: app/ml/models/*.joblib (on Railway: ephemeral, retrained on boot)|
+------------------------------------------------------------------------------------------+
```

*Alternative Mermaid rendering (paste into https://mermaid.live to generate PNG/SVG):*

```mermaid
flowchart TB
    subgraph UI["PRESENTATION TIER (Browser)"]
        UI1[Bootstrap 5.3 + Jinja2 Templates]
        UI2[ApexCharts visualizations]
        UI3[Views: Login, Dashboard, Projects, Partners, MOA, Reports, Evaluations, Surveys, Finance, ML Lab]
    end

    subgraph APP["APPLICATION TIER (Flask)"]
        C1[auth] C2[dashboard] C3[projects] C4[partners]
        C5[beneficiaries] C6[activities] C7[moas] C8[reports]
        C9[evaluations] C10[surveys] C11[finance] C12[ml]
        AI["AI / ML Engine (app/ml/)<br/>preprocess.py, engine.py<br/>Multinomial Naive Bayes<br/>- Document Type model<br/>- Project Domain model<br/>- objective extraction"]
        FE["File Extraction Service<br/>pypdf (PDF) -> text<br/>python-docx (DOCX) -> text"]
        SEC["Flask-Login / Flask-WTF"]
    end

    subgraph DATA["DATA TIER (SQLAlchemy ORM)"]
        DB[(SQLite / PostgreSQL)]
        ML[(ML artifacts .joblib)]
    end

    UI1 --> C1 & C2 & C3 & C4 & C5 & C6 & C7 & C8 & C9 & C10 & C11 & C12
    C7 --> FE
    FE --> AI
    C12 --> AI
    C2 --> DB
    AI <--> ML
    AI --> DB
    C1 <--> SEC
```

## 3. Component Discussion

**Presentation Tier (Client).** Renders all pages using **Jinja2 templates** and **Bootstrap 5**, so the interface is responsive across desktops and mobile. Interactive dashboards are visualized with **ApexCharts** (pie/donut/bar charts and the ML confusion-matrix heatmap). This tier only displays the data and never touches business logic directly.

**Application Tier (Flask).**
- **Controllers** are organized into twelve feature **blueprints**: `auth` (login/roles), `projects`, `partners`, `beneficiaries`, `activities`, `moas`, `reports`, `evaluations`, `surveys`, `finance`, `ml`, and `dashboard`, each handling its own HTTP routes, form validation, and business rules.
- **Flask-Login** and **Flask-WTF** guard authenticated access and form/data validation.
- **AI/ML Engine (`app/ml/`)** - two independent **Multinomial Naive Bayes classifiers** trained with an 80/20 stratified split:
  - a *document-type* classifier (Project Proposal, Activity Design, Accomplishment Report, Memorandum of Agreement, Monitoring and Evaluation Report, Stakeholder Feedback), and
  - a *project-category* classifier (Governance, Education, Health, Livelihood, Environment, etc.).
  The full pipeline is: **preprocessing -> TF-IDF vectorization -> fit -> predict -> evaluation** (accuracy, precision, recall, F1, confusion matrix). An **objective extractor** summarizes each uploaded document.
- **File Extraction Service** - on upload, `pypdf` for PDFs and `python-docx` for DOCX files extract the embedded text, which the AI engine then scans.

**Data Tier.**
- **SQLAlchemy ORM** maps all entities - `User`, `Project`, `Beneficiary`, `Partner`, `Activity`, `MOA`, `Document`, `Survey`, `Evaluation`, `Finance/Transaction` - to a relational database (SQLite locally, **PostgreSQL** when deployed on Railway, selected automatically via an environment variable). `db.create_all()` initializes the schema, and **model artifacts** (`.joblib`) are persisted for on-demand reuse.

## 4. Integrated Technologies and External Services

| Technology | Purpose in the system |
|-----------|------------------------|
| Flask 3 | Web application framework (routes, sessions, templating) |
| Flask-SQLAlchemy / SQLAlchemy 2 | Object-relational mapping and database access |
| scikit-learn (MultinomialNB, TfidfVectorizer) | Naive Bayes classification and TF-IDF feature extraction |
| joblib | Persist/reload trained model artifacts |
| pypdf / python-docx | Extract text from uploaded PDF/DOCX documents |
| ApexCharts 3.45 | Data visualization (doughnut/bar/heatmap charts) |
| Bootstrap 5.3 / Bootstrap Icons | Responsive UI framework and iconography |
| Flask-Login / Flask-WTF | Authentication, session, and CSRF form security |
| gunicorn | Production WSGI server (declared in the Procfile) |
| SQLite / PostgreSQL | Relational storage (PostgreSQL on Railway) |

## 5. Overall Workflow

1. **Authentication** - an authorized user logs in; Flask-Login grants role-scoped access to the modules.
2. **Data entry / import** - a staff member registers projects, partners, activities, MOAs, surveys, and evaluations through the CRUD modules. Uploaded MOAs (PDF/DOCX) are text-extracted and stored.
3. **Classification** - when a document is uploaded (or the ML Documents page is opened), the AI Engine runs the trained Naive Bayes classifiers over the extracted **content** and writes the *Document Type* and *Project Category* predictions back to the record.
4. **Training** - on an empty database the system auto-seeds labeled extension documents; the classifiers auto-train on boot, or manually via the "Train Model" action in the **ML Lab**, and report accuracy/precision/recall/F1 and a confusion-matrix heatmap.
5. **Evaluation and survey intelligence** - the `evaluations` module stores ISO 25010 scores and shows results; the `surveys` module collects MISP-A responses.
6. **Reporting and decision support** - controllers aggregate the persisted rows and render descriptive percentage distributions, printable institutional reports, and the dashboard overview.
