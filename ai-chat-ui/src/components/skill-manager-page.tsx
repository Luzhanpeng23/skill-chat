import { useEffect, useMemo, useState } from 'react'
import { Eye, EyeOff, Loader2, Plus, Search, Trash2, RotateCcw, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'

import type { SkillPack, SkillTask } from '@/types'
import {
  createSkillTask,
  deleteSkillTask,
  deleteSkillPack,
  listMySkillPacks,
  listSkillTasks,
  updateSkillPackVisibility,
} from '@/lib/skills'
import { resolveTaskDisplayTitle } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { TaskDetailsPage } from './task-details-page'
import { withBasePath } from '@/lib/base-path'

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
}

// 合并任务和技能包数据
interface UnifiedItem {
  task: SkillTask
  pack?: SkillPack
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  fileName: string
  fileSize: number
  verifiedCount: number
  visibility?: 'public' | 'private'
  createdAt: string
}

type StatusFilter = 'all' | 'running' | 'completed' | 'failed'

export function SkillManagerPage() {
  const [tasks, setTasks] = useState<SkillTask[]>([])
  const [packs, setPacks] = useState<SkillPack[]>([])
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [taskToDelete, setTaskToDelete] = useState<SkillTask | null>(null)
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null)
  const [updatingPackId, setUpdatingPackId] = useState<string | null>(null)

  const refreshData = async () => {
    const [nextTasks, nextPacks] = await Promise.all([listSkillTasks(), listMySkillPacks()])
    setTasks(nextTasks.filter((task) => task.fileName && task.fileName.trim() !== ''))
    setPacks(nextPacks)
  }

  useEffect(() => {
    refreshData().catch((error: unknown) => {
      console.error('Failed to load skill data:', error)
      toast.error('加载技能数据失败')
    })
  }, [])

  // 合并任务和技能包数据
  const unifiedItems = useMemo<UnifiedItem[]>(() => {
    const packMap = new Map<string, SkillPack>()
    const taskIds = new Set(tasks.map(t => t.id))
    
    packs.forEach((pack) => {
      if (pack.taskId) {
        packMap.set(pack.taskId, pack)
      }
    })

    // 有任务的技能包
    const taskBasedItems: UnifiedItem[] = tasks.map((task) => {
      const pack = packMap.get(task.id)
      const title = resolveTaskDisplayTitle(task)
      return {
        task,
        pack,
        title,
        status: task.status,
        fileName: task.fileName,
        fileSize: task.fileSize,
        verifiedCount: pack?.verifiedCount || 0,
        visibility: pack?.visibility,
        createdAt: task.createdAt,
      }
    })

    // 没有关联任务的技能包（从广场复制的）
    const standalonePacks: UnifiedItem[] = packs
      .filter(pack => !pack.taskId || !taskIds.has(pack.taskId))
      .map(pack => ({
        task: {
          id: pack.id,
          type: 'book2skill' as const,
          status: 'completed' as const,
          createdAt: pack.createdAt,
          updatedAt: pack.createdAt,
          fileName: pack.title || '未知文件',
          filePath: '',
          fileSize: 0,
          mimeType: '',
        },
        pack,
        title: pack.title || '未命名技能包',
        status: 'completed' as const,
        fileName: pack.title || '未知文件',
        fileSize: 0,
        verifiedCount: pack.verifiedCount || 0,
        visibility: pack.visibility,
        createdAt: pack.createdAt,
      }))

    return [...taskBasedItems, ...standalonePacks]
  }, [tasks, packs])

  // 筛选和搜索
  const filteredItems = useMemo(() => {
    let items = unifiedItems

    // 状态筛选
    if (statusFilter !== 'all') {
      items = items.filter((item) => {
        if (statusFilter === 'running') {
          return item.status === 'pending' || item.status === 'running'
        }
        return item.status === statusFilter
      })
    }

    // 搜索筛选
    const keyword = searchQuery.trim().toLowerCase()
    if (keyword) {
      items = items.filter((item) => {
        return (
          item.title.toLowerCase().includes(keyword) ||
          item.fileName.toLowerCase().includes(keyword)
        )
      })
    }

    return items
  }, [unifiedItems, statusFilter, searchQuery])

  // 统计各状态数量
  const statusCounts = useMemo(() => {
    const counts = {
      all: unifiedItems.length,
      running: 0,
      completed: 0,
      failed: 0,
    }
    unifiedItems.forEach((item) => {
      if (item.status === 'pending' || item.status === 'running') {
        counts.running++
      } else if (item.status === 'completed') {
        counts.completed++
      } else if (item.status === 'failed') {
        counts.failed++
      }
    })
    return counts
  }, [unifiedItems])

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    event.target.value = ''
    try {
      setSubmitting(true)
      const task = await createSkillTask(file)
      setTasks((current) => [task, ...current])
      toast.success('任务已创建')
      setActiveTaskId(task.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '创建任务失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteTask = async () => {
    if (!taskToDelete) return
    try {
      setDeletingTaskId(taskToDelete.id)
      
      // 查找关联的技能包
      const relatedPack = packs.find(p => p.taskId === taskToDelete.id || p.id === taskToDelete.id)
      
      if (relatedPack && !relatedPack.taskId) {
        // 复制的技能包（没有taskId），直接删除技能包
        await deleteSkillPack(relatedPack.id)
        setPacks((current) => current.filter((pack) => pack.id !== relatedPack.id))
        toast.success('已从我的技能中移除')
      } else {
        // 有taskId的任务，删除任务（会级联删除技能包）
        await deleteSkillTask(taskToDelete.id)
        setTasks((current) => current.filter((task) => task.id !== taskToDelete.id))
        setPacks((current) => current.filter((pack) => pack.taskId !== taskToDelete.id))
        toast.success('任务已删除')
      }
      
      setDeleteDialogOpen(false)
      setTaskToDelete(null)
      window.dispatchEvent(new Event('skill-packs-changed'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '删除失败')
    } finally {
      setDeletingTaskId(null)
    }
  }

  const handleToggleVisibility = async (pack: SkillPack) => {
    try {
      setUpdatingPackId(pack.id)
      const nextVisibility = pack.visibility === 'public' ? 'private' : 'public'
      const updated = await updateSkillPackVisibility(pack.id, nextVisibility)
      setPacks((current) => current.map((item) => (item.id === pack.id ? { ...item, ...updated } : item)))
      window.dispatchEvent(new Event('skill-packs-changed'))
      toast.success(nextVisibility === 'public' ? '已公开到广场' : '已改为私有')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '更新可见性失败')
    } finally {
      setUpdatingPackId(null)
    }
  }

  const handleLoadToChat = (packId: string) => {
    queuePackForChat(packId)
    window.history.pushState({}, '', withBasePath('/'))
    window.dispatchEvent(new Event('history-state-changed'))
  }

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  // 格式化日期
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) {
      return '今天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays === 1) {
      return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays < 7) {
      return diffDays + ' 天前'
    } else {
      return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
    }
  }

  // 渲染状态徽章
  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-xs">
            已完成
          </Badge>
        )
      case 'running':
        return (
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs">
            运行中
          </Badge>
        )
      case 'pending':
        return (
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-xs">
            等待中
          </Badge>
        )
      case 'failed':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200 text-xs">
            失败
          </Badge>
        )
      default:
        return null
    }
  }

  if (activeTaskId) {
    return <TaskDetailsPage taskId={activeTaskId} onBack={() => setActiveTaskId(null)} />
  }

  return (
    <div className="flex h-full flex-col bg-background overflow-y-auto">
      <div className="max-w-6xl mx-auto w-full p-6 md:p-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">我的技能</h1>
            <p className="text-muted-foreground text-sm mt-1">管理你的私有技能库，或将高质量的解析发布至广场。</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="搜索标题或文件..."
                className="pl-9 h-9 w-48 bg-background border-border/40 focus-visible:ring-1 rounded-md text-sm"
              />
            </div>
            <label className="shrink-0 cursor-pointer">
              <div className="flex h-9 items-center gap-1.5 rounded-md bg-foreground px-3 text-sm font-medium text-background transition hover:bg-foreground/90">
                {submitting ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
                上传 EPUB
              </div>
              <input
                type="file"
                className="hidden"
                accept=".epub,application/epub+zip"
                onChange={handleUpload}
                disabled={submitting}
              />
            </label>
          </div>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1 mb-4 border-b border-border/40 pb-0">
          {(['all', 'running', 'completed', 'failed'] as const).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                statusFilter === status
                  ? 'border-foreground text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {status === 'all' && '全部'}
              {status === 'running' && '进行中'}
              {status === 'completed' && '已完成'}
              {status === 'failed' && '失败'}
              <span className="ml-1.5 text-xs text-muted-foreground">({statusCounts[status]})</span>
            </button>
          ))}
        </div>

        {/* Data Table */}
        <div className="border border-border/40 rounded-md overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-muted/30 border-b border-border/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">标题</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">状态</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">文件</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">片段</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">可见性</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">时间</th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item, index) => (
                <tr
                  key={item.task.id}
                  className={`border-b border-border/40 hover:bg-muted/20 transition-colors ${
                    index % 2 === 0 ? 'bg-background' : 'bg-muted/10'
                  }`}
                >
                  {/* 标题 */}
                  <td className="px-4 py-3">
                    <div
                      className="text-sm font-medium text-foreground cursor-pointer hover:text-primary truncate max-w-[200px]"
                      onClick={() => setActiveTaskId(item.task.id)}
                      title={item.title}
                    >
                      {item.title}
                    </div>
                  </td>

                  {/* 状态 */}
                  <td className="px-4 py-3">
                    {renderStatusBadge(item.status)}
                  </td>

                  {/* 文件 */}
                  <td className="px-4 py-3">
                    <div className="text-xs text-muted-foreground">
                      <div className="truncate max-w-[150px]" title={item.fileName}>{item.fileName}</div>
                      <div>{formatFileSize(item.fileSize)}</div>
                    </div>
                  </td>

                  {/* 片段数 */}
                  <td className="px-4 py-3">
                    <span className="text-sm text-foreground">
                      {item.status === 'completed' ? item.verifiedCount : '-'}
                    </span>
                  </td>

                  {/* 可见性 */}
                  <td className="px-4 py-3">
                    {item.pack && item.status === 'completed' ? (
                      <Badge
                        variant="outline"
                        className={`text-xs ${
                          item.visibility === 'public'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-muted text-muted-foreground border-border'
                        }`}
                      >
                        {item.visibility === 'public' ? '公开' : '私有'}
                      </Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">-</span>
                    )}
                  </td>

                  {/* 时间 */}
                  <td className="px-4 py-3">
                    <span className="text-xs text-muted-foreground">{formatDate(item.createdAt)}</span>
                  </td>

                  {/* 操作 */}
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {item.status === 'completed' && item.pack && (
                        <>
                          {/* 只有自己创建的技能包才能切换可见性 */}
                          {item.pack.taskId && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2 text-xs"
                                  onClick={() => handleToggleVisibility(item.pack!)}
                                  disabled={updatingPackId === item.pack!.id}
                                >
                                  {updatingPackId === item.pack!.id ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : item.visibility === 'public' ? (
                                    <EyeOff className="w-3 h-3" />
                                  ) : (
                                    <Eye className="w-3 h-3" />
                                  )}
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>{item.visibility === 'public' ? '设为私有' : '公开到广场'}</p>
                              </TooltipContent>
                            </Tooltip>
                          )}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs text-primary"
                                onClick={() => handleLoadToChat(item.pack!.id)}
                              >
                                <ExternalLink className="w-3 h-3" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>装载到新对话</p>
                            </TooltipContent>
                          </Tooltip>
                        </>
                      )}
                      {item.status === 'failed' && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs text-amber-600"
                              onClick={() => setActiveTaskId(item.task.id)}
                            >
                              <RotateCcw className="w-3 h-3" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>查看详情</p>
                          </TooltipContent>
                        </Tooltip>
                      )}
                      {/* 删除按钮：自己创建的任务或复制的技能包都可以删除 */}
                      {(item.pack?.taskId || item.pack) && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive"
                              onClick={() => {
                                setTaskToDelete(item.task)
                                setDeleteDialogOpen(true)
                              }}
                              disabled={deletingTaskId === item.task.id}
                            >
                              {deletingTaskId === item.task.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Trash2 className="w-3 h-3" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{item.pack?.taskId ? '删除任务' : '从我的技能中移除'}</p>
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Empty State */}
          {filteredItems.length === 0 && (
            <div className="text-center py-12">
              <p className="text-muted-foreground text-sm">
                {searchQuery ? '未找到匹配的技能包' : '暂无数据'}
              </p>
              {!searchQuery && statusFilter === 'all' && (
                <p className="text-muted-foreground text-xs mt-1">
                  点击右上角"上传 EPUB"开始解析
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer Info */}
        {filteredItems.length > 0 && (
          <div className="mt-3 text-xs text-muted-foreground text-right">
            共 {filteredItems.length} 条记录
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>删除任务？</DialogTitle>
            <DialogDescription>这会删除上传文件、生成的技能包和相关记录，且不可撤销。</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0 mt-4">
            <Button variant="ghost" onClick={() => setDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteTask}
              disabled={deletingTaskId !== null}
              className="rounded-md px-4"
            >
              {deletingTaskId ? '删除中...' : '确认删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
