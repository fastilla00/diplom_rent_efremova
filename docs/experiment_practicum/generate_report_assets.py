"""
Генерация таблиц и графиков для отчёта по практике (эксперимент с ML-прогнозом рентабельности).

Запуск из корня репозитория:
  Windows (PowerShell):
    cd backend; $env:PYTHONPATH="."; python ..\\docs\\experiment_practicum\\generate_report_assets.py

Проверка:
  pytest tests/test_forecast_ml.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# backend как корень импорта
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.services.forecast.constants import BACKTEST_HOLDOUT_MONTHS, MAX_TRAIN_MONTHS
from app.services.forecast.features import build_features
from app.services.forecast.metrics import mae, wape
from app.services.forecast.validation import collect_model_scores, pick_best_model_id, walk_forward_true_pred_arima_family
from app.services.forecast.models_arima import forecast_arima
from app.services.forecast.ensemble import forecast_ensemble


OUT = Path(__file__).resolve().parent / "out"
RNG_SEED = 42
N_MONTHS = 42
HOLDOUT = BACKTEST_HOLDOUT_MONTHS


def synthetic_monthly_df(n_months: int = N_MONTHS, seed: int = RNG_SEED) -> pd.DataFrame:
    """Синтетические помесячные метрики: тренд + годовая сезонность + шум (проверяемые диапазоны в отчёте)."""
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2022-01-01", periods=n_months, freq="MS")
    t = np.arange(n_months, dtype=float)
    seasonal = 2.2 * np.sin(2 * np.pi * (t % 12.0) / 12.0)
    trend = 0.06 * t
    noise = rng.normal(0.0, 0.65, n_months)
    profitability = np.clip(8.0 + trend + seasonal + noise, 2.0, 22.0)

    base_rev = 120_000.0 + 800.0 * t + rng.normal(0.0, 2500.0, n_months)
    revenue = np.maximum(base_rev, 50_000.0)
    costs = revenue * (1.0 - profitability / 100.0)

    df = pd.DataFrame(
        {
            "period": periods,
            "year": periods.year,
            "month": periods.month,
            "revenue": revenue.astype(float),
            "costs": costs.astype(float),
            "profitability": profitability.astype(float),
        }
    )
    return df.sort_values("period").reset_index(drop=True)


def walk_forward_naive_one_step(series: pd.Series, holdout: int = HOLDOUT) -> tuple[list[float], list[float]]:
    """Наивный бейзлайн: прогноз на месяц вперёд = последнее наблюдённое значение (persistent)."""
    s = series.dropna()
    if len(s) < holdout + 5:
        return [], []
    h = min(holdout, len(s) - 4)
    y_true: list[float] = []
    y_pred: list[float] = []
    for i in range(len(s) - h, len(s)):
        y_true.append(float(s.iloc[i]))
        y_pred.append(float(s.iloc[i - 1]))
    return y_true, y_pred


def ensemble_holdout_preds(df_feat: pd.DataFrame, series: pd.Series, holdout: int) -> list[float]:
    """Путь прогнозов ансамбля на holdout (как в проде: ARIMA + CatBoost, `forecast_ensemble`)."""
    s = series.dropna()
    if len(s) < holdout + 5:
        return []
    h = min(holdout, len(s) - 4)
    preds: list[float] = []
    for i in range(len(s) - h, len(s)):
        last_obs = s.index[i - 1]
        sub = df_feat[df_feat["period"] <= last_obs].copy()
        if len(sub) < 4:
            continue
        last_period = pd.Timestamp(sub["period"].iloc[-1])
        row_df = sub.tail(MAX_TRAIN_MONTHS)
        _, _, ens = forecast_ensemble(row_df, horizon=1, last_period=last_period)
        if ens:
            preds.append(float(ens[0]))
        else:
            preds.append(float(s.iloc[i - 1]))
    return preds


def figure_timeseries(df: pd.DataFrame, split_idx: int, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=120)
    ax.plot(df["period"], df["profitability"], color="#1f77b4", linewidth=1.8, label="Рентабельность, %")
    split_ts = df["period"].iloc[split_idx]
    ax.axvline(split_ts, color="#d62728", linestyle="--", linewidth=1.5, label="Граница hold-out (6 мес.)")
    ax.set_xlabel("Период (месяц)")
    ax.set_ylabel("Рентабельность, %")
    ax.set_title("Синтетический ряд рентабельности для эксперимента")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def figure_metrics_bars(rows: list[tuple[str, float]], path: Path) -> None:
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = ["#7f7f7f" if "наивн" in x.lower() or "naive" in x.lower() else "#2ca02c" for x in labels]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=120)
    ax.bar(labels, vals, color=colors, edgecolor="#333", linewidth=0.4)
    ax.set_ylabel("MAE на hold-out, п.п.")
    ax.set_title("Сравнение моделей с наивным бейзлайном (walk-forward, один шаг)")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def figure_holdout_lines(
    periods: list[pd.Timestamp], y_true: list[float], y_ens: list[float], y_naive: list[float], path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=120)
    ax.plot(periods, y_true, "o-", color="#1f77b4", label="Факт (тест)")
    ax.plot(periods, y_naive, "s--", color="#7f7f7f", label="Наивный бейзлайн")
    ax.plot(periods, y_ens, "^-", color="#ff7f0e", label="Ансамбль (ARIMA + CatBoost)")
    ax.set_xlabel("Период (месяц)")
    ax.set_ylabel("Рентабельность, %")
    ax.set_title("Hold-out: факт vs ансамбль vs наивный прогноз")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def figure_wape_bars(rows: list[tuple[str, float | None]], path: Path) -> None:
    labels = [r[0] for r in rows]
    vals = [0.0 if r[1] is None else float(r[1]) for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=120)
    ax.bar(labels, vals, color="#9467bd", edgecolor="#333", linewidth=0.4)
    ax.set_ylabel("WAPE (относительная ошибка)")
    ax.set_title("WAPE по моделям на последних 6 месяцах")
    ax.tick_params(axis="x", rotation=22)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def run_pytest_capture() -> str:
    try:
        # --disable-warnings: в полном pytest часто сыпется DeprecationWarning из Pydantic
        # при импорте моделей приложения — это не про тесты прогноза и путает в отчёте.
        env = {**os.environ, "PYTHONWARNINGS": "ignore"}
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_forecast_ml.py",
                "-q",
                "--tb=no",
                "--disable-warnings",
            ],
            cwd=str(_BACKEND),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        if err and err not in out:
            out = f"{out}\n{err}" if out else err
        return f"exit={p.returncode}\n{out}"
    except Exception as e:
        return f"pytest_error: {e}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    df = synthetic_monthly_df()
    df_feat = build_features(df).dropna(subset=["lag_1"]).reset_index(drop=True)
    series = df_feat.set_index("period")["profitability"]

    scores = collect_model_scores(df_feat, series)
    best_id = pick_best_model_id(scores, prefer_wape=True) or "arima"

    yt_naive, yp_naive = walk_forward_naive_one_step(series, HOLDOUT)
    yt_arima, yp_arima = walk_forward_true_pred_arima_family(series, forecast_arima, HOLDOUT)

    # Ансамбль на каждом шаге hold-out
    yp_ens = ensemble_holdout_preds(df_feat, series, HOLDOUT)
    yt_common = yt_naive
    if len(yp_ens) != len(yt_common):
        # подрезаем к общей длине
        m = min(len(yp_ens), len(yt_common))
        yt_common = yt_common[-m:]
        yp_naive = yp_naive[-m:]
        yp_ens = yp_ens[-m:]
        yp_arima = yp_arima[-m:] if len(yp_arima) >= m else yp_arima

    mae_naive = mae(np.array(yt_common), np.array(yp_naive))
    wape_naive = wape(np.array(yt_common), np.array(yp_naive))
    mae_ens = mae(np.array(yt_common), np.array(yp_ens)) if yp_ens else float("nan")
    wape_ens = wape(np.array(yt_common), np.array(yp_ens)) if yp_ens else None

    # Таблица метрик из scores + naive + ensemble manual
    table_rows: list[dict[str, object]] = []
    for mid, sc in scores.items():
        if not sc:
            continue
        table_rows.append(
            {
                "model": mid,
                "MAE": sc.get("backtest_mae"),
                "WAPE": sc.get("backtest_wape"),
                "N": sc.get("backtest_n"),
            }
        )
    table_rows.append({"model": "naive_persistent", "MAE": mae_naive, "WAPE": wape_naive, "N": len(yt_common)})
    if yp_ens:
        table_rows.append(
            {"model": "ensemble_arima_catboost (replayed)", "MAE": mae_ens, "WAPE": wape_ens, "N": len(yt_common)}
        )

    # MAE bar chart data
    bar_mae: list[tuple[str, float]] = [("наивный", mae_naive)]
    for mid in ("arima", "sarimax", "catboost", "lightgbm", "prophet"):
        sc = scores.get(mid) or {}
        v = sc.get("backtest_mae")
        if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
            bar_mae.append((mid, float(v)))
    if yp_ens and not np.isnan(mae_ens):
        bar_mae.append(("ансамбль (replay)", float(mae_ens)))

    bar_wape: list[tuple[str, float | None]] = [("наивный", wape_naive)]
    for mid in ("arima", "sarimax", "catboost", "lightgbm", "prophet"):
        sc = scores.get(mid) or {}
        bar_wape.append((mid, sc.get("backtest_wape")))

    split_idx = max(0, len(df) - HOLDOUT)
    figure_timeseries(df, split_idx, OUT / "fig1_timeseries.png")
    figure_metrics_bars(bar_mae, OUT / "fig2_mae_models.png")

    hold_periods = list(df_feat["period"].tail(HOLDOUT))
    if len(hold_periods) > len(yt_common):
        hold_periods = hold_periods[-len(yt_common) :]
    figure_holdout_lines(hold_periods, yt_common, yp_ens, yp_naive, OUT / "fig3_holdout_lines.png")
    figure_wape_bars(bar_wape, OUT / "fig4_wape_models.png")

    params = [
        {"parameter": "Длина ряда (месяцев)", "value": N_MONTHS, "range_or_note": "36–48 (здесь 42)"},
        {"parameter": "Hold-out (walk-forward)", "value": HOLDOUT, "range_or_note": "4–8 (как в коде: 6)"},
        {"parameter": "Амплитуда сезонности, п.п.", "value": 2.2, "range_or_note": "1.5–3.5"},
        {"parameter": "Наклон тренда (лин. компонента)", "value": 0.06, "range_or_note": "0.02–0.12"},
        {"parameter": "σ шума", "value": 0.65, "range_or_note": "0.3–1.2"},
        {"parameter": "CatBoost: iterations / depth / lr", "value": "200 / 5 / 0.05", "range_or_note": "как в validation.py"},
        {"parameter": "seed RNG", "value": RNG_SEED, "range_or_note": "фиксирован для воспроизводимости"},
    ]
    (OUT / "table_parameters.json").write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "table_metrics.json").write_text(json.dumps(table_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    pytest_log = run_pytest_capture()
    (OUT / "verification_pytest.txt").write_text(pytest_log, encoding="utf-8")

    # Проверки «верификации» внутри пайплайна
    checks = [
        ("len(df) >= MIN_HISTORY", bool(len(df_feat) >= 12)),
        ("collect_model_scores non-empty", bool(any(scores.values()))),
        (
            "figures exist",
            bool(
                all((OUT / n).exists() for n in ("fig1_timeseries.png", "fig2_mae_models.png", "fig3_holdout_lines.png", "fig4_wape_models.png"))
            ),
        ),
        ("naive mae finite", bool(np.isfinite(mae_naive))),
    ]
    (OUT / "verification_checks.json").write_text(
        json.dumps({k: bool(v) for k, v in checks}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Markdown отчёт
    def fmt_num(x: object) -> str:
        if x is None:
            return "—"
        if isinstance(x, float):
            if np.isnan(x):
                return "—"
            return f"{x:.4f}"
        return str(x)

    h1_text = ""
    if wape_ens is not None and wape_naive is not None:
        if float(wape_ens) < float(wape_naive):
            h1_text = f"**Результат на этом прогоне:** WAPE ансамбля = {fmt_num(wape_ens)}, наивного = {fmt_num(wape_naive)} → H1 **принимается** при сравнении с наивным бейзлайном (ошибка ансамбля меньше). Лучшая одиночная модель по автоматической метрике валидации: `{best_id}`."
        else:
            h1_text = f"**Результат на этом прогоне:** WAPE ансамбля = {fmt_num(wape_ens)} не меньше наивного ({fmt_num(wape_naive)}) → на данном ряду улучшение ансамбля **не подтверждено**; сравнение с одиночными моделями см. таблицу 2. Лучший автоматический выбор: `{best_id}`."
    else:
        h1_text = f"**Результат:** метрики WAPE для ансамбля недоступны; ориентир — таблица 2 и модель `{best_id}`."

    md_lines = [
        "# Отчёт: эксперимент по прогнозированию рентабельности (практика)",
        "",
        "Документ сформирован автоматически скриптом `generate_report_assets.py` на основе кода сервиса прогноза (`backend/app/services/forecast/*`).",
        "",
        "## 1. План эксперимента и ключевые параметры",
        "",
        "Цель: сравнить качество **walk-forward one-step** прогноза рентабельности (%) для статистических и ML-моделей относительно **наивного бейзлайна** (прогноз = значение предыдущего месяца).",
        "",
        "**Схема валидации:** для каждого из последних `H` месяцев модель обучается только на префиксе ряда и предсказывает один шаг вперёд; затем считаются **MAE** и **WAPE**.",
        "",
        f"**Выбранный лучший идентификатор по WAPE на валидации (автовыбор как в `pick_best_model_id`):** `{best_id}`.",
        "",
        "### Таблица 1. Параметры эксперимента и диапазоны",
        "",
        "| Параметр | Значение в прогоне | Диапазон / комментарий |",
        "|----------|-------------------|-------------------------|",
    ]
    for p in params:
        md_lines.append(f"| {p['parameter']} | {p['value']} | {p['range_or_note']} |")
    md_lines += [
        "",
        "## 2. Численные результаты",
        "",
        "### Таблица 2. Метрики hold-out по моделям",
        "",
        "| Модель | MAE | WAPE | N |",
        "|--------|-----|------|---|",
    ]
    for row in table_rows:
        md_lines.append(
            f"| {row['model']} | {fmt_num(row.get('MAE'))} | {fmt_num(row.get('WAPE'))} | {fmt_num(row.get('N'))} |"
        )

    md_lines += [
        "",
        "## 3. Графики",
        "",
        "### Рисунок 1. Исходный ряд и зона hold-out",
        f"![Временной ряд](out/fig1_timeseries.png)",
        "",
        "### Рисунок 2. MAE: модели и наивный бейзлайн",
        f"![MAE по моделям](out/fig2_mae_models.png)",
        "",
        "### Рисунок 3. Траектории на hold-out",
        f"![Факт vs ансамбль vs наивный](out/fig3_holdout_lines.png)",
        "",
        "### Рисунок 4. WAPE по моделям (дополнительно)",
        f"![WAPE](out/fig4_wape_models.png)",
        "",
        "## 4. Научная гипотеза и её проверка",
        "",
        "- **Гипотеза H1:** при наличии тренда и годовой сезонности в помесячной рентабельности комбинированный прогноз (**ансамбль ARIMA + CatBoost**) даёт **ниже WAPE/MAE** на walk-forward hold-out, чем **наивный перенос последнего значения**.",
        "- **Нулевая гипотеза H0:** различий по WAPE/MAE нет (наивный метод не хуже).",
        "",
        h1_text,
        "",
        "## 5. Анализ и сравнение с бейзлайном / «конкурентами»",
        "",
        f"- **Наивный бейзлайн:** MAE = {mae_naive:.4f} п.п., WAPE = {fmt_num(wape_naive)}.",
        f"- **Ансамбль (ARIMA + CatBoost, воспроизведение шага как в `forecast_ensemble`):** MAE = {fmt_num(mae_ens)}, WAPE = {fmt_num(wape_ens)}.",
        "",
        "**Интерпретация:** если WAPE/MAE ансамбля ниже, чем у наивного метода, это подтверждает рабочую гипотезу, что комбинация линейно-стохастической структуры (ARIMA) и нелинейных признаков (CatBoost) **извлекает сигнал сверх простого переноса последнего значения**. Если на конкретном синтетическом ряде лучше оказывается отдельная модель из таблицы — это не противоречит практике: автоматический выбор (`pick_best_model_id`) как раз предназначен для таких случаев.",
        "",
        "**Сравнение с «конкурентами»:** в таблице 2 приведены ARIMA, SARIMAX, CatBoost, LightGBM, Prophet — все обучаются в одной схеме backtest, что даёт сопоставимую оценку качества.",
        "",
        "## 6. Верификация корректности",
        "",
        "### 6.1. Автоматические проверки генератора",
        "",
        "```json",
        json.dumps({k: v for k, v in checks}, ensure_ascii=False, indent=2),
        "```",
        "",
        "### 6.2. Регрессионные тесты проекта",
        "",
        "Вывод `pytest tests/test_forecast_ml.py -q --tb=no --disable-warnings` при `PYTHONWARNINGS=ignore` в подпроцессе (файл `out/verification_pytest.txt`). Так в лог не попадают предупреждения **зависимостей** (например, Pydantic при импорте моделей); сами проверки прогноза те же, `exit=0` и число пройденных тестов — показатель успеха.",
        "",
        "```text",
        pytest_log[:4000],
        "```",
        "",
        "---",
        "",
        "*Конец отчёта.*",
    ]

    report_path = Path(__file__).resolve().parent / "otchet_eksperiment_praktika.md"
    report_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"OK: wrote {report_path} and figures to {OUT}")


if __name__ == "__main__":
    main()
