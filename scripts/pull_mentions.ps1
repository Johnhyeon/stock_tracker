# 라즈베리파이에서 mentions.json을 가져와 서버에 동기화하는 PowerShell 스크립트
#
# 사용법:
#   .\pull_mentions.ps1
#
# Windows 작업 스케줄러 등록 시:
#   프로그램: powershell.exe
#   인수: -ExecutionPolicy Bypass -File "D:\project\stock_tracker\scripts\pull_mentions.ps1"

# === 설정 ===
$RASPI_HOST = "라파IP"           # VPN 접속 후 라파 IP
$RASPI_USER = "hyeon"            # SSH 유저
$REMOTE_FILE = "/home/hyeon/project/88_bot/mentions.json"
$LOCAL_FILE = "$env:TEMP\mentions.json"
$SERVER_URL = "http://localhost:8000/api/v1/traders/upload-mentions"

# === 1. SCP로 파일 가져오기 ===
Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INFO] 라파에서 mentions.json 가져오는 중..."

scp "${RASPI_USER}@${RASPI_HOST}:${REMOTE_FILE}" "$LOCAL_FILE"

if ($LASTEXITCODE -ne 0) {
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [ERROR] SCP 실패. VPN 연결 확인 필요."
    exit 1
}

# === 2. 서버에 업로드 ===
Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INFO] 서버에 업로드 중..."

try {
    $response = curl.exe -s -w "`n%{http_code}" -X POST $SERVER_URL -F "file=@${LOCAL_FILE}"
    $lines = $response -split "`n"
    $httpCode = $lines[-1]
    $body = ($lines[0..($lines.Length-2)]) -join "`n"

    if ($httpCode -eq "200") {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [OK] 동기화 완료: $body"
    } else {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [ERROR] HTTP ${httpCode}: $body"
    }
} finally {
    Remove-Item $LOCAL_FILE -ErrorAction SilentlyContinue
}
