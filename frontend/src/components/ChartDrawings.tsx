import { useEffect, useRef, useState, useCallback } from 'react'
import type { IChartApi, ISeriesApi } from 'lightweight-charts'
import { useDarkMode } from '../hooks/useDarkMode'

// 드로잉 타입
export type DrawingType = 'trendline' | 'horizontal' | 'channel' | 'fibonacci' | null

// 드로잉 데이터
export interface DrawingPoint {
  time: number  // UTC timestamp
  price: number
}

export interface TrendlineDrawing {
  type: 'trendline'
  id: string
  points: [DrawingPoint, DrawingPoint]
}

export interface HorizontalDrawing {
  type: 'horizontal'
  id: string
  price: number
  time: number  // 기준 시간 (차트 범위 내 표시용)
}

export interface ChannelDrawing {
  type: 'channel'
  id: string
  points: [DrawingPoint, DrawingPoint]  // 기준선 2점
  offset: number  // 가격 오프셋
}

export interface FibonacciDrawing {
  type: 'fibonacci'
  id: string
  points: [DrawingPoint, DrawingPoint]
}

export type Drawing = TrendlineDrawing | HorizontalDrawing | ChannelDrawing | FibonacciDrawing

// 피보나치 레벨
const FIBO_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]

// 드로잉 색상 (다크모드 대응)
const DRAWING_COLORS = {
  light: { line: '#000000', handle: '#3b82f6', fiboBg: 'rgba(59,130,246,0.08)' },
  dark: { line: '#e5e7eb', handle: '#60a5fa', fiboBg: 'rgba(96,165,250,0.12)' },
} as const

// localStorage 키
const getStorageKey = (stockCode: string) => `chart-drawings-${stockCode}`

// 드로잉 저장/불러오기
export function loadDrawings(stockCode: string): Drawing[] {
  try {
    const data = localStorage.getItem(getStorageKey(stockCode))
    return data ? JSON.parse(data) : []
  } catch {
    return []
  }
}

export function saveDrawings(stockCode: string, drawings: Drawing[]) {
  try {
    localStorage.setItem(getStorageKey(stockCode), JSON.stringify(drawings))
  } catch {
    console.error('Failed to save drawings')
  }
}

// 고유 ID 생성
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

// 드래그 상태 타입
interface DragState {
  drawingId: string
  pointIndex: number  // 0 또는 1 (수평선은 0만)
}

interface ChartDrawingsProps {
  stockCode: string
  chart: IChartApi
  series: ISeriesApi<'Candlestick'>
  containerRef: React.RefObject<HTMLDivElement>
  height: number
  enabled?: boolean
}

