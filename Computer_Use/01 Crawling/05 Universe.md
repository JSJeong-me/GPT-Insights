네, **재활용 가능합니다.** 오히려 “Universe 스캐너”는 CTTR/Spread/OFI 같은 **미시구조 지표 계산 코드를 그대로 재사용**하고, 그 위에 **(1) 후보 종목 수집 → (2) 지표 계산 → (3) 스코어링/랭킹 → (4) Top 100 → (5) Excel 저장**만 얹는 구조가 가장 깔끔합니다.

아래는 “기존 CTTR/Spread 코드가 이미 있다”는 가정하에, **바로 재활용할 수 있게 모듈 경계/코드 스켈레톤**을 제시합니다.

---

## 재활용이 잘 되는 조건 (지금 코드가 이런 형태면 그대로 씁니다)

* CTTR/Spread/OFI 계산이 **순수 함수** 형태
  예) `cttr(df_ticks)->float`, `spread(lob)->float`
* 데이터 수집(KIS 호출/LOB 로더)과 지표 계산이 분리
  예) `fetch_*()` 와 `compute_*()`가 별도

만약 현재가 “Runner 안에 계산이 섞여있다”면, **계산 함수만 `features/`로 추출**하면 됩니다.

---

## 권장 아키텍처

* `universe/`

  * `scanner.py` : 후보 수집 + 병렬 계산 + 랭킹 + 저장
  * `data_sources.py` : KIS/로컬로그에서 데이터 로드
  * `features.py` : **기존 CTTR/Spread/OFI 계산 함수(재사용)**
  * `scoring.py` : 표준화(zscore) + 가중합/규칙 기반 점수
  * `export.py` : Excel 저장(서식 포함)

---

## Excel에 저장할 추천 스키마 (Top 100)

필수 컬럼 예시:

* `rank, symbol, name, market`
* `cttr, spread, ofi, obi, microprice_dev, vwap_dev`
* `liquidity_score, risk_score, final_score`
* `asof` (스캔 시각), `window` (예: last 10d)

---

## Playwright 자동입력과의 연결 포인트

* Universe 스캐너가 `universe_top100.xlsx`를 만들고
* POP 자동화는 이 엑셀에서 `symbol` 컬럼을 읽어 **100개 루프 입력+캡처**하면 됩니다.

---

## “바로 실행 가능한” Universe 스캐너 스켈레톤 (Python)

> 아래 코드는 **기존 CTTR/Spread 계산 함수를 끼워 넣는 자리**를 명확히 만들어둔 형태입니다.
> 데이터 로드는 “KIS” 또는 “기존에 저장해둔 LOB/tick jsonl” 중 아무거나로 바꿔 끼울 수 있습니다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universe Scanner (Top 100) -> Excel export

- Reuse existing CTTR / Spread / OFI feature calculators
- Fetch data per symbol (KIS or local logs)
- Score & rank
- Save to Excel (openpyxl formatting)

Run:
  python universe_scan.py --out ./universe_top100.xlsx --limit 100
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# -------------------------
# 1) CONFIG
# -------------------------

@dataclass
class UniverseScanConfig:
    limit: int = 100
    window_days: int = 10          # 예: 최근 2주(10거래일) 컨셉
    min_liquidity: float = 0.0     # 필요 시 거래대금/체결수 필터
    max_spread: Optional[float] = None
    workers: int = 8               # 병렬 처리 (thread/process는 상황에 맞게)
    asof: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# -------------------------
# 2) DATA SOURCE (stub)
# -------------------------

def load_candidates() -> pd.DataFrame:
    """
    후보 종목 목록 로더 (stub)

    반환 스키마 예:
      symbol, name, market
    - 이미 Universe 후보(예: KOSPI200, KOSDAQ150, 거래대금 상위 N) 리스트가 있으면 여기서 불러오면 됨
    """
    # TODO: 사용자 환경에 맞게 구현:
    # - KRX 마스터/기보유 리스트/DB/파일 등에서 로드
    return pd.DataFrame([
        {"symbol": "005930", "name": "삼성전자", "market": "KOSPI"},
        {"symbol": "000660", "name": "SK하이닉스", "market": "KOSPI"},
        {"symbol": "015760", "name": "한국전력", "market": "KOSPI"},
    ])


def fetch_symbol_data(symbol: str, window_days: int) -> Dict[str, pd.DataFrame]:
    """
    종목별 데이터 로더 (stub)

    반환 예:
      {
        "ticks": DataFrame,    # 체결/호가 기반이면
        "lob": DataFrame,      # LOB 스냅샷이면
        "minutes": DataFrame,  # 분봉이면
      }

    - 여기서 기존 KIS fetch 함수(예: fetch_intraday_minutes_from_kis 등) 또는
      로컬에 저장된 jsonl/npz/parquet 로더를 연결하면 됨.
    """
    # TODO: implement
    return {}


# -------------------------
# 3) FEATURE COMPUTATION (reuse your existing code here)
# -------------------------

