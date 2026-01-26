"""DART 공시 필터링.

중요 공시를 분류하고 필터링하는 로직을 제공합니다.
"""
import re
from typing import Optional

from models.disclosure import DisclosureType, DisclosureImportance


# 중요 공시 키워드 (HIGH importance)
HIGH_IMPORTANCE_KEYWORDS = [
    # 실적 관련
    "실적", "매출", "영업이익", "순이익", "분기보고서", "사업보고서",
    "감사보고서", "영업실적", "분기실적", "잠정실적",
    # 대규모 계약/투자
    "대규모", "계약", "수주", "투자", "인수", "합병", "M&A",
    "공급계약", "납품계약",
    # 자본/주주 관련
    "유상증자", "무상증자", "자사주", "배당", "주식분할",
    "감자", "자본감소", "주식소각",
    # 임원/지배구조
    "대표이사", "임원", "사외이사", "최대주주", "지분",
    # 중요 이벤트
    "상장폐지", "관리종목", "투자주의", "거래정지",
    "횡령", "배임", "소송",
]

# 제외 키워드 (중요도 낮음)
LOW_IMPORTANCE_KEYWORDS = [
    "일괄신고", "증권신고서", "정정신고", "기재정정",
    "투자설명서", "예비심사", "소액",
    "주식매수선택권", "스톡옵션",
]

# 공시 유형별 분류
DISCLOSURE_TYPE_PATTERNS = {
    DisclosureType.REGULAR: [
        r"분기보고서",
        r"반기보고서",
        r"사업보고서",
    ],
    DisclosureType.FAIR: [
        r"공정공시",
    ],
    DisclosureType.MATERIAL: [
        r"주요사항보고",
        r"대규모",
        r"수주",
        r"계약",
        r"인수",
        r"합병",
        r"증자",
        r"감자",
    ],
    DisclosureType.EXTERNAL_AUDIT: [
        r"감사보고서",
        r"검토보고서",
        r"외부감사",
    ],
}


def classify_disclosure_type(report_nm: str) -> DisclosureType:
    """공시 유형 분류.

    Args:
        report_nm: 보고서명

    Returns:
        DisclosureType
    """
    report_nm_lower = report_nm.lower()

    for dtype, patterns in DISCLOSURE_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, report_nm_lower):
                return dtype

    return DisclosureType.OTHER


def classify_importance(report_nm: str, corp_cls: Optional[str] = None) -> DisclosureImportance:
    """공시 중요도 분류.

    Args:
        report_nm: 보고서명
        corp_cls: 법인구분 (Y:유가, K:코스닥)

    Returns:
        DisclosureImportance
    """
    # 제외 키워드 체크
    for keyword in LOW_IMPORTANCE_KEYWORDS:
        if keyword in report_nm:
            return DisclosureImportance.LOW

    # 중요 키워드 체크
    high_count = sum(1 for keyword in HIGH_IMPORTANCE_KEYWORDS if keyword in report_nm)

    if high_count >= 2:
        return DisclosureImportance.HIGH
    elif high_count == 1:
        # 유가증권(대형주)이면 중요도 상향
        if corp_cls == "Y":
            return DisclosureImportance.HIGH
        return DisclosureImportance.MEDIUM

    return DisclosureImportance.MEDIUM


def filter_important_disclosures(
    disclosures: list[dict],
    min_importance: DisclosureImportance = DisclosureImportance.MEDIUM,
    stock_codes: Optional[list[str]] = None,
) -> list[dict]:
    """중요 공시 필터링.

    Args:
        disclosures: DART API 공시 목록
        min_importance: 최소 중요도
        stock_codes: 관심 종목코드 목록 (있으면 해당 종목만)

    Returns:
        필터링된 공시 목록 (importance 필드 추가)
    """
    result = []
    importance_order = {
        DisclosureImportance.HIGH: 0,
        DisclosureImportance.MEDIUM: 1,
        DisclosureImportance.LOW: 2,
    }
    min_order = importance_order[min_importance]

    for disc in disclosures:
        # 종목 필터
        if stock_codes and disc.get("stock_code") not in stock_codes:
            continue

        # 중요도 분류
        importance = classify_importance(
            disc.get("report_nm", ""),
            disc.get("corp_cls")
        )

        # 중요도 필터
        if importance_order[importance] > min_order:
            continue

        # 유형 분류
        disc_type = classify_disclosure_type(disc.get("report_nm", ""))

        # 결과에 추가
        result.append({
            **disc,
            "disclosure_type": disc_type,
            "importance": importance,
        })

    # 중요도 순 정렬 (HIGH 먼저)
    result.sort(key=lambda x: (importance_order[x["importance"]], x.get("rcept_dt", "")))

    return result


def extract_summary(report_nm: str) -> Optional[str]:
    """보고서명에서 요약 추출.

    Args:
        report_nm: 보고서명

    Returns:
        요약 문자열 또는 None
    """
    # 괄호 안 내용 추출 시도
    match = re.search(r'\(([^)]+)\)', report_nm)
    if match:
        return match.group(1)

    # 첫 50자 반환
    if len(report_nm) > 50:
        return report_nm[:50] + "..."
    return report_nm