export default function ChartDrawings({
  stockCode,
  chart,
  series,
  containerRef,
  height,
  enabled = true,
}: ChartDrawingsProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [drawings, setDrawings] = useState<Drawing[]>([])
  const [activeTool, setActiveTool] = useState<DrawingType>(null)
  const [tempPoints, setTempPoints] = useState<DrawingPoint[]>([])
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null)
  const [selectedDrawing, setSelectedDrawing] = useState<string | null>(null)
  const [channelOffsetPrice, setChannelOffsetPrice] = useState<number>(0)
  const [magnetEnabled, setMagnetEnabled] = useState(true)
  const [renderKey, setRenderKey] = useState(0)
  const [dragState, setDragState] = useState<DragState | null>(null)
  const { isDark } = useDarkMode()

  const palette = isDark ? DRAWING_COLORS.dark : DRAWING_COLORS.light
  const drawingColor = palette.line
  const handleColor = palette.handle

  // 드로잉 불러오기
  useEffect(() => {
    if (stockCode) {
      setDrawings(loadDrawings(stockCode))
    }
  }, [stockCode])

  // 드로잉 저장 (변경 시 자동 저장)
  useEffect(() => {
    if (stockCode && drawings.length >= 0) {
      saveDrawings(stockCode, drawings)
    }
  }, [stockCode, drawings])

  // 단축키 처리
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl 키와 함께 눌렀을 때만 처리
      if (!e.ctrlKey) return

      // 입력 필드에서는 무시
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      switch (e.key.toLowerCase()) {
        case 'h': // Ctrl+H: 수평선
          e.preventDefault()
          setActiveTool(prev => prev === 'horizontal' ? null : 'horizontal')
          setTempPoints([])
          break
        case 't': // Ctrl+T: 추세선
          e.preventDefault()
          setActiveTool(prev => prev === 'trendline' ? null : 'trendline')
          setTempPoints([])
          break
        case 'p': // Ctrl+P: 채널
          e.preventDefault()
          setActiveTool(prev => prev === 'channel' ? null : 'channel')
          setTempPoints([])
          break
        case 'f': // Ctrl+F: 피보나치
          e.preventDefault()
          setActiveTool(prev => prev === 'fibonacci' ? null : 'fibonacci')
          setTempPoints([])
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled])

  // 좌표 변환: 시간/가격 → 픽셀 (매번 새로 계산)
  const toPixel = (point: DrawingPoint): { x: number; y: number } | null => {
    if (!chart || !series) return null
    const timeScale = chart.timeScale()
    const x = timeScale.timeToCoordinate(point.time as never)
    const y = series.priceToCoordinate(point.price)
    if (x === null || y === null) return null
    return { x, y }
  }

  // 가장 가까운 캔들 찾기
  const findClosestCandle = useCallback((x: number) => {
    if (!chart || !series) return null
    const timeScale = chart.timeScale()
    const time = timeScale.coordinateToTime(x)
    if (time === null) return null

    const data = series.data()
    let closestCandle = null
    let minDiff = Infinity
    for (const candle of data) {
      const candleTime = candle.time as number
      const diff = Math.abs(candleTime - (time as number))
      if (diff < minDiff) {
        minDiff = diff
        closestCandle = candle
      }
    }
    return closestCandle
  }, [chart, series])

  // 좌표 변환: 픽셀 → 시간/가격
  // X축: 항상 가장 가까운 캔들의 정확한 시간 사용 (오차 방지)
  // Y축: 마그넷 ON이면 고가에 스냅, OFF면 실제 좌표
  const fromPixel = useCallback((x: number, y: number): DrawingPoint | null => {
    if (!chart || !series) return null

    // 항상 가장 가까운 캔들 찾기 (X축 오차 방지)
    const closestCandle = findClosestCandle(x)
    if (!closestCandle) return null

    const candleTime = closestCandle.time as number

    // Y축: 마그넷 여부에 따라 결정
    if (magnetEnabled && 'high' in closestCandle) {
      return {
        time: candleTime,
        price: closestCandle.high as number
      }
    }

    const price = series.coordinateToPrice(y)
    if (price === null) return null
    return { time: candleTime, price }
  }, [chart, series, magnetEnabled, findClosestCandle])

  // 가격만 변환 (수평선용)
  // X축: 항상 가장 가까운 캔들의 정확한 시간 사용
  // Y축: 마그넷 ON이면 고가에 스냅
  const priceFromPixel = useCallback((x: number, y: number): { price: number; time: number } | null => {
    if (!series || !chart) return null

    // 항상 가장 가까운 캔들 찾기
    const closestCandle = findClosestCandle(x)
    if (!closestCandle) return null

    const candleTime = closestCandle.time as number

    if (magnetEnabled && 'high' in closestCandle) {
      return {
        price: closestCandle.high as number,
        time: candleTime
      }
    }

    const price = series.coordinateToPrice(y)
    if (price === null) return null
    return { price, time: candleTime }
  }, [series, chart, magnetEnabled, findClosestCandle])

  // 드래그 시작
  const handleDragStart = useCallback((drawingId: string, pointIndex: number, e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    setDragState({ drawingId, pointIndex })
    setSelectedDrawing(drawingId)
  }, [])

  // 드래그 중 드로잉 업데이트
  const updateDrawingPoint = useCallback((x: number, y: number) => {
    if (!dragState) return

    const newPoint = fromPixel(x, y)
    if (!newPoint) return

    setDrawings(prev => prev.map(drawing => {
      if (drawing.id !== dragState.drawingId) return drawing

      if (drawing.type === 'horizontal') {
        const result = priceFromPixel(x, y)
        if (!result) return drawing
        return { ...drawing, price: result.price, time: result.time }
      }

      if (drawing.type === 'trendline') {
        const newPoints = [...drawing.points] as [DrawingPoint, DrawingPoint]
        newPoints[dragState.pointIndex] = newPoint
        return { ...drawing, points: newPoints }
      }

      if (drawing.type === 'channel') {
        const newPoints = [...drawing.points] as [DrawingPoint, DrawingPoint]
        newPoints[dragState.pointIndex] = newPoint
        return { ...drawing, points: newPoints }
      }

      if (drawing.type === 'fibonacci') {
        const newPoints = [...drawing.points] as [DrawingPoint, DrawingPoint]
        newPoints[dragState.pointIndex] = newPoint
        return { ...drawing, points: newPoints }
      }

      return drawing
    }))
  }, [dragState, fromPixel, priceFromPixel])

  // 마우스 이동 핸들러
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    setMousePos({ x, y })

    // 드래그 중이면 드로잉 업데이트
    if (dragState) {
      updateDrawingPoint(x, y)
      return
    }

    // 도구 활성화 상태가 아니면 리턴
    if (!activeTool) return

    // 채널: 2점 후 오프셋 계산 (가격 단위로)
    if (activeTool === 'channel' && tempPoints.length === 2) {
      const currentPrice = series.coordinateToPrice(y)
      if (currentPrice !== null) {
        const p1 = tempPoints[0]
        const p2 = tempPoints[1]
        const p1Pixel = toPixel(p1)
        const p2Pixel = toPixel(p2)
        if (p1Pixel && p2Pixel) {
          const t = (x - p1Pixel.x) / (p2Pixel.x - p1Pixel.x || 1)
          const basePrice = p1.price + t * (p2.price - p1.price)
          setChannelOffsetPrice(currentPrice - basePrice)
        }
      }
    }
  }, [containerRef, activeTool, tempPoints, series, dragState, updateDrawingPoint])

  // 드래그 종료
  const handleMouseUp = useCallback(() => {
    if (dragState) {
      setDragState(null)
    }
  }, [dragState])

  // 마우스가 SVG를 벗어나면 드래그 종료
  const handleMouseLeave = useCallback(() => {
    if (dragState) {
      setDragState(null)
    }
  }, [dragState])

  // 클릭 핸들러
  const handleClick = useCallback((e: React.MouseEvent) => {
    // 드래그 중이면 클릭 무시
    if (dragState) return
    if (!activeTool || !containerRef.current) return

    const rect = containerRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // 수평선: 1점 (마그넷 적용)
    if (activeTool === 'horizontal') {
      const result = priceFromPixel(x, y)
      if (result !== null) {
        const newDrawing: HorizontalDrawing = {
          type: 'horizontal',
          id: generateId(),
          price: result.price,
          time: result.time,
        }
        setDrawings(prev => [...prev, newDrawing])
        setActiveTool(null)
      }
      return
    }

    // 채널: 2점 후 오프셋 확정
    if (activeTool === 'channel' && tempPoints.length === 2) {
      const newDrawing: ChannelDrawing = {
        type: 'channel',
        id: generateId(),
        points: [tempPoints[0], tempPoints[1]],
        offset: channelOffsetPrice,
      }
      setDrawings(prev => [...prev, newDrawing])
      setTempPoints([])
      setChannelOffsetPrice(0)
      setActiveTool(null)
      return
    }

    // 마그넷으로 점 가져오기
    const point = fromPixel(x, y)
    if (!point) return

    const newPoints = [...tempPoints, point]

    // 필요한 점 수에 따라 드로잉 완성
    if (activeTool === 'trendline' && newPoints.length >= 2) {
      const newDrawing: TrendlineDrawing = {
        type: 'trendline',
        id: generateId(),
        points: [newPoints[0], newPoints[1]],
      }
      setDrawings(prev => [...prev, newDrawing])
      setTempPoints([])
      setActiveTool(null)
    } else if (activeTool === 'fibonacci' && newPoints.length >= 2) {
      const newDrawing: FibonacciDrawing = {
        type: 'fibonacci',
        id: generateId(),
        points: [newPoints[0], newPoints[1]],
      }
      setDrawings(prev => [...prev, newDrawing])
      setTempPoints([])
      setActiveTool(null)
    } else if (activeTool === 'channel' && newPoints.length === 2) {
      setTempPoints(newPoints)
    } else {
      setTempPoints(newPoints)
    }
  }, [activeTool, tempPoints, fromPixel, priceFromPixel, channelOffsetPrice, containerRef, dragState])

  // 드로잉 삭제
  const handleDelete = useCallback((id: string, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation()
    }
    setDrawings(prev => prev.filter(d => d.id !== id))
    setSelectedDrawing(null)
  }, [])

  // 전체 삭제
  const handleClearAll = useCallback(() => {
    if (confirm('모든 작도를 삭제하시겠습니까?')) {
      setDrawings([])
      setSelectedDrawing(null)
    }
  }, [])

  // 드로잉 취소
  const handleCancel = useCallback(() => {
    setActiveTool(null)
    setTempPoints([])
    setMousePos(null)
    setChannelOffsetPrice(0)
    setDragState(null)
  }, [])

  // ESC 키로 취소
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCancel()
      } else if (e.key === 'Delete' && selectedDrawing) {
        handleDelete(selectedDrawing)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleCancel, handleDelete, selectedDrawing])

  // 차트 스크롤/줌 시 강제 리렌더링 (이벤트 기반 - rAF 폴링 대신)
  useEffect(() => {
    if (!chart) return

    const handleRangeChange = () => {
      setRenderKey(n => n + 1)
    }

    chart.timeScale().subscribeVisibleLogicalRangeChange(handleRangeChange)

    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleRangeChange)
    }
  }, [chart])

  // 선택 해제 (바깥 클릭)
  const handleSvgClick = useCallback(() => {
    // 드래그 중이면 무시
    if (dragState) return
    // 도구 활성화 상태면 handleClick이 처리
    if (activeTool) return
    // 선택 해제
    setSelectedDrawing(null)
  }, [dragState, activeTool])

  if (!enabled) return null

  const containerWidth = containerRef.current?.clientWidth || 800

  // 드래그 핸들 렌더링 (선택된 드로잉의 끝점)
  const renderHandle = (x: number, y: number, drawingId: string, pointIndex: number) => {
    const isBeingDragged = dragState?.drawingId === drawingId && dragState?.pointIndex === pointIndex
    return (
      <circle
        key={`handle-${drawingId}-${pointIndex}`}
        cx={x}
        cy={y}
        r={isBeingDragged ? 8 : 6}
        fill={handleColor}
        stroke={isDark ? '#1f2937' : '#fff'}
        strokeWidth={2}
        style={{ cursor: 'grab', pointerEvents: 'auto' }}
        onMouseDown={(e) => handleDragStart(drawingId, pointIndex, e)}
      />
    )
  }

  // 수평선 렌더링
  const renderHorizontal = (drawing: HorizontalDrawing) => {
    const y = series.priceToCoordinate(drawing.price)
    if (y === null) return null

    const isSelected = selectedDrawing === drawing.id
    return (
      <g key={`${drawing.id}-${renderKey}`}>
        <line
          x1={0} y1={y} x2={containerWidth} y2={y}
          stroke={drawingColor}
          strokeWidth={isSelected ? 2 : 1}
          strokeDasharray="5,5"
          style={{ pointerEvents: 'none' }}
        />
        <text
          x={containerWidth - 5}
          y={y - 5}
          fontSize="10"
          fill={drawingColor}
          textAnchor="end"
          style={{ pointerEvents: 'none' }}
        >
          {drawing.price.toLocaleString()}
        </text>
        {/* 선택 시 양쪽 끝에 핸들 표시 */}
        {isSelected && (
          <>
            {renderHandle(50, y, drawing.id, 0)}
            {renderHandle(containerWidth - 50, y, drawing.id, 0)}
          </>
        )}
      </g>
    )
  }

  // 트렌드라인 렌더링
  const renderTrendline = (drawing: TrendlineDrawing, isTemp = false) => {
    const p1 = toPixel(drawing.points[0])
    const p2 = toPixel(drawing.points[1])
    if (!p1 || !p2) return null

    const isSelected = selectedDrawing === drawing.id
    return (
      <g key={`${drawing.id}-${renderKey}`}>
        <line
          x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
          stroke={drawingColor}
          strokeWidth={isSelected ? 2 : 1}
          strokeDasharray={isTemp ? '5,5' : undefined}
          style={{ pointerEvents: 'none' }}
        />
        {!isTemp && !isSelected && (
          <>
            <circle cx={p1.x} cy={p1.y} r={4} fill={drawingColor} style={{ pointerEvents: 'none' }} />
            <circle cx={p2.x} cy={p2.y} r={4} fill={drawingColor} style={{ pointerEvents: 'none' }} />
          </>
        )}
        {/* 선택 시 드래그 핸들 표시 */}
        {isSelected && !isTemp && (
          <>
            {renderHandle(p1.x, p1.y, drawing.id, 0)}
            {renderHandle(p2.x, p2.y, drawing.id, 1)}
          </>
        )}
      </g>
    )
  }

  // 패러럴 채널 렌더링
  const renderChannel = (drawing: ChannelDrawing, isTemp = false, tempOffset?: number) => {
    const p1 = toPixel(drawing.points[0])
    const p2 = toPixel(drawing.points[1])
    if (!p1 || !p2) return null

    const offset = tempOffset !== undefined ? tempOffset : drawing.offset
    const p1Offset = toPixel({ time: drawing.points[0].time, price: drawing.points[0].price + offset })
    const p2Offset = toPixel({ time: drawing.points[1].time, price: drawing.points[1].price + offset })
    if (!p1Offset || !p2Offset) return null

    const isSelected = selectedDrawing === drawing.id
    const strokeWidth = isSelected ? 2 : 1

    return (
      <g key={`${drawing.id}-${renderKey}`}>
        <line
          x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
          stroke={drawingColor}
          strokeWidth={strokeWidth}
          strokeDasharray={isTemp ? '5,5' : undefined}
          style={{ pointerEvents: 'none' }}
        />
        <line
          x1={p1Offset.x} y1={p1Offset.y}
          x2={p2Offset.x} y2={p2Offset.y}
          stroke={drawingColor}
          strokeWidth={strokeWidth}
          strokeDasharray={isTemp ? '5,5' : undefined}
          style={{ pointerEvents: 'none' }}
        />
        <line
          x1={p1.x} y1={p1.y} x2={p1Offset.x} y2={p1Offset.y}
          stroke={drawingColor}
          strokeWidth={1}
          strokeDasharray="2,2"
          opacity={0.5}
          style={{ pointerEvents: 'none' }}
        />
        <line
          x1={p2.x} y1={p2.y} x2={p2Offset.x} y2={p2Offset.y}
          stroke={drawingColor}
          strokeWidth={1}
          strokeDasharray="2,2"
          opacity={0.5}
          style={{ pointerEvents: 'none' }}
        />
        {!isTemp && !isSelected && (
          <>
            <circle cx={p1.x} cy={p1.y} r={4} fill={drawingColor} style={{ pointerEvents: 'none' }} />
            <circle cx={p2.x} cy={p2.y} r={4} fill={drawingColor} style={{ pointerEvents: 'none' }} />
          </>
        )}
        {/* 선택 시 드래그 핸들 표시 */}
        {isSelected && !isTemp && (
          <>
            {renderHandle(p1.x, p1.y, drawing.id, 0)}
            {renderHandle(p2.x, p2.y, drawing.id, 1)}
          </>
        )}
      </g>
    )
  }

  // 피보나치 렌더링
  const renderFibonacci = (drawing: FibonacciDrawing, isTemp = false) => {
    const p1 = toPixel(drawing.points[0])
    const p2 = toPixel(drawing.points[1])
    if (!p1 || !p2) return null

    const minX = Math.min(p1.x, p2.x) - 20
    const maxX = Math.max(p1.x, p2.x) + 20
    const priceRange = drawing.points[1].price - drawing.points[0].price

    const isSelected = selectedDrawing === drawing.id
    return (
      <g key={`${drawing.id}-${renderKey}`}>
        {FIBO_LEVELS.map(level => {
          const price = drawing.points[0].price + priceRange * level
          const pixel = toPixel({ time: drawing.points[0].time, price })
          if (!pixel) return null

          return (
            <g key={level}>
              <line
                x1={minX} y1={pixel.y} x2={maxX + 50} y2={pixel.y}
                stroke={drawingColor}
                strokeWidth={level === 0 || level === 1 ? (isSelected ? 2 : 1.5) : 1}
                strokeDasharray={isTemp ? '5,5' : (level === 0.5 ? '5,5' : undefined)}
                opacity={isSelected ? 1 : 0.8}
                style={{ pointerEvents: 'none' }}
              />
              <text
                x={maxX + 55}
                y={pixel.y + 4}
                fontSize="10"
                fill={drawingColor}
                style={{ pointerEvents: 'none' }}
              >
                {(level * 100).toFixed(1)}%
              </text>
            </g>
          )
        })}
        <line
          x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
          stroke={drawingColor}
          strokeWidth={1}
          strokeDasharray="3,3"
          opacity={0.5}
          style={{ pointerEvents: 'none' }}
        />
        {!isTemp && !isSelected && (
          <>
            <circle cx={p1.x} cy={p1.y} r={4} fill={drawingColor} style={{ pointerEvents: 'none' }} />
            <circle cx={p2.x} cy={p2.y} r={4} fill={drawingColor} style={{ pointerEvents: 'none' }} />
          </>
        )}
        {/* 선택 시 드래그 핸들 표시 */}
        {isSelected && !isTemp && (
          <>
            {renderHandle(p1.x, p1.y, drawing.id, 0)}
            {renderHandle(p2.x, p2.y, drawing.id, 1)}
          </>
        )}
      </g>
    )
  }

  // 임시 드로잉 (작성 중)
  const renderTempDrawing = () => {
    if (!activeTool || !mousePos) return null

    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return null

    if (activeTool === 'horizontal') {
      const result = priceFromPixel(mousePos.x, mousePos.y)
      if (result === null) return null
      const y = magnetEnabled ? series.priceToCoordinate(result.price) : mousePos.y
      if (y === null) return null
      return (
        <g>
          <line
            x1={0} y1={y} x2={containerWidth} y2={y}
            stroke={drawingColor}
            strokeWidth={1}
            strokeDasharray="5,5"
            opacity={0.7}
          />
          <text x={containerWidth - 5} y={y - 5} fontSize="10" fill={drawingColor} textAnchor="end">
            {result.price.toLocaleString()}
          </text>
        </g>
      )
    }

    if (tempPoints.length === 0) {
      if (magnetEnabled) {
        const point = fromPixel(mousePos.x, mousePos.y)
        if (point) {
          const pixel = toPixel(point)
          if (pixel) {
            return <circle cx={pixel.x} cy={pixel.y} r={5} fill={drawingColor} opacity={0.5} />
          }
        }
      }
      return null
    }

    const currentPoint = fromPixel(mousePos.x, mousePos.y)
    if (!currentPoint) return null

    if (activeTool === 'channel' && tempPoints.length === 2) {
      return renderChannel(
        {
          type: 'channel',
          id: 'temp',
          points: [tempPoints[0], tempPoints[1]],
          offset: channelOffsetPrice,
        },
        true,
        channelOffsetPrice
      )
    }

    const allPoints = [...tempPoints, currentPoint]

    if (activeTool === 'trendline' && allPoints.length >= 2) {
      return renderTrendline({
        type: 'trendline',
        id: 'temp',
        points: [allPoints[0], allPoints[1]],
      }, true)
    }

    if (activeTool === 'channel' && allPoints.length >= 2) {
      return renderChannel({
        type: 'channel',
        id: 'temp',
        points: [allPoints[0], allPoints[1]],
        offset: 0,
      }, true)
    }

    if (activeTool === 'fibonacci' && allPoints.length >= 2) {
      return renderFibonacci({
        type: 'fibonacci',
        id: 'temp',
        points: [allPoints[0], allPoints[1]],
      }, true)
    }

    const p1 = toPixel(tempPoints[0])
    if (p1) {
      const currentPixel = toPixel(currentPoint)
      return (
        <g>
          <circle cx={p1.x} cy={p1.y} r={4} fill={drawingColor} />
          {currentPixel && (
            <line
              x1={p1.x} y1={p1.y} x2={currentPixel.x} y2={currentPixel.y}
              stroke={drawingColor}
              strokeWidth={1}
              strokeDasharray="5,5"
              opacity={0.5}
            />
          )}
        </g>
      )
    }

    return null
  }

  // 클릭 가능한 드로잉 오버레이 렌더링
  const renderClickableOverlay = () => {
    return drawings.map(drawing => {
      if (drawing.type === 'horizontal') {
        const y = series.priceToCoordinate(drawing.price)
        if (y === null) return null
        return (
          <line
            key={`click-${drawing.id}`}
            x1={0} y1={y} x2={containerWidth} y2={y}
            stroke="transparent"
            strokeWidth={12}
            style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
            onClick={(e) => { e.stopPropagation(); setSelectedDrawing(drawing.id) }}
          />
        )
      }
      if (drawing.type === 'trendline') {
        const p1 = toPixel(drawing.points[0])
        const p2 = toPixel(drawing.points[1])
        if (!p1 || !p2) return null
        return (
          <line
            key={`click-${drawing.id}`}
            x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
            stroke="transparent"
            strokeWidth={12}
            style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
            onClick={(e) => { e.stopPropagation(); setSelectedDrawing(drawing.id) }}
          />
        )
      }
      if (drawing.type === 'channel') {
        const p1 = toPixel(drawing.points[0])
        const p2 = toPixel(drawing.points[1])
        const p1Offset = toPixel({ time: drawing.points[0].time, price: drawing.points[0].price + drawing.offset })
        const p2Offset = toPixel({ time: drawing.points[1].time, price: drawing.points[1].price + drawing.offset })
        if (!p1 || !p2 || !p1Offset || !p2Offset) return null
        return (
          <g key={`click-${drawing.id}`}>
            <line
              x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
              stroke="transparent"
              strokeWidth={12}
              style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
              onClick={(e) => { e.stopPropagation(); setSelectedDrawing(drawing.id) }}
            />
            <line
              x1={p1Offset.x} y1={p1Offset.y}
              x2={p2Offset.x} y2={p2Offset.y}
              stroke="transparent"
              strokeWidth={12}
              style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
              onClick={(e) => { e.stopPropagation(); setSelectedDrawing(drawing.id) }}
            />
          </g>
        )
      }
      if (drawing.type === 'fibonacci') {
        const p1 = toPixel(drawing.points[0])
        const p2 = toPixel(drawing.points[1])
        if (!p1 || !p2) return null
        const minX = Math.min(p1.x, p2.x) - 20
        const maxX = Math.max(p1.x, p2.x) + 70
        const priceRange = drawing.points[1].price - drawing.points[0].price
        return (
          <g key={`click-${drawing.id}`}>
            {FIBO_LEVELS.map(level => {
              const price = drawing.points[0].price + priceRange * level
              const pixel = toPixel({ time: drawing.points[0].time, price })
              if (!pixel) return null
              return (
                <line
                  key={level}
                  x1={minX} y1={pixel.y} x2={maxX} y2={pixel.y}
                  stroke="transparent"
                  strokeWidth={12}
                  style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
                  onClick={(e) => { e.stopPropagation(); setSelectedDrawing(drawing.id) }}
                />
              )
            })}
          </g>
        )
      }
      return null
    })
  }

  return (
    <>
      {/* 도구 모음 */}
      <div className="absolute top-2 right-2 z-30 flex items-center gap-1 bg-white dark:bg-t-bg-card rounded-lg shadow-md p-1 border dark:border-t-border">
        <button
          onClick={() => setMagnetEnabled(!magnetEnabled)}
          className={`p-1.5 rounded text-xs font-medium transition-colors ${
            magnetEnabled
              ? 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-400'
              : 'text-gray-400 dark:text-t-text-muted hover:bg-gray-100 dark:hover:bg-t-border/50'
          }`}
          title={magnetEnabled ? '마그넷 ON (고가 스냅)' : '마그넷 OFF'}
        >
          🧲
        </button>
        <div className="w-px h-4 bg-gray-300 dark:bg-t-border-hover" />
        <button
          onClick={() => { setActiveTool(activeTool === 'trendline' ? null : 'trendline'); setTempPoints([]) }}
          className={`p-1.5 rounded text-xs font-medium transition-colors ${
            activeTool === 'trendline'
              ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800'
              : 'text-gray-600 dark:text-t-text-secondary hover:bg-gray-100 dark:hover:bg-t-border/50'
          }`}
          title="추세선 Ctrl+T (2점)"
        >
          📏
        </button>
        <button
          onClick={() => { setActiveTool(activeTool === 'horizontal' ? null : 'horizontal'); setTempPoints([]) }}
          className={`p-1.5 rounded text-xs font-medium transition-colors ${
            activeTool === 'horizontal'
              ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800'
              : 'text-gray-600 dark:text-t-text-secondary hover:bg-gray-100 dark:hover:bg-t-border/50'
          }`}
          title="수평선 Ctrl+H (1점)"
        >
          ─
        </button>
        <button
          onClick={() => { setActiveTool(activeTool === 'channel' ? null : 'channel'); setTempPoints([]); setChannelOffsetPrice(0) }}
          className={`p-1.5 rounded text-xs font-medium transition-colors ${
            activeTool === 'channel'
              ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800'
              : 'text-gray-600 dark:text-t-text-secondary hover:bg-gray-100 dark:hover:bg-t-border/50'
          }`}
          title="채널 Ctrl+P (2점 + 드래그)"
        >
          ▭
        </button>
        <button
          onClick={() => { setActiveTool(activeTool === 'fibonacci' ? null : 'fibonacci'); setTempPoints([]) }}
          className={`p-1.5 rounded text-xs font-medium transition-colors ${
            activeTool === 'fibonacci'
              ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800'
              : 'text-gray-600 dark:text-t-text-secondary hover:bg-gray-100 dark:hover:bg-t-border/50'
          }`}
          title="피보나치 Ctrl+F (2점)"
        >
          ⟂
        </button>
        {drawings.length > 0 && (
          <>
            <div className="w-px h-4 bg-gray-300 dark:bg-t-border-hover mx-1" />
            <button
              onClick={handleClearAll}
              className="p-1.5 rounded text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
              title="모두 삭제"
            >
              🗑️
            </button>
          </>
        )}
      </div>

      {/* 선택된 드로잉 삭제 버튼 */}
      {selectedDrawing && !dragState && (
        <div className="absolute top-12 right-2 z-30 bg-white dark:bg-t-bg-card rounded-lg shadow-md p-1 border dark:border-t-border">
          <button
            onClick={() => handleDelete(selectedDrawing)}
            className="px-2 py-1 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
          >
            선택 삭제 (Del)
          </button>
        </div>
      )}

      {/* 안내 메시지 */}
      {activeTool && (
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-30 bg-black/70 text-white text-xs px-3 py-1.5 rounded-full pointer-events-none">
          {activeTool === 'trendline' && `트렌드라인: ${tempPoints.length}/2점`}
          {activeTool === 'horizontal' && '수평선: 클릭하여 가격 지정'}
          {activeTool === 'channel' && (
            tempPoints.length < 2
              ? `채널: ${tempPoints.length}/2점 (기준선)`
              : '채널: 마우스로 너비 조절 후 클릭'
          )}
          {activeTool === 'fibonacci' && `피보나치: ${tempPoints.length}/2점`}
          {magnetEnabled && <span className="ml-1 text-yellow-400">🧲</span>}
          <span className="ml-2 opacity-70">(ESC 취소)</span>
        </div>
      )}

      {/* 드래그 중 안내 */}
      {dragState && (
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-30 bg-blue-600/90 text-white text-xs px-3 py-1.5 rounded-full pointer-events-none">
          드래그하여 위치 조절 중...
          {magnetEnabled && <span className="ml-1 text-yellow-400">🧲</span>}
        </div>
      )}

      {/* 메인 SVG - 드로잉 + 도구 + 드래그 */}
      <svg
        ref={svgRef}
        className="absolute inset-0 z-20"
        style={{
          width: '100%',
          height: height,
          pointerEvents: activeTool || dragState || selectedDrawing ? 'auto' : 'none',
          cursor: dragState ? 'grabbing' : (activeTool ? 'crosshair' : 'default'),
        }}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onClick={activeTool ? handleClick : handleSvgClick}
      >
        {/* 저장된 드로잉 */}
        {drawings.map(drawing => {
          if (drawing.type === 'horizontal') return renderHorizontal(drawing)
          if (drawing.type === 'trendline') return renderTrendline(drawing)
          if (drawing.type === 'channel') return renderChannel(drawing)
          if (drawing.type === 'fibonacci') return renderFibonacci(drawing)
          return null
        })}

        {/* 작성 중인 드로잉 */}
        {renderTempDrawing()}
      </svg>

      {/* 드로잉이 있을 때 클릭 가능한 오버레이 (선택되지 않은 상태에서만) */}
      {!activeTool && !dragState && !selectedDrawing && drawings.length > 0 && (
        <svg
          className="absolute inset-0 z-20"
          style={{
            width: '100%',
            height: height,
            pointerEvents: 'none',
          }}
        >
          {renderClickableOverlay()}
        </svg>
      )}
    </>
  )
}
