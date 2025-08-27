from __future__ import annotations
from typing import Dict, Any, Iterable, List, Tuple, Optional
from datetime import datetime
import math

try:
    import numpy as np
except Exception:
    np = None

# SciPy가 있으면 GEV 사용, 없으면 경험적 분위수로 대체
try:
    from scipy.stats import genextreme as GEV  # type: ignore

    _HAS_SCIPY = True
except Exception:
    _HAS_SCIPY = False


def _month_key(ts: datetime) -> str:
    return f"{ts.year:04d}-{ts.month:02d}"


def _block_maxima(ts: Iterable[datetime], x: Iterable[float]) -> Tuple[List[str], List[float]]:
    by_m: Dict[str, float] = {}
    for t, v in zip(ts, x):
        if not isinstance(t, datetime):
            continue
        if v is None:
            continue
        try:
            fv = float(v)
        except Exception:
            continue
        if not math.isfinite(fv):
            continue
        key = _month_key(t)
        prev = by_m.get(key, float("-inf"))
        by_m[key] = fv if fv > prev else prev
    months = sorted(by_m.keys())
    return months, [by_m[m] for m in months]


def _np_quantile(arr: List[float], q: float) -> float:
    if not arr:
        return float("nan")
    if np is None:
        s = sorted(arr)
        i = min(len(s) - 1, max(0, int(round((len(s) - 1) * q))))
        return float(s[i])
    return float(np.quantile(np.asarray(arr, dtype=float), q))


def estimate_extremes(
    ts: List[datetime],
    power_kw: List[float],
    p_target: float = 0.98,
    q_high: float = 0.99,
) -> Dict[str, Any]:
    """
    월 블록 최대값에 GEV 적합(가능 시) 또는 분위수 대체.
    반환:
      - method: 'GEV' | 'Quantile'
      - months: ['YYYY-MM', ...]
      - blocks: [max_kw_per_month]
      - return_level: p_target 확률 수준의 월 최대 재현수준
      - q_high: 상위 분위수(진단용)
    """
    months, blocks = _block_maxima(ts, power_kw)
    if not blocks:
        return {
            "method": "NA",
            "months": [],
            "blocks": [],
            "return_level": None,
            "q_high": None,
            "p_target": p_target,
        }

    if _HAS_SCIPY and len(blocks) >= 8:
        # 블록 최대에 GEV 적합
        c, loc, scale = GEV.fit(blocks)  # shape, loc, scale
        rl = float(GEV.ppf(p_target, c, loc=loc, scale=scale))
        qh = float(GEV.ppf(q_high, c, loc=loc, scale=scale))
        return {
            "method": "GEV",
            "params": {"shape": float(c), "loc": float(loc), "scale": float(scale)},
            "months": months,
            "blocks": blocks,
            "return_level": rl,
            "q_high": qh,
            "p_target": p_target,
        }

    # Fallback: 경험적 분위수
    qh = _np_quantile(blocks, q_high)
    rl = _np_quantile(blocks, p_target)
    return {
        "method": "Quantile",
        "months": months,
        "blocks": blocks,
        "return_level": float(rl) if math.isfinite(rl) else None,
        "q_high": float(qh) if math.isfinite(qh) else None,
        "p_target": p_target,
    }


def estimate_extremes_from_df(
    df,
    ts_candidates: Optional[List[str]] = None,
    power_candidates: Optional[List[str]] = None,
    p_target: float = 0.98,
    q_high: float = 0.99,
) -> Dict[str, Any]:
    """
    DataFrame에서 시계열을 추출해 EVT 적용.
    ts_candidates: 타임스탬프 컬럼 후보
    power_candidates: 전력(kW) 컬럼 후보
    """
    ts_candidates = ts_candidates or [
        "timestamp",
        "time",
        "datetime",
        "event_time",
        "start_time",
        "session_start",
        "end_time",
        "session_end",
    ]
    power_candidates = power_candidates or [
        "power",
        "power_kw",
        "kw",
        "demand_kw",
        "max_power_kw",
        "peak_power_kw",
        "session_peak_kw",
    ]
    if df is None or df.empty:
        return {"method": "NA", "months": [], "blocks": [], "return_level": None, "q_high": None, "p_target": p_target}

    cols = {c.lower(): c for c in df.columns}
    ts_col = next((cols[c] for c in (c.lower() for c in ts_candidates) if c in cols), None)
    pw_col = next((cols[c] for c in (c.lower() for c in power_candidates) if c in cols), None)
    if ts_col is None or pw_col is None:
        return {"method": "NA", "months": [], "blocks": [], "return_level": None, "q_high": None, "p_target": p_target}

    # 파싱
    ts = []
    pw = []
    for _, row in df[[ts_col, pw_col]].dropna().iterrows():
        try:
            t = row[ts_col]
            if not isinstance(t, datetime):
                t = datetime.fromisoformat(str(t).replace("Z", "+00:00")) if "T" in str(t) else pd_to_datetime(t)
            v = float(row[pw_col])
            if math.isfinite(v):
                ts.append(t)
                pw.append(v)
        except Exception:
            continue

    return estimate_extremes(ts, pw, p_target=p_target, q_high=q_high)


def pd_to_datetime(x) -> datetime:
    # pandas Timestamp 호환
    try:
        return x.to_pydatetime()  # type: ignore
    except Exception:
        return datetime.fromisoformat(str(x))
