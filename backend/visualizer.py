"""Base64 chart generation for automated EDA."""

import base64
import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sns.set_theme(style="darkgrid", palette="mako")


def _to_base64(fig: plt.Figure) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=140, bbox_inches="tight", facecolor="#10131f")
    buffer.seek(0)
    image = base64.b64encode(buffer.read()).decode("utf-8")
    buffer.close()
    plt.close(fig)
    plt.close("all")
    return image


def _style(fig: plt.Figure) -> None:
    fig.patch.set_facecolor("#10131f")
    for axis in fig.axes:
        axis.set_facecolor("#161b2d")
        axis.tick_params(colors="#c8d0e7")
        axis.xaxis.label.set_color("#e9edff")
        axis.yaxis.label.set_color("#e9edff")
        axis.title.set_color("#e9edff")


def generate_charts(frame: pd.DataFrame) -> dict[str, str | None]:
    numeric = frame.select_dtypes(include="number").columns.tolist()[:8]
    categorical = frame.select_dtypes(include=["object", "string", "category"]).columns.tolist()[:4]
    charts: dict[str, str | None] = {"heatmap": None, "distributions": None, "boxplots": None, "categories": None}

    if len(numeric) >= 2:
        fig, axis = plt.subplots(figsize=(max(7, len(numeric)), max(5, len(numeric) * 0.72)))
        _style(fig)
        sns.heatmap(frame[numeric].corr(), annot=True, fmt=".2f", cmap="mako", center=0, ax=axis)
        axis.set_title("Correlation Heatmap", pad=14, fontweight="bold")
        charts["heatmap"] = _to_base64(fig)

    if numeric:
        fig, axes = plt.subplots(len(numeric), 1, figsize=(9, max(3, 2.7 * len(numeric))))
        axes = [axes] if len(numeric) == 1 else axes
        _style(fig)
        for axis, column in zip(axes, numeric):
            sns.histplot(frame[column].dropna(), kde=True, ax=axis, color="#8b5cf6")
            axis.set_title(f"Distribution: {column}", loc="left", fontsize=10)
        fig.tight_layout()
        charts["distributions"] = _to_base64(fig)

        fig, axis = plt.subplots(figsize=(max(8, len(numeric) * 1.25), 5))
        _style(fig)
        sns.boxplot(data=frame[numeric], ax=axis, color="#22d3ee")
        axis.set_title("Numeric Outlier Overview", pad=14, fontweight="bold")
        axis.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        charts["boxplots"] = _to_base64(fig)

    if categorical:
        fig, axes = plt.subplots(len(categorical), 1, figsize=(9, max(3, 3 * len(categorical))))
        axes = [axes] if len(categorical) == 1 else axes
        _style(fig)
        for axis, column in zip(axes, categorical):
            counts = frame[column].astype(str).value_counts().head(10)
            sns.barplot(x=counts.values, y=counts.index, hue=counts.index, legend=False, palette="viridis", ax=axis)
            axis.set_title(f"Top categories: {column}", loc="left", fontsize=10)
            axis.set_xlabel("Count")
            axis.set_ylabel("")
        fig.tight_layout()
        charts["categories"] = _to_base64(fig)
    return charts
