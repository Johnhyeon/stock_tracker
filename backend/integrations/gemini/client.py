"""Google Gemini AI 클라이언트."""
import asyncio
import json
import logging
from typing import Optional

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

_gemini_client: Optional["GeminiClient"] = None


class GeminiClient:
    """Google Gemini API 클라이언트."""

    def __init__(self):
        self.settings = get_settings()
        self._api_key = getattr(self.settings, "gemini_api_key", None)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.0-flash"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def _generate(self, prompt: str, max_retries: int = 4) -> Optional[str]:
        """Gemini API 호출. 429 시 지수 백오프 재시도."""
        if not self.is_configured:
            return None

        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            },
        }

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        url,
                        params={"key": self._api_key},
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()

                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries:
                    # Retry-After 헤더 존중, 없으면 지수 백오프 (2, 4, 8, 16초)
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait = min(int(retry_after), 30)
                    else:
                        wait = 2 ** (attempt + 1)  # 2, 4, 8, 16초
                    logger.warning(
                        f"Gemini 429 → {wait}초 후 재시도 ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"Gemini API 호출 실패: {e}")
                break
            except Exception as e:
                logger.error(f"Gemini API 호출 실패: {e}")
                break

        return None

    def _parse_json_response(self, text: str) -> Optional[dict]:
        """Gemini 응답에서 JSON 추출."""
        if not text:
            return None

        # JSON 블록 추출
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"JSON 파싱 실패: {text[:200]}")
            return None

    async def extract_entities(self, text: str) -> Optional[dict]:
        """텍스트에서 종목/테마 엔티티 추출."""
        prompt = f"""다음 한국 주식 관련 텍스트에서 종목과 테마를 추출해주세요.

텍스트:
{text}

JSON 형식으로 응답해주세요:
{{
    "stocks": [
        {{"code": "종목코드(6자리)", "name": "종목명", "context": "언급 맥락"}}
    ],
    "themes": ["테마1", "테마2"]
}}

종목코드를 모르면 code를 빈 문자열로, 종목이 없으면 빈 배열로 응답하세요."""

        result = await self._generate(prompt)
        return self._parse_json_response(result)

    async def analyze_chart_signal(
        self,
        stock_code: str,
        stock_name: str,
        ohlcv_summary: dict,
        signal_data: dict,
    ) -> Optional[dict]:
        """차트 매매 규칙 기반 AI 분석."""
        prompt = f"""당신은 차트 매매 규칙에 정통한 한국 주식 차트 분석 전문가입니다.

## 핵심 매매 규칙
1. **ABCD 매매법**: A(신고거래량 기준봉) → B(1차돌파) → C(눌림+정배열전환, 최적 매수구간) → D(재돌파)
2. **이평선**: 5/20/60/120일선. 역배열→정배열 전환이 C구간의 핵심 신호
3. **갭 분류**: 보통갭(메워짐), 돌파갭(바닥탈출, 강력매수), 진행갭(추세가속), 소멸갭(천장주의)
4. **깬돌지**: 지지선 이탈 후 재돌파하며 지지 확인 → 강한 매수 신호
5. **진입 원칙**: 정배열+MA20근접+거래량수축 = 이상적 눌림목 매수 조건
6. **손절 원칙**: MA20 이탈 시 경고, 기준봉 저점 이탈 시 손절

## 분석 대상: {stock_name} ({stock_code})

### 자동 분석 결과
- ABCD 구간: {signal_data.get('abcd_phase', 'unknown')}
- 이평선 배열: {signal_data.get('ma_alignment', 'mixed')}
- 갭 상태: {signal_data.get('gap_type', 'none')}
- 깬돌지: {'있음' if signal_data.get('has_kkandolji') else '없음'}
- 총점: {signal_data.get('total_score', 0)}/100 (등급 {signal_data.get('grade', 'D')})

### 가격/지표 데이터
- 현재가: {ohlcv_summary.get('current_price', 0):,}원
- MA5: {ohlcv_summary.get('ma5', '-')}, MA20: {ohlcv_summary.get('ma20', '-')}, MA60: {ohlcv_summary.get('ma60', '-')}, MA120: {ohlcv_summary.get('ma120', '-')}
- 거래량비(당일/20일평균): {ohlcv_summary.get('volume_ratio', 1.0)}x
- 60일 고가: {ohlcv_summary.get('high_60d', 0):,}원, 60일 저가: {ohlcv_summary.get('low_60d', 0):,}원

### 최근 5일 캔들
{self._format_candles(ohlcv_summary.get('recent_candles', []))}

JSON 형식으로 응답해주세요:
{{
    "abcd_phase": "A/B/C/D 중 하나",
    "phase_description": "현재 구간에 대한 설명 (2-3문장)",
    "entry_recommendation": "적극매수/매수대기/관망/매도검토 중 하나",
    "risk_assessment": "낮음/보통/높음 중 하나",
    "key_observations": ["핵심 관찰 1", "핵심 관찰 2", "핵심 관찰 3"],
    "entry_conditions": ["진입 조건 1", "진입 조건 2"],
    "exit_conditions": ["청산 조건 1", "청산 조건 2"],
    "confidence": 0.0~1.0
}}"""

        result = await self._generate(prompt)
        return self._parse_json_response(result)

    def _format_candles(self, candles: list) -> str:
        """캔들 데이터를 텍스트로 포맷."""
        if not candles:
            return "데이터 없음"
        lines = []
        for c in candles:
            change = ""
            if c.get("open") and c["open"] > 0:
                pct = (c["close"] - c["open"]) / c["open"] * 100
                change = f" ({pct:+.1f}%)"
            lines.append(
                f"  {c.get('date', '?')}: 시{c.get('open', 0):,} 고{c.get('high', 0):,} "
                f"저{c.get('low', 0):,} 종{c.get('close', 0):,}{change} "
                f"거래량{c.get('volume', 0):,}"
            )
        return "\n".join(lines)

    async def analyze_narrative_briefing(
        self,
        stock_code: str,
        stock_name: str,
        profile_data: dict,
    ) -> Optional[dict]:
        """종목 내러티브 브리핑 생성."""
        # 프로필 데이터 요약 생성
        ohlcv = profile_data.get("ohlcv", {})
        flow = profile_data.get("investor_flow", {})
        youtube = profile_data.get("youtube_mentions", {})
        expert = profile_data.get("expert_mentions", {})
        disclosures = profile_data.get("disclosures", [])
        ideas = profile_data.get("telegram_ideas", [])
        sentiment = profile_data.get("sentiment", {})
        themes = profile_data.get("themes", [])
        financial = profile_data.get("financial_summary", {})

        # 공시 제목 목록
        disc_titles = [d.get("title", "") for d in disclosures[:5]] if disclosures else []
        # 텔레그램 아이디어 요약
        idea_summaries = [i.get("message_text", "")[:100] for i in ideas[:3]] if ideas else []

        # 재무 섹션 구성
        fin_has_data = financial.get("has_data", False)
        if fin_has_data:
            def _fmt_amt(v):
                if v is None:
                    return "N/A"
                if abs(v) >= 1_0000_0000:
                    return f"{v / 1_0000_0000:.1f}억"
                elif abs(v) >= 1_0000:
                    return f"{v / 1_0000:.0f}만"
                return str(v)

            def _fmt_pct(v):
                return f"{v:+.1f}%" if v is not None else "N/A"

            # 연간 추세 포맷
            annual_trend = financial.get("annual_trend", [])
            trend_lines = []
            for t in annual_trend:
                trend_lines.append(
                    f"  {t['year']}년: 매출 {_fmt_amt(t.get('revenue'))}, "
                    f"영업이익 {_fmt_amt(t.get('operating_income'))}, "
                    f"순이익 {_fmt_amt(t.get('net_income'))}"
                )
            trend_section = "\n".join(trend_lines) if trend_lines else "  데이터 없음"

            fin_section = f"""### 재무 요약

**최신 보고서: {financial.get('latest_period', '?')}** (전년 동기 대비)
- 매출: {_fmt_amt(financial.get('revenue'))} (YoY {_fmt_pct(financial.get('revenue_growth_yoy'))})
- 영업이익: {_fmt_amt(financial.get('operating_income'))} (YoY {_fmt_pct(financial.get('oi_growth_yoy'))})
- 순이익: {_fmt_amt(financial.get('net_income'))} (YoY {_fmt_pct(financial.get('ni_growth_yoy'))})
- 흑자여부: {'흑자' if financial.get('is_profitable') else '적자'}
- 매출성장: {'성장' if financial.get('is_growing') else '감소/정체'}

**연간 실적 추이**
{trend_section}

**수익성 (최신 보고서 기준)**
- ROE: {_fmt_pct(financial.get('roe'))}, ROA: {_fmt_pct(financial.get('roa'))}
- 영업이익률: {_fmt_pct(financial.get('operating_margin'))}, 순이익률: {_fmt_pct(financial.get('net_margin'))}
- 마진 추세: {financial.get('margin_trend', 'N/A')} (improving=개선, stable=안정, deteriorating=악화)

**재무건전성**
- 부채비율: {_fmt_pct(financial.get('debt_ratio'))}, 유동비율: {_fmt_pct(financial.get('current_ratio'))}
- 총자산: {_fmt_amt(financial.get('total_assets'))}, 자본총계: {_fmt_amt(financial.get('total_equity'))}"""
        else:
            fin_section = """### 재무 요약
- 재무 데이터 없음"""

        prompt = f"""당신은 한국 주식 시장 전문 애널리스트입니다. 아래 데이터를 종합하여 투자자가 이 종목의 "내러티브(이야기)"를 빠르게 이해할 수 있도록 브리핑을 작성해주세요.

## 종목: {stock_name} ({stock_code})

### 가격/거래 데이터
- 최근 종가: {ohlcv.get('latest_price', '?')}원
- 등락률: {ohlcv.get('change_rate', '?')}%
- 거래량: {ohlcv.get('volume', '?')}

### 수급 데이터
- 외국인 10일 순매수: {flow.get('foreign_net_total', '?')}
- 기관 10일 순매수: {flow.get('institution_net_total', '?')}
- 외국인 연속 매수: {flow.get('consecutive_foreign_buy', 0)}일

### 소셜/언급 데이터
- 유튜브 영상 수: {youtube.get('video_count', 0)}건 (14일)
- 전문가 언급: {expert.get('total_mentions', 0)}건 (14일)
- 텔레그램 아이디어: {len(ideas)}건

### 공시 (최근 30일)
{chr(10).join(f'- {t}' for t in disc_titles) if disc_titles else '- 없음'}

### 텔레그램 인사이트
{chr(10).join(f'- {s}' for s in idea_summaries) if idea_summaries else '- 없음'}

### 감정분석
- 분석 건수: {sentiment.get('analysis_count', 0)}
- 평균 점수: {sentiment.get('avg_score', 0)} (-1~+1)

### 소속 테마
{', '.join(themes[:5]) if themes else '없음'}

{fin_section}

---

위 데이터를 종합하여 아래 JSON 형식으로 응답해주세요. 모든 텍스트는 한국어로 작성하세요.

**narrative_strength 판정 기준** (데이터 신뢰도, 투자방향 아님):
- "strong": 다음 5개 조건 중 3개 이상 충족
  1) 수급 동반 (외국인 or 기관 순매수 양수)
  2) 2개 이상 소스에서 언급 (유튜브+전문가+텔레그램 중)
  3) 최근 30일 내 공시 존재
  4) 감정분석 평균 > 0.3
  5) 재무 데이터 존재 + 흑자 + 매출 성장
- "weak": 다음 4개 조건 중 2개 이상 해당
  1) 수급 데이터 없거나 이탈(둘 다 음수)
  2) 언급 소스 1개 이하
  3) 재무 데이터 없음
  4) 감정분석 없음 (분석 건수 0)
- "moderate": 나머지

**market_outlook 판정 기준** (주가 방향성 전망):
- "bullish": 매출/이익 성장 + 수급 유입 + 감정분석 긍정이 정렬
- "bearish": 이익 감소 + 수급 이탈 + 감정분석 부정이 정렬
- "neutral": 혼재되거나 데이터 부족

{{
    "one_liner": "한 줄로 이 종목의 현재 상황 요약 (30자 이내)",
    "why_moving": "왜 움직이는가? 주가 변동의 핵심 원인을 2-3문장으로",
    "theme_context": "테마/섹터 맥락에서 이 종목의 위치를 2-3문장으로",
    "expert_perspective": "전문가/소셜 데이터에서 읽히는 시각을 2-3문장으로",
    "financial_highlight": "재무 상황을 1-2문장으로 요약 (성장성, 수익성, 건전성 핵심만). 재무 데이터 없으면 빈 문자열",
    "catalysts": ["향후 주가에 영향을 줄 카탈리스트 1", "카탈리스트 2"],
    "risk_factors": ["주요 리스크 1", "리스크 2"],
    "narrative_strength": "strong/moderate/weak 중 하나",
    "market_outlook": "bullish/neutral/bearish 중 하나"
}}"""

        result = await self._generate(prompt)
        return self._parse_json_response(result)

    async def classify_news_catalysts(self, news_items: list[dict]) -> list[dict]:
        """뉴스 기사들의 재료 유형과 중요도를 분류.

        Args:
            news_items: [{"title": ..., "description": ..., "stock_name": ...}, ...]

        Returns:
            [{"catalyst_type": ..., "importance": ...}, ...]
        """
        items_text = ""
        for i, item in enumerate(news_items):
            items_text += f"\n{i+1}. [{item.get('stock_name', '')}] {item.get('title', '')} - {item.get('description', '')[:100]}"

        prompt = f"""다음 한국 주식 뉴스 기사들의 재료 유형과 중요도를 분류해주세요.

뉴스 목록:{items_text}

각 뉴스에 대해 아래 기준으로 분류:

catalyst_type (하나만 선택):
- policy: 정책/규제 (정부 정책, 법안, 보조금)
- earnings: 실적 (실적 발표, 실적 서프라이즈)
- contract: 수주/계약 (대규모 수주, 공급 계약)
- theme: 테마/섹터 (AI, 2차전지 등 테마 관련)
- management: 경영 (M&A, 인수, 임원변동, 유상증자)
- product: 제품/기술 (신제품, 기술개발, FDA승인)
- other: 기타

importance (하나만 선택):
- high: 주가에 직접적 영향 가능 (대형 수주, 정책 변화, 실적 서프라이즈)
- medium: 관심을 가질만한 뉴스
- low: 일반적인 뉴스

JSON 배열로 응답해주세요. 뉴스 순서대로:
[
  {{"catalyst_type": "contract", "importance": "high"}},
  ...
]"""

        result = await self._generate(prompt)
        if not result:
            return []

        parsed = self._parse_json_response(result)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "items" in parsed:
            return parsed["items"]
        return []

    async def analyze_report_sentiment(self, text: str) -> Optional[dict]:
        """리포트 감정 분석."""
        prompt = f"""다음 한국 주식 관련 리포트를 분석해주세요.

리포트:
{text}

JSON 형식으로 응답해주세요:
{{
    "stocks": [
        {{
            "name": "종목명",
            "sentiment": "POSITIVE/NEGATIVE/NEUTRAL",
            "sentiment_score": 0.0~1.0,
            "confidence": 0.0~1.0,
            "summary": "한줄 요약",
            "key_points": ["핵심포인트1", "핵심포인트2"],
            "investment_signal": "BUY/SELL/HOLD/WATCH"
        }}
    ],
    "themes": ["관련테마1", "관련테마2"]
}}

종목이 언급되지 않았으면 stocks를 빈 배열로 응답하세요."""

        result = await self._generate(prompt)
        return self._parse_json_response(result)


def get_gemini_client() -> GeminiClient:
    """싱글톤 Gemini 클라이언트 반환."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
