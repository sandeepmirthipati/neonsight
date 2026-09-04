"""In-memory data cleaning and exploratory-data-analysis helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _json_value(value: Any) -> Any:
    """Convert Pandas/NumPy values into JSON-safe values."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def dataframe_records(frame: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    """Return a JSON-safe, compact dataset preview."""
    preview = frame.head(limit).copy()
    for column in preview.columns:
        if pd.api.types.is_datetime64_any_dtype(preview[column]):
            preview[column] = preview[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    return [
        {str(key): _json_value(value) for key, value in row.items()}
        for row in preview.to_dict(orient="records")
    ]


def profile(frame: pd.DataFrame) -> dict[str, Any]:
    """Return high-level health and type metrics for a DataFrame."""
    numeric_columns = frame.select_dtypes(include=np.number).columns.tolist()
    datetime_columns = frame.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    categorical_columns = [
        column for column in frame.columns if column not in numeric_columns + datetime_columns
    ]
    total_cells = max(frame.shape[0] * frame.shape[1], 1)
    missing_count = int(frame.isna().sum().sum())
    return {
        "total_rows": int(frame.shape[0]),
        "total_columns": int(frame.shape[1]),
        "missing_count": missing_count,
        "missing_percentage": round((missing_count / total_cells) * 100, 2),
        "duplicate_count": int(frame.duplicated().sum()),
        "data_types": {
            "numeric": len(numeric_columns),
            "categorical": len(categorical_columns),
            "datetime": len(datetime_columns),
        },
    }


def _clean_headers_and_strings(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip() or f"Column {index + 1}" for index, column in enumerate(result.columns)]
    # Ensure column labels remain unique after trimming.
    seen: dict[str, int] = {}
    labels: list[str] = []
    for label in result.columns:
        seen[label] = seen.get(label, 0) + 1
        labels.append(label if seen[label] == 1 else f"{label}_{seen[label]}")
    result.columns = labels
    for column in result.select_dtypes(include=["object", "string", "category"]).columns:
        result[column] = result[column].map(lambda value: value.strip() if isinstance(value, str) else value)
    return result


def _infer_datetimes(frame: pd.DataFrame) -> pd.DataFrame:
    """Parse clearly date-like object columns without converting general categories."""
    result = frame.copy()
    for column in result.select_dtypes(include=["object", "string"]).columns:
        non_null = result[column].dropna()
        if non_null.empty:
            continue
        values = non_null.astype(str)
        date_hint = values.str.contains(r"[-/:]|\d{4}", regex=True).mean()
        if date_hint < 0.7:
            continue
        parsed = pd.to_datetime(values, errors="coerce")
        if parsed.notna().mean() >= 0.85:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def clean_and_analyze(frame: pd.DataFrame) -> dict[str, Any]:
    """Clean an uploaded dataset and return its EDA metrics and cleaned DataFrame."""
    summary_before = profile(frame)
    cleaned = _infer_datetimes(_clean_headers_and_strings(frame))

    duplicates_dropped = int(cleaned.duplicated().sum())
    cleaned = cleaned.drop_duplicates().copy()
    nulls_before_imputation = int(cleaned.isna().sum().sum())

    numeric_columns = cleaned.select_dtypes(include=np.number).columns.tolist()
    datetime_columns = cleaned.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    categorical_columns = [
        column for column in cleaned.columns if column not in numeric_columns + datetime_columns
    ]
    for column in numeric_columns:
        median = cleaned[column].median()
        if pd.notna(median):
            cleaned[column] = cleaned[column].fillna(median)
    for column in categorical_columns:
        cleaned[column] = cleaned[column].fillna("Unknown")
    # Datetime columns retain missing timestamps; inventing dates would be misleading.

    outliers: dict[str, int] = {}
    for column in numeric_columns:
        values = cleaned[column].dropna()
        if values.empty:
            outliers[column] = 0
            continue
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        if pd.isna(iqr) or iqr == 0:
            outliers[column] = 0
        else:
            outliers[column] = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())

    numeric_summary: dict[str, dict[str, float | None]] = {}
    for column in numeric_columns:
        series = cleaned[column]
        numeric_summary[column] = {
            "mean": _json_value(series.mean()),
            "std_dev": _json_value(series.std()),
            "min": _json_value(series.min()),
            "median": _json_value(series.median()),
            "max": _json_value(series.max()),
        }

    correlations: list[dict[str, Any]] = []
    if len(numeric_columns) >= 2:
        matrix = cleaned[numeric_columns].corr(method="pearson")
        for index, first in enumerate(numeric_columns):
            for second in numeric_columns[index + 1 :]:
                value = matrix.loc[first, second]
                if pd.notna(value) and abs(value) > 0.7:
                    correlations.append({"column_a": first, "column_b": second, "correlation": round(float(value), 3)})

    summary_after = profile(cleaned)
    nulls_filled = max(summary_before["missing_count"] - summary_after["missing_count"], 0)
    return {
        "cleaned_frame": cleaned,
        "summary_before": summary_before,
        "summary_after": summary_after,
        "eda_metrics": {
            "numerical_summary": numeric_summary,
            "high_correlation_pairs": correlations,
            "outliers_by_column": outliers,
            "total_outliers": sum(outliers.values()),
        },
        "cleaning_actions": {
            "nulls_filled": nulls_filled,
            "duplicates_dropped": duplicates_dropped,
        },
    }
