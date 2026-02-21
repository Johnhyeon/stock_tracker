#!/bin/bash
# 라즈베리파이에서 mentions.json 변경 감지 → GitHub Gist 업로드
#
# 필수 패키지:
#   sudo apt install inotify-tools jq
#
# 초기 설정:
#   1. GitHub에서 Personal Access Token 발급 (scope: gist)
#      https://github.com/settings/tokens → Generate new token → gist 체크
#   2. Private Gist 생성:
#      curl -s -H "Authorization: token YOUR_TOKEN" \
#        -d '{"description":"mentions","public":false,"files":{"mentions.json":{"content":"{}"}}}' \
#        https://api.github.com/gists
#      → 응답에서 "id" 값을 GIST_ID에 넣기
#   3. 아래 설정 수정
#
# 사용법:
#   ./push_mentions.sh          # 포그라운드 (테스트)
#   nohup ./push_mentions.sh &  # 백그라운드
#
# systemd 서비스 등록 (권장):
#   sudo cp push_mentions.service /etc/systemd/system/
#   sudo systemctl enable --now push_mentions

# === 설정 ===
MENTIONS_FILE="/home/hyeon/project/88_bot/mentions.json"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GIST_ID="99eafc977e832087a1268589ceef272e"
COOLDOWN=5

# === 업로드 함수 ===
upload() {
    if [ ! -f "$MENTIONS_FILE" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] 파일 없음: $MENTIONS_FILE"
        return 1
    fi

    # JSON 이스케이프 (jq로 문자열화)
    CONTENT=$(jq -Rs '.' < "$MENTIONS_FILE")

    RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        -d "{\"files\":{\"mentions.json\":{\"content\":${CONTENT}}}}" \
        "https://api.github.com/gists/${GIST_ID}")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" = "200" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [OK] Gist 업로드 완료"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] HTTP $HTTP_CODE"
        echo "$RESPONSE" | head -n -1 | tail -5
    fi
}

# === 시작 시 1회 업로드 ===
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] 초기 업로드..."
upload

# === 파일 변경 감지 루프 ===
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $MENTIONS_FILE 감시 시작..."

inotifywait -m -e close_write,moved_to "$(dirname "$MENTIONS_FILE")" --format '%f' |
while read FILENAME; do
    if [ "$FILENAME" = "$(basename "$MENTIONS_FILE")" ]; then
        sleep "$COOLDOWN"
        echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] 변경 감지, Gist 업로드 중..."
        upload
    fi
done
