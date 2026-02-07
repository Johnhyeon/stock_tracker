import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import SentimentIndicator from '../../components/ui/SentimentIndicator'
import HashtagChips from '../../components/ui/HashtagChips'
import type { TelegramIdea } from '../../types/telegram_idea'

interface TelegramIdeaCardProps {
  idea: TelegramIdea
  onStockClick?: (stockCode: string) => void
  onAuthorClick?: (author: string) => void
  onHashtagClick?: (hashtag: string) => void
  compact?: boolean  // 컴팩트 모드 (그룹 뷰에서 사용)
  hideStock?: boolean  // 종목명 숨기기 (그룹 헤더에서 이미 표시)
}

// 메시지에서 해시태그 하이라이트
function highlightHashtags(text: string): React.ReactNode {
  const parts = text.split(/(#[가-힣A-Za-z0-9]+)/g)
  return parts.map((part, index) => {
    if (part.startsWith('#')) {
      return (
        <span key={index} className="text-primary-600 dark:text-primary-400 font-medium">
          {part}
        </span>
      )
    }
    return part
  })
}

// 날짜 포맷
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return `오늘 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
  } else if (diffDays === 1) {
    return '어제'
  } else if (diffDays < 7) {
    return `${diffDays}일 전`
  } else {
    return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
  }
}

export default function TelegramIdeaCard({
  idea,
  onStockClick,
  onAuthorClick,
  onHashtagClick,
  compact = false,
  hideStock = false,
}: TelegramIdeaCardProps) {
  const [expanded, setExpanded] = useState(false)

  // 메시지가 긴 경우 접기/펼치기 (컴팩트 모드에서는 더 짧게)
  const maxLength = compact ? 150 : 200
  const isLongMessage = idea.message_text.length > maxLength
  const displayText = expanded || !isLongMessage
    ? idea.message_text
    : idea.message_text.slice(0, maxLength) + '...'

  // 컴팩트 모드: 카드 없이 간단하게 표시
  if (compact) {
    return (
      <div className="p-3">
        {/* 상단: 발신자 및 날짜 */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {idea.is_forwarded && idea.forward_from_name && (
              <button
                onClick={() => onAuthorClick?.(idea.forward_from_name!)}
                className="text-xs text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
              >
                {idea.forward_from_name}
              </button>
            )}
            {!hideStock && idea.stock_name && (
              <button
                onClick={() => idea.stock_code && onStockClick?.(idea.stock_code)}
                className="text-xs font-medium text-primary-600 dark:text-primary-400 hover:underline"
              >
                {idea.stock_name}
              </button>
            )}
            {idea.sentiment && (
              <div className="flex items-center gap-1">
                <SentimentIndicator score={idea.sentiment_score} size="sm" />
              </div>
            )}
          </div>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {formatDate(idea.original_date)}
          </span>
        </div>

        {/* 메시지 내용 */}
        <div
          className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap"
          onClick={() => isLongMessage && setExpanded(!expanded)}
        >
          {highlightHashtags(displayText)}
          {isLongMessage && (
            <button
              className="text-primary-600 dark:text-primary-400 ml-1 hover:underline text-xs"
              onClick={(e) => {
                e.stopPropagation()
                setExpanded(!expanded)
              }}
            >
              {expanded ? '접기' : '더보기'}
            </button>
          )}
        </div>

        {/* 해시태그 */}
        {idea.raw_hashtags?.length > 0 && (
          <div className="mt-2">
            <HashtagChips
              hashtags={idea.raw_hashtags}
              maxVisible={3}
              size="sm"
              onHashtagClick={onHashtagClick}
            />
          </div>
        )}
      </div>
    )
  }

  // 기본 모드: 카드 형태
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        {/* 헤더: 종목 정보 + 소스 배지 + 날짜 */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            {!hideStock && (
              idea.stock_name ? (
                <button
                  onClick={() => idea.stock_code && onStockClick?.(idea.stock_code)}
                  className="font-semibold text-primary-600 dark:text-primary-400 hover:underline"
                >
                  {idea.stock_name}
                  {idea.stock_code && (
                    <span className="text-gray-500 dark:text-gray-400 text-sm ml-1">
                      ({idea.stock_code})
                    </span>
                  )}
                </button>
              ) : (
                <span className="text-gray-500 dark:text-gray-400 text-sm">종목 미지정</span>
              )
            )}
            {idea.stock_code && (
              <Link
                to={`/stocks/${idea.stock_code}`}
                className="text-xs text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400"
              >
                차트
              </Link>
            )}
            {/* 소스 타입 배지 */}
            {idea.source_type === 'my' && (
              <Badge variant="info" size="sm">내 아이디어</Badge>
            )}
            {idea.source_type === 'others' && (
              <Badge variant="default" size="sm">타인</Badge>
            )}
          </div>
          <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
            {formatDate(idea.original_date)}
          </span>
        </div>

        {/* 본문: 메시지 내용 */}
        <div
          className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap mb-3"
          onClick={() => isLongMessage && setExpanded(!expanded)}
        >
          {highlightHashtags(displayText)}
          {isLongMessage && (
            <button
              className="text-primary-600 dark:text-primary-400 ml-1 hover:underline"
              onClick={(e) => {
                e.stopPropagation()
                setExpanded(!expanded)
              }}
            >
              {expanded ? '접기' : '더보기'}
            </button>
          )}
        </div>

        {/* 해시태그 */}
        {idea.raw_hashtags?.length > 0 && (
          <div className="mb-3">
            <HashtagChips
              hashtags={idea.raw_hashtags}
              maxVisible={5}
              size="sm"
              onHashtagClick={onHashtagClick}
            />
          </div>
        )}

        {/* 푸터: 발신자 + 감정 분석 */}
        <div className="flex items-center justify-between flex-wrap gap-2 pt-3 border-t border-gray-100 dark:border-gray-700">
          <div className="flex items-center gap-2">
            {idea.is_forwarded && idea.forward_from_name && (
              <button
                onClick={() => onAuthorClick?.(idea.forward_from_name!)}
                className="text-xs text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
              >
                from: {idea.forward_from_name}
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {idea.sentiment && (
              <>
                <SentimentIndicator score={idea.sentiment_score} size="sm" />
                <Badge
                  variant={
                    idea.sentiment === 'POSITIVE' ? 'success' :
                    idea.sentiment === 'NEGATIVE' ? 'danger' : 'default'
                  }
                  size="sm"
                >
                  {idea.sentiment === 'POSITIVE' ? '긍정' :
                   idea.sentiment === 'NEGATIVE' ? '부정' : '중립'}
                </Badge>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
