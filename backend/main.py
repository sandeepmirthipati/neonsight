"""Adaptive, in-memory profiling API for the Smart Data Analyzer."""

from __future__ import annotations

import io
import math
import time
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
ALLOWED_ORIGINS = ["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:8000"]
PALETTE = ["#00f2fe", "#7928ca", "#ff0080", "#00e676", "#ff9f03", "#4facfe", "#ff5e62", "#c6ff00"]

app = FastAPI(title="Enterprise Smart Data Analyzer", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])


def _fail(status: int, message: str) -> None:
    raise HTTPException(status_code=status, detail=message)


def _read_file(filename: str, content: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        _fail(422, "Unsupported file type. Upload a CSV or XLSX file.")
    try:
        buffer = io.BytesIO(content)
        if suffix == ".xlsx":
            return pd.read_excel(buffer, engine="openpyxl")
        try:
            return pd.read_csv(buffer)
        except UnicodeDecodeError:
            buffer.seek(0)
            return pd.read_csv(buffer, encoding="latin-1")
    except (ValueError, OSError, zipfile.BadZipFile, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        _fail(400, f"Unable to read this dataset: {exc}")


def _safe_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value): return None
    number = float(value)
    if not math.isfinite(number): return None
    return int(number) if number.is_integer() else round(number, 4)


def _kind(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series): return "Boolean"
    if pd.api.types.is_numeric_dtype(series): return "Numerical"
    if pd.api.types.is_datetime64_any_dtype(series): return "Datetime"
    return "Categorical"


def _infer_datetimes(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for name in result.select_dtypes(include=["object", "string"]).columns:
        values = result[name].dropna().astype(str)
        if values.empty or values.str.contains(r"[-/:]|\d{4}", regex=True).mean() < .7: continue
        parsed = pd.to_datetime(values, errors="coerce")
        if parsed.notna().mean() >= .85: result[name] = pd.to_datetime(result[name], errors="coerce")
    return result


def _histogram(series: pd.Series) -> tuple[list[str], list[int]]:
    values = series.dropna().astype(float)
    if values.empty: return [], []
    counts, edges = np.histogram(values, bins=min(12, max(4, int(np.sqrt(len(values))))))
    return [f"{edges[i]:.3g}–{edges[i + 1]:.3g}" for i in range(len(counts))], counts.astype(int).tolist()


def _chart_payloads(frame: pd.DataFrame, numeric: list[str], categorical: list[str], datetime_columns: list[str]) -> dict[str, Any]:
    total_cells = frame.shape[0] * frame.shape[1]
    missing = int(frame.isna().sum().sum())
    if categorical:
        category_column = min(categorical, key=lambda name: frame[name].nunique(dropna=True))
        counts = frame[category_column].fillna("Missing").astype(str).value_counts().head(10)
        categorical_chart = {"title": f"Top categories · {category_column}", "source": category_column, "labels": counts.index.tolist(), "values": counts.astype(int).tolist()}
    elif numeric:
        labels, values = _histogram(frame[numeric[0]])
        categorical_chart = {"title": f"Distribution · {numeric[0]}", "source": numeric[0], "labels": labels, "values": values}
    else:
        categorical_chart = {"title": "No categorical distribution", "source": None, "labels": [], "values": []}

    trend_column = numeric[0] if numeric else None
    trend_values = frame[trend_column].replace([np.inf, -np.inf], np.nan).dropna() if trend_column else pd.Series(dtype=float)
    trend_labels: list[str]
    if datetime_columns and trend_column:
        dates = frame.loc[frame[trend_column].notna(), datetime_columns[0]].astype(str)
        trend_labels = dates.tolist()
    else:
        trend_labels = [str(i + 1) for i in range(len(trend_values))]
    if len(trend_values) > 80:
        positions = np.linspace(0, len(trend_values) - 1, 80, dtype=int)
        trend_values, trend_labels = trend_values.iloc[positions], [trend_labels[i] for i in positions]

    range_columns = numeric[:6]
    range_chart = {"labels": range_columns, "minimum": [_safe_number(frame[name].min()) for name in range_columns], "average": [_safe_number(frame[name].mean()) for name in range_columns], "maximum": [_safe_number(frame[name].max()) for name in range_columns]}
    radar_metrics = {
        "Completeness": round(100 * (1 - missing / max(total_cells, 1)), 2),
        "Unique values": round(100 * frame.nunique(dropna=True).sum() / max(total_cells, 1), 2),
        "Numeric coverage": round(100 * len(numeric) / max(frame.shape[1], 1), 2),
        "Category coverage": round(100 * len(categorical) / max(frame.shape[1], 1), 2),
        "Duplicate-free": round(100 * (1 - frame.duplicated().sum() / max(len(frame), 1)), 2),
    }
    x_name = y_name = None
    points: list[dict[str, float]] = []
    correlation = None
    if len(numeric) >= 2:
        matrix = frame[numeric].corr(numeric_only=True).abs()
        pairs = [(matrix.loc[left, right], left, right) for index, left in enumerate(numeric) for right in numeric[index + 1:] if pd.notna(matrix.loc[left, right])]
        if pairs:
            _, x_name, y_name = max(pairs, key=lambda item: item[0])
            correlation = _safe_number(frame[[x_name, y_name]].corr().iloc[0, 1])
            clean = frame[[x_name, y_name]].dropna().head(250)
            points = [{"x": float(row[x_name]), "y": float(row[y_name])} for _, row in clean.iterrows()]
    elif numeric:
        x_name, y_name = "Record", numeric[0]
        points = [{"x": index + 1, "y": float(value)} for index, value in enumerate(frame[numeric[0]].dropna().head(250))]
    return {
        "health": {"labels": ["Complete", "Missing"], "values": [max(total_cells - missing, 0), missing]},
        "categories": categorical_chart,
        "trend": {"title": f"Trend · {trend_column}" if trend_column else "No numeric trend", "labels": trend_labels, "values": [_safe_number(value) for value in trend_values], "column": trend_column, "uses_datetime": bool(datetime_columns)},
        "radar": {"labels": list(radar_metrics), "values": list(radar_metrics.values())},
        "ranges": range_chart,
        "scatter": {"x_name": x_name, "y_name": y_name, "correlation": correlation, "points": points},
    }


def _profile(frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.copy()
    frame.columns = [str(name).strip() or f"Column {position + 1}" for position, name in enumerate(frame.columns)]
    frame = _infer_datetimes(frame.replace([np.inf, -np.inf], np.nan))
    numeric = frame.select_dtypes(include=np.number).columns.tolist()
    datetime_columns = frame.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    categorical = [name for name in frame.columns if name not in numeric + datetime_columns]
    total_rows, total_columns = frame.shape
    missing_cells = int(frame.isna().sum().sum())
    types = Counter(_kind(frame[name]) for name in frame.columns)
    details = []
    for name in frame.columns:
        series = frame[name]
        detail = {"name": str(name), "kind": _kind(series), "dtype": str(series.dtype), "missing": int(series.isna().sum()), "unique": int(series.nunique(dropna=True))}
        if name in numeric:
            detail["statistics"] = {"mean": _safe_number(series.mean()), "median": _safe_number(series.median()), "min": _safe_number(series.min()), "max": _safe_number(series.max()), "std": _safe_number(series.std())}
        else:
            top = series.dropna().astype(str).value_counts().head(1)
            detail["top_value"] = top.index[0] if not top.empty else None
            detail["top_frequency"] = int(top.iloc[0]) if not top.empty else 0
        details.append(detail)
    memory = int(frame.memory_usage(deep=True).sum())
    primary_type = "Numerical" if numeric else ("Categorical" if categorical else ("Datetime" if datetime_columns else "Unknown"))
    return {
        "summary": {"total_rows": int(total_rows), "total_columns": int(total_columns), "missing_cells": missing_cells, "missing_percentage": round(100 * missing_cells / max(total_rows * total_columns, 1), 2), "memory_bytes": memory, "duplicate_rows": int(frame.duplicated().sum()), "primary_column_type": primary_type, "type_counts": dict(types)},
        "columns": details, "charts": _chart_payloads(frame, numeric, categorical, datetime_columns), "preview": frame.head(10).replace({np.nan: None}).astype(object).where(pd.notnull(frame.head(10)), None).to_dict(orient="records"),
    }


@app.get("/")
def health() -> dict[str, str]: return {"status": "online"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename: _fail(422, "A dataset file is required.")
    content = await file.read()
    if not content: _fail(400, "The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES: _fail(422, "Files must be 30 MB or smaller.")
    started = time.perf_counter()
    dataset = _read_file(file.filename, content)
    if dataset.empty: _fail(400, "The dataset contains no data rows.")
    result = _profile(dataset)
    result["file_name"] = Path(file.filename).name
    result["processing_time_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result