def compute_features(symbol: str, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    """
    기존 CTTR/Spread/OFI 계산 코드를 여기에 "그대로" 연결하세요.

    예:
      cttr = calc_cttr_from_lob(data["lob"])
      spr  = calc_spread_from_lob(data["lob"])
      ofi  = calc_ofi_from_lob(data["lob"])
    """
    # TODO: replace these stubs with your real functions
    cttr = float("nan")
    spread = float("nan")
    ofi = float("nan")

    # (선택) 유동성 지표: 거래대금/체결수/호가잔량 등
    liquidity = float("nan")

    return {
        "cttr": cttr,
        "spread": spread,
        "ofi": ofi,
        "liquidity": liquidity,
    }


# -------------------------
# 4) SCORING / RANKING
# -------------------------

def zscore(series: pd.Series) -> pd.Series:
    mu = series.mean(skipna=True)
    sd = series.std(skipna=True)
    if sd == 0 or pd.isna(sd):
        return series * 0.0
    return (series - mu) / sd


def score_universe(df: pd.DataFrame) -> pd.DataFrame:
    """
    점수 예시 (원칙만 제시)
    - spread는 낮을수록 좋음 => -z
    - cttr/ofi/liquidity는 높을수록 좋음 => +z
    """
    out = df.copy()

    out["z_cttr"] = zscore(out["cttr"])
    out["z_ofi"] = zscore(out["ofi"])
    out["z_liq"] = zscore(out["liquidity"])
    out["z_spread"] = zscore(out["spread"])

    # 가중치는 운영 경험에 맞게 조정
    out["final_score"] = (
        0.35 * out["z_liq"] +
        0.30 * out["z_ofi"] +
        0.20 * out["z_cttr"] +
        0.15 * (-out["z_spread"])
    )

    out = out.sort_values("final_score", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out


# -------------------------
# 5) EXPORT to EXCEL (with minimal formatting)
# -------------------------

def save_to_excel(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="universe_top")
        ws = writer.sheets["universe_top"]

        # Freeze header
        ws.freeze_panes = "A2"

        # Auto filter
        ws.auto_filter.ref = ws.dimensions

        # Simple column width
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col[:200]:  # cap
                if cell.value is None:
                    continue
                max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 40)


# -------------------------
# 6) MAIN
# -------------------------

def run_scan(cfg: UniverseScanConfig) -> pd.DataFrame:
    candidates = load_candidates()
    rows: List[Dict[str, object]] = []

    # 간단 단일 스레드 버전 (필요하면 ThreadPool로 병렬화)
    for _, r in candidates.iterrows():
        symbol = r["symbol"]
        name = r.get("name", "")
        market = r.get("market", "")

        try:
            data = fetch_symbol_data(symbol, cfg.window_days)
            feats = compute_features(symbol, data)
            rows.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                **feats,
                "asof": cfg.asof,
                "window_days": cfg.window_days,
            })
        except Exception as e:
            rows.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                "cttr": float("nan"),
                "spread": float("nan"),
                "ofi": float("nan"),
                "liquidity": float("nan"),
                "error": str(e),
                "asof": cfg.asof,
                "window_days": cfg.window_days,
            })

    df = pd.DataFrame(rows)

    # (선택) 필터링 예시
    if cfg.max_spread is not None:
        df = df[df["spread"].isna() | (df["spread"] <= cfg.max_spread)]

    scored = score_universe(df)
    top = scored.head(cfg.limit).copy()
    return top


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./universe_top100.xlsx")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--window-days", type=int, default=10)
    ap.add_argument("--max-spread", type=float, default=None)
    return ap.parse_args()


def main():
    args = parse_args()
    cfg = UniverseScanConfig(
        limit=args.limit,
        window_days=args.window_days,
        max_spread=args.max_spread,
    )

    top = run_scan(cfg)
    out_path = Path(args.out)
    save_to_excel(top, out_path)
    print(f"[OK] saved: {out_path.resolve()}  rows={len(top)}")


if __name__ == "__main__":
    main()
```

---

## “기존 코드 재활용”을 실제로 연결하는 방법 (핵심 2곳만 바꾸면 됨)

1. `fetch_symbol_data()`

   * 기존에 **LOB jsonl**을 저장해 둔 경로가 있으면 그걸 읽어서 `data["lob"]`로 반환
   * 또는 기존 **KIS 분봉/tick fetch 함수**를 호출해서 `data["minutes"]` / `data["ticks"]`로 반환

2. `compute_features()`

   * 기존 CTTR/Spread/OFI 함수 호출만 붙이면 끝
   * 예:

     * `spread = calc_spread_from_lob(df_lob)`
     * `cttr = calc_cttr(df_ticks or df_lob)`
     * `ofi = calc_ofi(df_lob)`

---

## 다음 단계 (POP 자동캡처까지 연결)

Universe 엑셀 생성이 끝나면 POP 자동화 쪽에서:

* `pd.read_excel(universe_top100.xlsx)["symbol"].tolist()`로 100개 종목 읽어서
* 이전 Playwright 코드에 “for symbol in symbols: 입력→Enter→팝업캡처” 루프만 추가하면 됩니다.

---

원하시면 제가 **당신이 이미 갖고 있는 CTTR/Spread 계산 함수 시그니처**(예: `calc_cttr_from_lob(lob_df)` 같은 형태)만 가정해서, 위 스켈레톤에 **ThreadPool 병렬 스캔 + 캐시(이미 계산한 종목은 재계산 X) + Excel에 요약 시트(분포/상위10)**까지 포함한 “실전판”으로 확장해드릴게요.
