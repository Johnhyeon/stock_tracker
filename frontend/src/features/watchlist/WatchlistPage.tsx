import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { watchlistApi, stockApi } from '../../services/api'
import type { WatchlistGroup, WatchlistItemFull } from '../../services/api'
import { useWatchlist } from '../../hooks/useWatchlist'
import { useWatchlistStore } from '../../store/useWatchlistStore'

const GROUP_COLORS = [
  '#6366f1', '#ef4444', '#f59e0b', '#10b981', '#3b82f6',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#06b6d4',
]

export default function WatchlistPage() {
  const [groups, setGroups] = useState<WatchlistGroup[]>([])
  const [items, setItems] = useState<WatchlistItemFull[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())
  const [collapsedGroups, setCollapsedGroups] = useState<Set<number>>(new Set())
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupColor, setNewGroupColor] = useState('#6366f1')
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null)
  const [editingGroupName, setEditingGroupName] = useState('')
  const [showAddStock, setShowAddStock] = useState(false)
  const [addQuery, setAddQuery] = useState('')
  const [addResults, setAddResults] = useState<{ code: string; name: string; market: string }[]>([])
  const [addLoading, setAddLoading] = useState(false)
  const addDebounceRef = useRef<ReturnType<typeof setTimeout>>()
  const { toggleWatch } = useWatchlist()
  const refreshStoreGroups = useWatchlistStore(s => s.refreshGroups)

  const fetchData = useCallback(async () => {
    try {
      const data = await watchlistApi.getGrouped()
      setGroups(data.groups)
      setItems(data.items)
    } catch (err) {
      console.error('관심종목 로드 실패:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 그룹별 아이템 분류
  const groupedItems = useMemo(() => {
    const map = new Map<number | null, WatchlistItemFull[]>()
    map.set(null, []) // 미분류
    for (const g of groups) {
      map.set(g.id, [])
    }
    for (const item of items) {
      const key = item.group_id
      if (!map.has(key)) map.set(null, [...(map.get(null) || []), item])
      else map.get(key)!.push(item)
    }
    return map
  }, [groups, items])

  // 네비게이션용 전체 종목 리스트
  const stockNavList = useMemo(() =>
    items.map(i => ({ code: i.stock_code, name: i.stock_name || i.stock_code })),
    [items]
  )

  const toggleCollapse = (groupId: number) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

  const toggleSelect = (code: string) => {
    setSelectedCodes(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  const selectAll = (codes: string[]) => {
    setSelectedCodes(prev => {
      const next = new Set(prev)
      const allSelected = codes.every(c => next.has(c))
      if (allSelected) {
        codes.forEach(c => next.delete(c))
      } else {
        codes.forEach(c => next.add(c))
      }
      return next
    })
  }

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return
    try {
      await watchlistApi.createGroup(newGroupName.trim(), newGroupColor)
      setNewGroupName('')
      setShowCreateGroup(false)
      fetchData()
      refreshStoreGroups()
    } catch (err) {
      console.error('그룹 생성 실패:', err)
    }
  }

  const handleRenameGroup = async (groupId: number) => {
    if (!editingGroupName.trim()) return
    try {
      await watchlistApi.updateGroup(groupId, { name: editingGroupName.trim() })
      setEditingGroupId(null)
      fetchData()
      refreshStoreGroups()
    } catch (err) {
      console.error('그룹 이름 변경 실패:', err)
    }
  }

  const handleDeleteGroup = async (groupId: number, groupName: string) => {
    if (!confirm(`"${groupName}" 그룹을 삭제하시겠습니까?\n그룹 내 종목은 미분류로 이동됩니다.`)) return
    try {
      await watchlistApi.deleteGroup(groupId)
      fetchData()
      refreshStoreGroups()
    } catch (err) {
      console.error('그룹 삭제 실패:', err)
    }
  }

  const handleMoveToGroup = async (groupId: number | null) => {
    if (selectedCodes.size === 0) return
    try {
      await watchlistApi.moveToGroup(Array.from(selectedCodes), groupId)
      setSelectedCodes(new Set())
      fetchData()
    } catch (err) {
      console.error('이동 실패:', err)
    }
  }

  const handleRemoveItem = async (code: string) => {
    await toggleWatch(code)
    fetchData()
  }

  // 종목 검색
  const searchStocks = useCallback(async (q: string) => {
    if (!q || q.length < 1) { setAddResults([]); return }
    setAddLoading(true)
    try {
      const data = await stockApi.search(q, 10)
      setAddResults(data)
    } catch { setAddResults([]) }
    finally { setAddLoading(false) }
  }, [])

  const handleAddQueryChange = (value: string) => {
    setAddQuery(value)
    if (addDebounceRef.current) clearTimeout(addDebounceRef.current)
    addDebounceRef.current = setTimeout(() => searchStocks(value), 200)
  }

  const handleAddStock = async (code: string, name: string) => {
    // 이미 관심종목이면 무시
    if (items.some(i => i.stock_code === code)) return
    await toggleWatch(code, name)
    setAddQuery('')
    setAddResults([])
    fetchData()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
      </div>
    )
  }

  const renderItemRow = (item: WatchlistItemFull) => {
    const navIndex = stockNavList.findIndex(s => s.code === item.stock_code)
    return (
      <div
        key={item.stock_code}
        className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 transition-colors"
      >
        <input
          type="checkbox"
          checked={selectedCodes.has(item.stock_code)}
          onChange={() => toggleSelect(item.stock_code)}
          className="rounded border-gray-300 dark:border-t-border w-3.5 h-3.5 text-indigo-600 focus:ring-indigo-500"
        />
        <Link
          to={`/stocks/${item.stock_code}`}
          state={{ stockListContext: { source: '관심종목', stocks: stockNavList, currentIndex: navIndex >= 0 ? navIndex : 0 } }}
          className="flex-1 min-w-0 flex items-center gap-2"
        >
          <span className="font-medium text-gray-900 dark:text-t-text-primary truncate">
            {item.stock_name || item.stock_code}
          </span>
          <span className="text-xs text-gray-400 dark:text-t-text-muted">{item.stock_code}</span>
        </Link>
        <span className="text-xs text-gray-400 dark:text-t-text-muted hidden sm:inline">
          {new Date(item.created_at).toLocaleDateString()}
        </span>
        <button
          onClick={() => handleRemoveItem(item.stock_code)}
          className="text-gray-400 hover:text-red-500 transition-colors p-1"
          title="관심종목 해제"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    )
  }

  const renderGroupSection = (group: WatchlistGroup | null, groupItems: WatchlistItemFull[]) => {
    const isUngrouped = group === null
    const groupId = group?.id ?? -1
    const isCollapsed = !isUngrouped && collapsedGroups.has(groupId)
    const groupCodes = groupItems.map(i => i.stock_code)

    return (
      <div
        key={isUngrouped ? 'ungrouped' : group!.id}
        className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border overflow-hidden"
      >
        {/* 그룹 헤더 */}
        <div className="flex items-center gap-2 px-3 py-2.5 bg-gray-50 dark:bg-t-bg border-b border-gray-200 dark:border-t-border">
          {!isUngrouped && (
            <div className="w-1 h-6 rounded-full flex-shrink-0" style={{ backgroundColor: group!.color || '#6366f1' }} />
          )}
          {!isUngrouped && (
            <button
              onClick={() => toggleCollapse(groupId)}
              className="text-xs text-gray-400 dark:text-t-text-muted hover:text-gray-600 dark:hover:text-t-text-secondary"
            >
              {isCollapsed ? '\u25B6' : '\u25BC'}
            </button>
          )}
          {editingGroupId === groupId ? (
            <input
              autoFocus
              value={editingGroupName}
              onChange={e => setEditingGroupName(e.target.value)}
              onBlur={() => handleRenameGroup(groupId)}
              onKeyDown={e => { if (e.key === 'Enter') handleRenameGroup(groupId); if (e.key === 'Escape') setEditingGroupId(null) }}
              className="text-sm font-semibold bg-white dark:bg-t-bg-card border border-gray-300 dark:border-t-border rounded px-2 py-0.5 w-32"
            />
          ) : (
            <span className="text-sm font-semibold text-gray-800 dark:text-t-text-primary flex-1">
              {isUngrouped ? '미분류' : group!.name}
            </span>
          )}
          <span className="text-xs text-gray-400 dark:text-t-text-muted bg-gray-100 dark:bg-t-bg-elevated px-1.5 py-0.5 rounded-full">
            {groupItems.length}
          </span>
          {groupItems.length > 0 && (
            <button
              onClick={() => selectAll(groupCodes)}
              className="text-[10px] text-gray-400 dark:text-t-text-muted hover:text-gray-600 dark:hover:text-t-text-secondary px-1"
              title="전체선택/해제"
            >
              {groupCodes.every(c => selectedCodes.has(c)) ? '해제' : '전체'}
            </button>
          )}
          {!isUngrouped && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => { setEditingGroupId(groupId); setEditingGroupName(group!.name) }}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-t-text-secondary p-0.5"
                title="이름 변경"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              <button
                onClick={() => handleDeleteGroup(group!.id, group!.name)}
                className="text-gray-400 hover:text-red-500 p-0.5"
                title="그룹 삭제"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* 아이템 목록 */}
        {!isCollapsed && (
          <div className="divide-y divide-gray-100 dark:divide-t-border">
            {groupItems.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-gray-400 dark:text-t-text-muted">
                {isUngrouped ? '미분류 종목이 없습니다' : '그룹에 종목이 없습니다'}
              </div>
            ) : (
              groupItems.map((item) => renderItemRow(item))
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-t-text-primary">관심종목</h1>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-0.5">
            {items.length}개 종목 / {groups.length}개 그룹
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* 선택된 종목 이동 */}
          {selectedCodes.size > 0 && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-500 dark:text-t-text-muted">{selectedCodes.size}개 선택</span>
              <select
                onChange={e => {
                  const val = e.target.value
                  if (val === '') return
                  handleMoveToGroup(val === 'null' ? null : Number(val))
                  e.target.value = ''
                }}
                className="text-xs border border-gray-300 dark:border-t-border rounded-md px-2 py-1 bg-white dark:bg-t-bg-card text-gray-700 dark:text-t-text-secondary"
                defaultValue=""
              >
                <option value="" disabled>이동...</option>
                <option value="null">미분류</option>
                {groups.map(g => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
          )}
          <button
            onClick={() => { setShowAddStock(!showAddStock); setShowCreateGroup(false) }}
            className="px-3 py-1.5 text-sm font-medium bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition-colors"
          >
            + 종목
          </button>
          <button
            onClick={() => { setShowCreateGroup(!showCreateGroup); setShowAddStock(false) }}
            className="px-3 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            + 그룹
          </button>
        </div>
      </div>

      {/* 종목 추가 검색 */}
      {showAddStock && (
        <div className="relative bg-white dark:bg-t-bg-card p-3 rounded-lg border border-gray-200 dark:border-t-border">
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={addQuery}
              onChange={e => handleAddQueryChange(e.target.value)}
              onKeyDown={e => { if (e.key === 'Escape') { setShowAddStock(false); setAddQuery(''); setAddResults([]) } }}
              placeholder="종목명 또는 코드를 입력하세요"
              className="flex-1 text-sm border border-gray-300 dark:border-t-border rounded-md px-3 py-2 bg-white dark:bg-t-bg text-gray-900 dark:text-t-text-primary focus:ring-1 focus:ring-amber-500 outline-none"
            />
            {addLoading && (
              <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-amber-500 rounded-full" />
            )}
            <button
              onClick={() => { setShowAddStock(false); setAddQuery(''); setAddResults([]) }}
              className="text-sm text-gray-500 dark:text-t-text-muted hover:text-gray-700"
            >
              닫기
            </button>
          </div>
          {addResults.length > 0 && (
            <div className="mt-2 border border-gray-200 dark:border-t-border rounded-lg max-h-60 overflow-auto">
              {addResults.map(stock => {
                const alreadyAdded = items.some(i => i.stock_code === stock.code)
                return (
                  <button
                    key={stock.code}
                    onClick={() => !alreadyAdded && handleAddStock(stock.code, stock.name)}
                    disabled={alreadyAdded}
                    className={`w-full px-3 py-2 text-left flex items-center justify-between border-b border-gray-100 dark:border-t-border last:border-0 transition-colors ${
                      alreadyAdded
                        ? 'bg-gray-50 dark:bg-t-bg-elevated opacity-50 cursor-not-allowed'
                        : 'hover:bg-amber-50 dark:hover:bg-amber-900/10'
                    }`}
                  >
                    <div>
                      <span className="text-sm font-medium text-gray-900 dark:text-t-text-primary">{stock.name}</span>
                      <span className="text-xs text-gray-400 dark:text-t-text-muted ml-2">{stock.code}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-t-bg-elevated text-gray-500 dark:text-t-text-muted">
                        {stock.market}
                      </span>
                      {alreadyAdded ? (
                        <span className="text-xs text-green-500">추가됨</span>
                      ) : (
                        <span className="text-xs text-amber-500 font-medium">+ 추가</span>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* 그룹 생성 폼 */}
      {showCreateGroup && (
        <div className="flex items-center gap-2 bg-white dark:bg-t-bg-card p-3 rounded-lg border border-gray-200 dark:border-t-border">
          <input
            autoFocus
            value={newGroupName}
            onChange={e => setNewGroupName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleCreateGroup(); if (e.key === 'Escape') setShowCreateGroup(false) }}
            placeholder="그룹 이름"
            className="flex-1 text-sm border border-gray-300 dark:border-t-border rounded-md px-3 py-1.5 bg-white dark:bg-t-bg text-gray-900 dark:text-t-text-primary focus:ring-1 focus:ring-indigo-500"
          />
          <div className="flex gap-1">
            {GROUP_COLORS.map(c => (
              <button
                key={c}
                onClick={() => setNewGroupColor(c)}
                className={`w-5 h-5 rounded-full border-2 transition-all ${newGroupColor === c ? 'border-gray-800 dark:border-white scale-110' : 'border-transparent'}`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <button onClick={handleCreateGroup} className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
            생성
          </button>
          <button onClick={() => setShowCreateGroup(false)} className="px-3 py-1.5 text-sm text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary">
            취소
          </button>
        </div>
      )}

      {/* 그룹 섹션들 */}
      <div className="space-y-3">
        {groups.map(group => {
          const groupItems = groupedItems.get(group.id) || []
          return renderGroupSection(group, groupItems)
        })}

        {/* 미분류 */}
        {renderGroupSection(null, groupedItems.get(null) || [])}
      </div>

      {items.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-t-text-muted">
          <p className="text-lg mb-2">관심종목이 없습니다</p>
          <p className="text-sm">다른 페이지에서 종목의 &#9733; 아이콘을 클릭하여 추가하세요</p>
        </div>
      )}
    </div>
  )
}
