# NeonSight Data Analyzer

NeonSight is a stateless, in-memory data analytics dashboard for CSV and Excel (`.xlsx`) files. Upload a dataset and it automatically inspects its schema, data quality, numerical ranges, categorical values, datetime fields, and relationships—then turns that profile into an interactive Chart.js dashboard.

The application consists of a FastAPI/Pandas service and a dependency-light HTML, CSS, and vanilla JavaScript frontend.

## Highlights

- Upload CSV and XLSX datasets up to 30 MB.
- Processes data only in memory; it does not use a database or save uploaded files.
- Detects numerical, categorical, boolean, datetime, null, and duplicate data.
- Calculates per-column descriptive statistics and categorical frequency information.
- Produces six adaptive visualizations:
  - Data health doughnut: complete versus missing cells.
  - Category/distribution chart: leading categories or a numeric histogram.
  - Adaptive trend chart: a sequential or datetime-backed numeric trend.
  - Dataset-profile radar chart.
  - Range comparison chart: minimum, average, and maximum values.
  - Relationship scatterplot: the strongest available numeric relationship.
- Shows executive KPIs and a collapsible, type-labelled preview of the first 10 records.
- Uses an accessible dark, glassmorphism-inspired responsive interface with Lucide icons and Chart.js animations.

## Technology

| Layer | Technology |
| --- | --- |
| API | Python 3.11+, FastAPI, Uvicorn |
| Data analysis | Pandas, NumPy, OpenPyXL |
| UI | HTML5, CSS3, vanilla JavaScript |
| Charts | Chart.js 4 |
| Icons | Lucide |
| Storage | None — stateless in-memory processing |

## Project structure

```text
smart-data-analyzer/
├── backend/
│   ├── main.py              # FastAPI service and adaptive analysis engine
│   ├── requirements.txt     # Python runtime dependencies
│   ├── eda_engine.py        # Earlier EDA helper module (optional)
│   └── visualizer.py        # Earlier image-chart helper module (optional)
├── frontend/
│   ├── index.html           # Dashboard markup and CDN imports
│   ├── style.css            # Responsive neon glassmorphism UI
│   └── app.js               # Upload, API, table, and Chart.js logic
├── .gitignore
└── README.md
```

The active application entry points are `backend/main.py` and the three files in `frontend/`.

## Requirements

- Python 3.11 or later
- pip
- A modern browser (Chrome, Edge, Firefox, or Safari)

The frontend imports Chart.js and Lucide from CDNs, so an internet connection is required the first time the page loads unless those libraries are self-hosted.

## Local setup

### 1. Create and activate a virtual environment

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install backend dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### 3. Start FastAPI

