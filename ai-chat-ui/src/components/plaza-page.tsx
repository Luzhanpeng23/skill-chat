import { useEffect, useMemo, useState } from 'react'
import { Search, Globe, ExternalLink, User, Plus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { listPublicSkillPacks, copySkillPackToMyLibrary } from '@/lib/skills'
import { withBasePath } from '@/lib/base-path'
import { resolveSkillPackDisplayTitle } from '@/lib/utils'
import type { SkillPack } from '@/types'

const PENDING_SKILL_PACK_KEY = 'pending-skill-pack-id'

function queuePackForChat(packId: string) {
  const current = window.sessionStorage.getItem(PENDING_SKILL_PACK_KEY)
  const parsed = current ? (JSON.parse(current) as unknown) : []
  const next = Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : []
  if (!next.includes(packId)) {
    next.push(packId)
  }
  window.sessionStorage.setItem(PENDING_SKILL_PACK_KEY, JSON.stringify(next))
  window.dispatchEvent(new Event('skill-packs-changed'))
  window.history.pushState({}, '', withBasePath('/'))
  window.dispatchEvent(new Event('history-state-changed'))
}

export function PlazaPage() {
  const [packs, setPacks] = useState<SkillPack[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [copyingPackId, setCopyingPackId] = useState<string | null>(null)

  useEffect(() => {
    listPublicSkillPacks()
      .then(setPacks)
      .catch((error: unknown) => {
        console.error('Failed to load public skill packs:', error)
        toast.error('加载广场失败')
      })
      .finally(() => setLoading(false))
  }, [])

  const filteredPacks = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase()
    if (!keyword) return packs
    return packs.filter((pack) => {
      const title = resolveSkillPackDisplayTitle(pack).toLowerCase()
      const author = (pack.author || pack.ownerEmail || '').toLowerCase()
      return title.includes(keyword) || author.includes(keyword)
    })
  }, [packs, searchQuery])

  const handleLoadToChat = (packId: string) => {
    queuePackForChat(packId)
    window.history.pushState({}, '', withBasePath('/'))
    window.dispatchEvent(new Event('history-state-changed'))
  }

  const handleCopyToMyLibrary = async (packId: string) => {
    try {
      setCopyingPackId(packId)
      await copySkillPackToMyLibrary(packId)
      toast.success('已添加到我的技能')
      // 通知技能列表更新
      window.dispatchEvent(new Event('skill-packs-changed'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '添加失败')
    } finally {
      setCopyingPackId(null)
    }
  }

  // 格式化日期
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) {
      return '今天'
    } else if (diffDays === 1) {
      return '昨天'
    } else if (diffDays < 7) {
      return diffDays + ' 天前'
    } else if (diffDays < 30) {
      return Math.floor(diffDays / 7) + ' 周前'
    } else {
      return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
    }
  }

  return (
    <div className="flex h-full flex-col bg-background overflow-y-auto">
      <div className="max-w-6xl mx-auto w-full p-6 md:p-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">技能广场</h1>
            <p className="text-muted-foreground text-sm mt-1">浏览社区共享的解析技能包，一键装载到你的对话中。</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="搜索标题或作者..."
                className="pl-9 h-9 w-64 bg-background border-border/40 focus-visible:ring-1 rounded-md text-sm"
              />
            </div>
          </div>
        </div>

        {/* Stats Bar */}
        <div className="flex items-center gap-4 mb-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Globe className="w-4 h-4" />
            <span>共 {packs.length} 个公开技能包</span>
          </div>
        </div>

        {/* Data Table */}
        <div className="border border-border/40 rounded-md overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-muted/30 border-b border-border/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">标题</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">作者</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">片段数</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">发布时间</th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredPacks.map((pack, index) => {
                const title = resolveSkillPackDisplayTitle(pack)
                return (
                  <tr
                    key={pack.id}
                    className={`border-b border-border/40 hover:bg-muted/20 transition-colors ${
                      index % 2 === 0 ? 'bg-background' : 'bg-muted/10'
                    }`}
                  >
                    {/* 标题 */}
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-foreground truncate max-w-[250px]" title={title}>
                        {title}
                      </div>
                    </td>

                    {/* 作者 */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                        <User className="w-3.5 h-3.5 opacity-70" />
                        <span className="truncate max-w-[150px]">{pack.author || pack.ownerEmail || '未知'}</span>
                      </div>
                    </td>

                    {/* 片段数 */}
                    <td className="px-4 py-3">
                      <Badge variant="outline" className="text-xs bg-muted/50 text-muted-foreground border-border">
                        {pack.verifiedCount || 0} 个
                      </Badge>
                    </td>

                    {/* 发布时间 */}
                    <td className="px-4 py-3">
                      <span className="text-xs text-muted-foreground">{formatDate(pack.createdAt)}</span>
                    </td>

                    {/* 操作 */}
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs text-muted-foreground"
                              onClick={() => handleCopyToMyLibrary(pack.id)}
                              disabled={copyingPackId === pack.id}
                            >
                              {copyingPackId === pack.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Plus className="w-3 h-3" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>添加到我的技能</p>
                          </TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs text-primary"
                              onClick={() => handleLoadToChat(pack.id)}
                            >
                              <ExternalLink className="w-3 h-3" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>装载到新对话</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {/* Loading State */}
          {loading && (
            <div className="text-center py-12">
              <p className="text-muted-foreground text-sm">加载中...</p>
            </div>
          )}

          {/* Empty State */}
          {!loading && filteredPacks.length === 0 && (
            <div className="text-center py-12">
              <Globe className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-muted-foreground text-sm">
                {searchQuery ? '未找到匹配的技能包' : '暂无公开技能包'}
              </p>
              {!searchQuery && (
                <p className="text-muted-foreground text-xs mt-1">
                  在"我的技能"中将技能包设为公开后会显示在这里
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer Info */}
        {!loading && filteredPacks.length > 0 && (
          <div className="mt-3 text-xs text-muted-foreground text-right">
            共 {filteredPacks.length} 个技能包
          </div>
        )}
      </div>
    </div>
  )
}
