#!/usr/bin/env python3
"""실제 API 서버에 대한 라이브 테스트.

사용법: python tests/test_api_live.py
(서버가 실행 중이어야 함)
"""
import requests
import sys
from typing import Optional

BASE_URL = "http://localhost:8000/api/v1"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def log_pass(name: str):
    print(f"  {Colors.GREEN}✓ PASS{Colors.END} {name}")


def log_fail(name: str, detail: str = ""):
    print(f"  {Colors.RED}✗ FAIL{Colors.END} {name}")
    if detail:
        print(f"    {Colors.YELLOW}→ {detail}{Colors.END}")


def log_section(name: str):
    print(f"\n{Colors.BLUE}[{name}]{Colors.END}")


def test_ideas_crud():
    """아이디어 CRUD 테스트."""
    log_section("아이디어 CRUD 테스트")
    results = {"passed": 0, "failed": 0}

    # 1. 생성
    try:
        response = requests.post(
            f"{BASE_URL}/ideas",
            json={
                "type": "research",
                "tickers": ["테스트종목"],
                "thesis": "테스트 투자 논리입니다.",
                "expected_timeframe_days": 30,
                "target_return_pct": 15,
                "sector": "테스트섹터",
            },
        )
        if response.status_code == 201:
            data = response.json()
            idea_id = data["id"]
            if (
                data["type"] == "research"
                and data["status"] == "watching"
                and data["tickers"] == ["테스트종목"]
            ):
                log_pass("아이디어 생성")
                results["passed"] += 1
            else:
                log_fail("아이디어 생성", "응답 데이터가 예상과 다름")
                results["failed"] += 1
                return results
        else:
            log_fail("아이디어 생성", f"Status: {response.status_code}")
            results["failed"] += 1
            return results
    except Exception as e:
        log_fail("아이디어 생성", str(e))
        results["failed"] += 1
        return results

    # 2. 조회
    try:
        response = requests.get(f"{BASE_URL}/ideas/{idea_id}")
        if response.status_code == 200 and response.json()["id"] == idea_id:
            log_pass("아이디어 조회")
            results["passed"] += 1
        else:
            log_fail("아이디어 조회", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("아이디어 조회", str(e))
        results["failed"] += 1

    # 3. 목록 조회
    try:
        response = requests.get(f"{BASE_URL}/ideas")
        if response.status_code == 200 and isinstance(response.json(), list):
            log_pass("아이디어 목록 조회")
            results["passed"] += 1
        else:
            log_fail("아이디어 목록 조회", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("아이디어 목록 조회", str(e))
        results["failed"] += 1

    # 4. 수정
    try:
        response = requests.patch(
            f"{BASE_URL}/ideas/{idea_id}",
            json={
                "thesis": "수정된 논리",
                "status": "active",
                "fundamental_health": "deteriorating",
            },
        )
        if response.status_code == 200:
            data = response.json()
            if (
                data["thesis"] == "수정된 논리"
                and data["status"] == "active"
                and data["fundamental_health"] == "deteriorating"
            ):
                log_pass("아이디어 수정")
                results["passed"] += 1
            else:
                log_fail("아이디어 수정", "응답 데이터가 예상과 다름")
                results["failed"] += 1
        else:
            log_fail("아이디어 수정", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("아이디어 수정", str(e))
        results["failed"] += 1

    # 5. 삭제
    try:
        response = requests.delete(f"{BASE_URL}/ideas/{idea_id}")
        if response.status_code == 204:
            log_pass("아이디어 삭제")
            results["passed"] += 1
        else:
            log_fail("아이디어 삭제", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("아이디어 삭제", str(e))
        results["failed"] += 1

    return results


def test_dashboard():
    """대시보드 API 테스트."""
    log_section("대시보드 API 테스트")
    results = {"passed": 0, "failed": 0}

    # 1. 대시보드 기본 구조 테스트
    try:
        response = requests.get(f"{BASE_URL}/dashboard")
        if response.status_code == 200:
            data = response.json()
            required_fields = ["stats", "research_ideas", "chart_ideas", "watching_ideas"]
            stats_fields = ["total_ideas", "active_ideas", "watching_ideas", "research_ideas", "chart_ideas"]

            if all(field in data for field in required_fields):
                log_pass("대시보드 기본 구조")
                results["passed"] += 1
            else:
                missing = [f for f in required_fields if f not in data]
                log_fail("대시보드 기본 구조", f"누락된 필드: {missing}")
                results["failed"] += 1

            if all(field in data["stats"] for field in stats_fields):
                log_pass("대시보드 통계 구조")
                results["passed"] += 1
            else:
                missing = [f for f in stats_fields if f not in data["stats"]]
                log_fail("대시보드 통계 구조", f"누락된 필드: {missing}")
                results["failed"] += 1
        else:
            log_fail("대시보드 기본 구조", f"Status: {response.status_code}")
            results["failed"] += 2
    except Exception as e:
        log_fail("대시보드 기본 구조", str(e))
        results["failed"] += 2

    # 2. WATCHING 아이디어 생성 및 대시보드 확인
    try:
        # watching 아이디어 생성
        create_response = requests.post(
            f"{BASE_URL}/ideas",
            json={
                "type": "research",
                "tickers": ["대시보드테스트"],
                "thesis": "watching 테스트",
                "expected_timeframe_days": 30,
                "target_return_pct": 10,
            },
        )
        idea_id = create_response.json()["id"]

        # 대시보드 확인
        response = requests.get(f"{BASE_URL}/dashboard")
        data = response.json()

        if data["stats"]["watching_ideas"] >= 1:
            log_pass("대시보드 watching_ideas 카운트")
            results["passed"] += 1
        else:
            log_fail("대시보드 watching_ideas 카운트", f"값: {data['stats']['watching_ideas']}")
            results["failed"] += 1

        # watching_ideas 배열에 포함 확인
        watching_tickers = [idea.get("tickers", []) for idea in data["watching_ideas"]]
        if any("대시보드테스트" in t for t in watching_tickers):
            log_pass("대시보드 watching_ideas 목록에 표시")
            results["passed"] += 1
        else:
            log_fail("대시보드 watching_ideas 목록에 표시", "아이디어가 목록에 없음")
            results["failed"] += 1

        # 정리
        requests.delete(f"{BASE_URL}/ideas/{idea_id}")

    except Exception as e:
        log_fail("대시보드 WATCHING 테스트", str(e))
        results["failed"] += 2

    return results


def test_disclosures():
    """공시 API 테스트."""
    log_section("공시 API 테스트")
    results = {"passed": 0, "failed": 0}

    # 1. 공시 목록 조회
    try:
        response = requests.get(f"{BASE_URL}/disclosures")
        if response.status_code == 200:
            data = response.json()
            if "items" in data and "total" in data:
                log_pass("공시 목록 조회")
                results["passed"] += 1
            else:
                log_fail("공시 목록 조회", "응답 구조가 올바르지 않음")
                results["failed"] += 1
        else:
            log_fail("공시 목록 조회", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("공시 목록 조회", str(e))
        results["failed"] += 1

    # 2. my_ideas_only 파라미터 테스트
    try:
        response = requests.get(f"{BASE_URL}/disclosures?my_ideas_only=true")
        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                log_pass("공시 my_ideas_only 필터")
                results["passed"] += 1
            else:
                log_fail("공시 my_ideas_only 필터", "응답 구조가 올바르지 않음")
                results["failed"] += 1
        else:
            log_fail("공시 my_ideas_only 필터", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("공시 my_ideas_only 필터", str(e))
        results["failed"] += 1

    # 3. 공시 통계 조회
    try:
        response = requests.get(f"{BASE_URL}/disclosures/stats")
        if response.status_code == 200:
            data = response.json()
            if "total" in data and "unread" in data:
                log_pass("공시 통계 조회")
                results["passed"] += 1
            else:
                log_fail("공시 통계 조회", "응답 구조가 올바르지 않음")
                results["failed"] += 1
        else:
            log_fail("공시 통계 조회", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("공시 통계 조회", str(e))
        results["failed"] += 1

    return results


def test_alerts():
    """알림 API 테스트."""
    log_section("알림 API 테스트")
    results = {"passed": 0, "failed": 0}

    # 1. 알림 설정 조회
    try:
        response = requests.get(f"{BASE_URL}/alerts/settings")
        if response.status_code == 200:
            log_pass("알림 설정 조회")
            results["passed"] += 1
        else:
            log_fail("알림 설정 조회", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("알림 설정 조회", str(e))
        results["failed"] += 1

    # 2. 알림 규칙 목록 조회
    try:
        response = requests.get(f"{BASE_URL}/alerts/rules")
        if response.status_code == 200 and isinstance(response.json(), list):
            log_pass("알림 규칙 목록 조회")
            results["passed"] += 1
        else:
            log_fail("알림 규칙 목록 조회", f"Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        log_fail("알림 규칙 목록 조회", str(e))
        results["failed"] += 1

    return results


def main():
    print("=" * 60)
    print("  API 라이브 테스트")
    print("=" * 60)

    # 서버 연결 확인
    try:
        response = requests.get(f"{BASE_URL}/dashboard", timeout=5)
        if response.status_code != 200:
            print(f"\n{Colors.RED}서버가 응답하지 않습니다. 서버가 실행 중인지 확인하세요.{Colors.END}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n{Colors.RED}서버에 연결할 수 없습니다.{Colors.END}")
        print(f"  → 서버 실행: cd backend && uvicorn main:app --reload")
        sys.exit(1)

    total_passed = 0
    total_failed = 0

    # 테스트 실행
    for test_func in [test_ideas_crud, test_dashboard, test_disclosures, test_alerts]:
        results = test_func()
        total_passed += results["passed"]
        total_failed += results["failed"]

    # 결과 요약
    print("\n" + "=" * 60)
    print(f"  결과: {Colors.GREEN}{total_passed} passed{Colors.END}, ", end="")
    if total_failed > 0:
        print(f"{Colors.RED}{total_failed} failed{Colors.END}")
    else:
        print(f"{total_failed} failed")
    print("=" * 60)

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