Run this while your terminal is in the `backend` directory:

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Verify the service is online at [http://127.0.0.1:8000/](http://127.0.0.1:8000/). It should return:

```json
{"status":"online"}
```

### 4. Serve the frontend

Open a second terminal at the project root:

```powershell
cd frontend
python -m http.server 5500
```

Open [http://localhost:5500](http://localhost:5500) and upload a dataset.

> Do not use `file:///.../index.html` for normal development. Serving the frontend through a local web server gives browser requests a valid origin and matches the configured CORS policy.

## How analysis adapts to your data

### Column identification

The backend uses Pandas types and conservative date inference to classify fields:

- **Numerical**: integer and floating-point values.
- **Categorical**: text, object, and other non-numerical fields.
- **Datetime**: native date fields or date-like text columns with a high successful conversion rate.
- **Boolean**: `true`/`false` fields.

### Quality metrics

For every upload, NeonSight calculates total rows and columns, missing cells and missing percentage, duplicate row count, DataFrame memory usage, unique values, and per-column missing values.

For numeric columns, it provides mean, median, minimum, maximum, and standard deviation. For non-numeric columns, it identifies the most frequent value and its frequency.

### Chart selection

The API routes available structure to appropriate chart payloads:

| Dataset characteristic | Visualization behavior |
| --- | --- |
| Any dataset | Complete-versus-missing data health doughnut and profile radar chart |
| Categorical column present | Top ten values of the most compact categorical field |
| No categories but numeric data exists | Histogram for the primary numeric field |
| Numeric field present | Smoothed area trend by sequence; uses datetime labels if a datetime field exists |
| Multiple numeric fields | Scatterplot for the pair with the strongest absolute correlation |
| One numeric field | Scatterplot of record index against that field |
| Numeric fields present | Grouped min/mean/max comparison for up to six fields |

Charts with no compatible data remain visible and explain why they cannot be plotted.

## API reference

### `GET /`

Returns the server health state.

**Response**

```json
{"status":"online"}
```

### `POST /api/analyze`

Accepts a `multipart/form-data` request with a required `file` field.

**Supported formats**

- `.csv`
- `.xlsx`

**Example cURL request**

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -F "file=@sample-data.csv"
```

**Response shape**

```json
{
  "file_name": "sample-data.csv",
  "processing_time_ms": 24.6,
  "summary": {
    "total_rows": 250,
    "total_columns": 8,
    "missing_cells": 12,
    "missing_percentage": 0.6,
    "memory_bytes": 30240,
    "duplicate_rows": 2,
    "primary_column_type": "Numerical",
    "type_counts": {"Numerical": 4, "Categorical": 3, "Datetime": 1}
  },
  "columns": [],
  "charts": {
    "health": {},
    "categories": {},
    "trend": {},
    "radar": {},
    "ranges": {},
    "scatter": {}
  },
  "preview": []
}
```

### Errors

| Status | Meaning |
| --- | --- |
| `400` | Empty or unreadable/corrupt dataset |
| `422` | Missing file, unsupported extension, or file larger than 30 MB |

## CORS configuration

The API allows these development origins:

- `http://localhost:5500`
- `http://127.0.0.1:5500`
- `http://localhost:8000`

For deployment, add your public frontend domain to `ALLOWED_ORIGINS` in [backend/main.py](backend/main.py).

## Deploying

The frontend is static, but the FastAPI service needs a Python application host such as Render, Railway, Fly.io, Azure App Service, or Google Cloud Run.

### Backend command

Use this start command on most hosts:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Configure the host's working directory as `backend`, or use an equivalent module path from the repository root.

### Frontend API URL

Before deploying the static frontend, edit this line in [frontend/app.js](frontend/app.js):

```js
const API = 'http://127.0.0.1:8000';
```

Replace it with your HTTPS backend URL, for example:

```js
const API = 'https://your-api.example.com';
```

Then add the frontend deployment URL to `ALLOWED_ORIGINS` in `backend/main.py` and redeploy the API.

## GitHub

The included `.gitignore` excludes virtual environments, Python cache files, environment files, editor directories, and generated output. Commit the source files and `requirements.txt`; never commit secrets or a `.env` file.

```powershell
git init
git add .
git commit -m "Build adaptive NeonSight analytics dashboard"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

## Troubleshooting

### “Engine offline” or upload cannot connect

Make sure the FastAPI process is running on port 8000 and open the frontend at port 5500. Check `http://127.0.0.1:8000/` directly in your browser.

### “The analysis engine returned an invalid response”

Stop and restart Uvicorn from the `backend` directory, then hard-refresh the browser with `Ctrl + F5`. This removes an outdated JavaScript or backend process from the debugging path.

### XLSX upload fails

Reinstall dependencies from `backend/requirements.txt`; XLSX support requires `openpyxl`. Also make sure the file is a genuine `.xlsx` workbook rather than a renamed legacy `.xls` file.

### A chart says no compatible data is available

This is expected for datasets without the required structure. For example, a scatterplot needs numerical data, while a category chart needs either categorical data or a numerical field for a histogram.

## Privacy and limitations

Data remains in the server process memory only for the request lifetime. For production use, add authentication, upload-rate limits, request logging policies, content-scanning controls, and a reverse proxy with HTTPS. This project is intended for analytics exploration and should not be treated as a substitute for data-governance or security controls.
