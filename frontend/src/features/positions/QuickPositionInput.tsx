import { useState, useCallback, useEffect } from 'react'
import { Card } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import { positionBulkApi, ideaApi } from '../../services/api'
import type { ParseResult, BulkCreateResult } from '../../types/data'

interface IdeaStock {
  code: string
  name: string
  ticker_label: string
}

type InputMode = 'quick' | 'bulk' | 'brokerage' | 'file'

export default function QuickPositionInput() {
  const [mode, setMode] = useState<InputMode>('quick')
  const [inputText, setInputText] = useState('')
  const [parsedResult, setParsedResult] = useState<ParseResult | null>(null)
  const [createResult, setCreateResult] = useState<BulkCreateResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 아이디어 종목 자동완성
  const [ideaStocks, setIdeaStocks] = useState<IdeaStock[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [filteredStocks, setFilteredStocks] = useState<IdeaStock[]>([])

  // 아이디어 종목 목록 불러오기
  useEffect(() => {
    ideaApi.getIdeaStocks().then(setIdeaStocks).catch(console.error)
  }, [])

  // 입력 텍스트가 변경될 때 자동완성 필터링
  useEffect(() => {
    if (mode !== 'quick' || !inputText.trim()) {
      setShowSuggestions(false)
      return
    }

    const parts = inputText.trim().split(/\s+/)
    const firstWord = parts[0]?.toLowerCase() || ''

    // 첫 단어가 종목명이나 코드의 일부인지 확인
    if (firstWord.length >= 1 && parts.length <= 1) {
      const filtered = ideaStocks.filter(
        (s) =>
          s.name.toLowerCase().includes(firstWord) ||
          s.code.includes(firstWord)
      )
      setFilteredStocks(filtered)
      setShowSuggestions(filtered.length > 0)
    } else {
      setShowSuggestions(false)
    }
  }, [inputText, mode, ideaStocks])

  const handleParse = useCallback(async () => {
    if (!inputText.trim()) return

    setLoading(true)
    setError(null)
    setParsedResult(null)

    try {
      let result: ParseResult

      if (mode === 'quick') {
        const parsed = await positionBulkApi.parseQuick(inputText)
        result = {
          total: 1,
          valid: parsed.is_valid ? 1 : 0,
          invalid: parsed.is_valid ? 0 : 1,
          positions: [parsed],
        }
      } else if (mode === 'bulk') {
        result = await positionBulkApi.parseBulk(inputText)
      } else if (mode === 'brokerage') {
        result = await positionBulkApi.parseBrokerage(inputText)
      } else {
        return
      }

      setParsedResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : '파싱 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }, [inputText, mode])

  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setLoading(true)
    setError(null)
    setParsedResult(null)

    try {
      let result

      if (file.name.endsWith('.csv')) {
        result = await positionBulkApi.importCSV(file)
      } else if (file.name.endsWith('.json')) {
        result = await positionBulkApi.importJSON(file)
      } else if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
        result = await positionBulkApi.importExcel(file)
      } else {
        setError('지원하지 않는 파일 형식입니다. (CSV, JSON, Excel 지원)')
        return
      }

      setParsedResult({
        total: result.total,
        valid: result.success,
        invalid: result.failed,
        positions: result.positions,
      })

      if (result.errors.length > 0) {
        setError(result.errors.join('\n'))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '파일 처리 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleCreate = useCallback(async () => {
    if (!parsedResult || parsedResult.valid === 0) return

    setLoading(true)
    setError(null)

    try {
      const result = await positionBulkApi.createBulk(parsedResult.positions, true)
      setCreateResult(result)

      if (result.created > 0) {
        setInputText('')
        setParsedResult(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '포지션 생성 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }, [parsedResult])

  const handleSelectStock = (stock: IdeaStock) => {
    // 종목명으로 입력 텍스트 대체
    const parts = inputText.trim().split(/\s+/)
    parts[0] = stock.name
    setInputText(parts.join(' '))
    setShowSuggestions(false)
  }

  const getModeDescription = () => {
    switch (mode) {
      case 'quick':
        return '형식: "종목 수량 가격" (예: 삼성전자 100 70000, ㅅㅅㅈㅈ 100 70000)'
      case 'bulk':
        return '각 줄에 하나씩 입력하세요. 빈 줄과 #으로 시작하는 줄은 무시됩니다.'
      case 'brokerage':
        return '증권사 화면에서 복사한 텍스트를 붙여넣기 하세요. (탭 또는 | 구분 지원)'
      case 'file':
        return 'CSV, JSON, Excel 파일을 업로드하세요.'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">포지션 빠른 입력</h1>
      </div>

      {/* 입력 모드 선택 */}
      <div className="flex gap-2">
        {(['quick', 'bulk', 'brokerage', 'file'] as InputMode[]).map((m) => (
          <button
            key={m}
            onClick={() => {
              setMode(m)
              setParsedResult(null)
              setCreateResult(null)
              setError(null)
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === m
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {m === 'quick' && '빠른 입력'}
            {m === 'bulk' && '여러 줄 입력'}
            {m === 'brokerage' && '증권사 복사'}
            {m === 'file' && '파일 업로드'}
          </button>
        ))}
      </div>

      {/* 입력 영역 */}
      <Card className="p-4">
        <p className="text-sm text-gray-500 mb-3">{getModeDescription()}</p>

        {mode !== 'file' ? (
          <>
            <div className="relative">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onFocus={() => {
                  if (filteredStocks.length > 0 && mode === 'quick') {
                    setShowSuggestions(true)
                  }
                }}
                onBlur={() => {
                  // 약간의 딜레이로 클릭 이벤트 허용
                  setTimeout(() => setShowSuggestions(false), 150)
                }}
                placeholder={
                  mode === 'quick'
                    ? '삼성전자 100 70000'
                    : mode === 'bulk'
                    ? '삼성전자 100 70000\nSK하이닉스 50 120000\n...'
                    : '종목명  수량  매수가  현재가...'
                }
                className="w-full h-32 p-3 border rounded-lg font-mono text-sm resize-none"
              />
              {/* 자동완성 드롭다운 */}
              {showSuggestions && filteredStocks.length > 0 && (
                <div className="absolute z-10 left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  <div className="px-3 py-2 text-xs text-gray-500 bg-gray-50 border-b">
                    아이디어 등록 종목에서 선택
                  </div>
                  {filteredStocks.slice(0, 10).map((stock) => (
                    <button
                      key={stock.code}
                      type="button"
                      onClick={() => handleSelectStock(stock)}
                      className="w-full px-3 py-2 text-left hover:bg-blue-50 flex justify-between items-center text-sm"
                    >
                      <span className="font-medium">{stock.name}</span>
                      <span className="text-gray-400 text-xs">{stock.code}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {mode === 'quick' && ideaStocks.length > 0 && (
              <div className="mt-2 text-xs text-gray-500">
                💡 아이디어에 등록된 종목: {ideaStocks.map(s => s.name).join(', ')}
              </div>
            )}
            <div className="flex justify-end mt-3">
              <Button onClick={handleParse} disabled={loading || !inputText.trim()}>
                {loading ? '파싱 중...' : '파싱'}
              </Button>
            </div>
          </>
        ) : (
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <input
              type="file"
              accept=".csv,.json,.xlsx,.xls"
              onChange={handleFileUpload}
              className="hidden"
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer text-blue-500 hover:text-blue-600"
            >
              파일 선택
            </label>
            <p className="text-sm text-gray-500 mt-2">
              또는 파일을 여기에 드래그하세요
            </p>
          </div>
        )}
      </Card>

      {/* 에러 메시지 */}
      {error && (
        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-red-600 text-sm whitespace-pre-wrap">{error}</p>
        </Card>
      )}

      {/* 파싱 결과 */}
      {parsedResult && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">파싱 결과</h2>
            <div className="flex gap-2">
              <Badge variant="default">총 {parsedResult.total}건</Badge>
              <Badge variant="success">성공 {parsedResult.valid}건</Badge>
              {parsedResult.invalid > 0 && (
                <Badge variant="danger">실패 {parsedResult.invalid}건</Badge>
              )}
            </div>
          </div>

          <div className="space-y-2 max-h-60 overflow-y-auto">
            {parsedResult.positions.map((pos, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg text-sm ${
                  pos.is_valid ? 'bg-green-50' : 'bg-red-50'
                }`}
              >
                {pos.is_valid ? (
                  <div className="flex justify-between items-center">
                    <span className="font-medium">
                      {pos.stock_name} ({pos.stock_code})
                    </span>
                    <span className="text-gray-600">
                      {pos.quantity ? `${pos.quantity.toLocaleString()}주` : ''}
                      {pos.avg_price ? ` @ ${pos.avg_price.toLocaleString()}원` : ''}
                    </span>
                  </div>
                ) : (
                  <div>
                    <span className="text-red-600">{pos.error}</span>
                    <span className="text-gray-400 ml-2">({pos.raw_text})</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {parsedResult.valid > 0 && (
            <div className="flex justify-end mt-4">
              <Button onClick={handleCreate} disabled={loading}>
                {loading ? '생성 중...' : `${parsedResult.valid}건 포지션 생성`}
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* 생성 결과 */}
      {createResult && (
        <Card className="p-4 bg-green-50 border-green-200">
          <h2 className="font-semibold text-green-800 mb-2">포지션 생성 완료</h2>
          <p className="text-green-700">
            {createResult.created}건의 포지션이 생성되었습니다.
            {createResult.failed > 0 && ` (${createResult.failed}건 실패)`}
          </p>
          {createResult.errors.length > 0 && (
            <div className="mt-2 text-sm text-red-600">
              {createResult.errors.map((err, idx) => (
                <p key={idx}>{err}</p>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
