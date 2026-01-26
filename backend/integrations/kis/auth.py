"""KIS API 토큰 관리."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

# 토큰 저장 파일 경로
TOKEN_FILE = Path(__file__).parent.parent.parent / ".kis_token.json"


class KISTokenManager:
    """KIS API 접근 토큰 관리자.

    - 토큰 발급 및 자동 갱신
    - 토큰 만료 전 사전 갱신
    - 토큰을 파일에 저장하여 서버 재시작 후에도 재사용
    """

    def __init__(self):
        self.settings = get_settings()
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._lock = asyncio.Lock()
        # 저장된 토큰 로드
        self._load_token()

    @property
    def base_url(self) -> str:
        return self.settings.kis_base_url

    @property
    def is_token_valid(self) -> bool:
        """토큰이 유효한지 확인 (만료 5분 전이면 무효 처리)."""
        if not self._access_token or not self._token_expires_at:
            return False
        return datetime.now() < self._token_expires_at - timedelta(minutes=5)

    def _load_token(self) -> None:
        """파일에서 저장된 토큰 로드."""
        try:
            if TOKEN_FILE.exists():
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)

                self._access_token = data.get("access_token")
                expires_at_str = data.get("expires_at")

                if expires_at_str:
                    self._token_expires_at = datetime.fromisoformat(expires_at_str)

                if self.is_token_valid:
                    logger.info(
                        f"Loaded valid KIS token from file, expires at {self._token_expires_at}"
                    )
                else:
                    logger.info("Stored KIS token is expired, will request new one")
                    self._access_token = None
                    self._token_expires_at = None
        except Exception as e:
            logger.warning(f"Failed to load KIS token from file: {e}")
            self._access_token = None
            self._token_expires_at = None

    def _save_token(self) -> None:
        """토큰을 파일에 저장."""
        try:
            data = {
                "access_token": self._access_token,
                "expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None,
                "saved_at": datetime.now().isoformat(),
            }
            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"KIS token saved to {TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"Failed to save KIS token to file: {e}")

    async def get_access_token(self) -> str:
        """유효한 접근 토큰 반환. 필요시 새로 발급."""
        async with self._lock:
            if not self.is_token_valid:
                await self._issue_token()
            return self._access_token

    async def _issue_token(self) -> None:
        """새 접근 토큰 발급."""
        if not self.settings.kis_app_key or not self.settings.kis_app_secret:
            raise ValueError("KIS API credentials not configured")

        url = f"{self.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.settings.kis_app_key,
            "appsecret": self.settings.kis_app_secret,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                self._access_token = data["access_token"]
                # KIS 토큰은 24시간 유효 (86400초)
                expires_in = data.get("expires_in", 86400)
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                # 토큰을 파일에 저장
                self._save_token()

                logger.info(
                    f"KIS access token issued, expires at {self._token_expires_at}"
                )
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to issue KIS token: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error issuing KIS token: {e}")
                raise

    async def revoke_token(self) -> None:
        """토큰 폐기 (선택적)."""
        if not self._access_token:
            return

        url = f"{self.base_url}/oauth2/revokeP"
        payload = {
            "appkey": self.settings.kis_app_key,
            "appsecret": self.settings.kis_app_secret,
            "token": self._access_token,
        }

        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, json=payload, timeout=10.0)
                self._access_token = None
                self._token_expires_at = None
                # 저장된 토큰 파일 삭제
                if TOKEN_FILE.exists():
                    TOKEN_FILE.unlink()
                logger.info("KIS access token revoked")
            except Exception as e:
                logger.warning(f"Failed to revoke KIS token: {e}")

    def get_token_info(self) -> dict:
        """현재 토큰 정보 반환."""
        return {
            "has_token": self._access_token is not None,
            "is_valid": self.is_token_valid,
            "expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None,
            "remaining_hours": (
                round((self._token_expires_at - datetime.now()).total_seconds() / 3600, 1)
                if self._token_expires_at and self._token_expires_at > datetime.now()
                else 0
            ),
        }


# 싱글톤 인스턴스
_token_manager: Optional[KISTokenManager] = None


def get_token_manager() -> KISTokenManager:
    """토큰 관리자 싱글톤 반환."""
    global _token_manager
    if _token_manager is None:
        _token_manager = KISTokenManager()
    return _token_manager
