import { useEffect, useState } from 'react'
import {
  RefreshCw,
  Trash2,
  ShieldAlert,
  ShieldCheck,
  Users,
  MessageSquare,
  ListTodo,
  Package,
  Ban,
  CheckCircle2,
  Globe,
  Lock,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  deleteAdminConversation,
  deleteAdminTask,
  getAdminStats,
  listAdminConversations,
  listAdminSkillPacks,
  listAdminTasks,
  listAdminUsers,
  updateAdminSkillPackVisibility,
  updateAdminUser,
} from '@/lib/admin'
import type { AdminStats, ConversationEntry, SkillPack, SkillTask, UserProfile } from '@/types'
import { resolveSkillPackDisplayTitle, resolveTaskDisplayTitle } from '@/lib/utils'
import { cn } from '@/lib/utils'

const EMPTY_STATS: AdminStats = {
  users: 0,
  conversations: 0,
  tasks: 0,
  skillPacks: 0,
  publicSkillPacks: 0,
  activeUsers: 0,
}

export function AdminPage() {
  const [stats, setStats] = useState<AdminStats>(EMPTY_STATS)
  const [users, setUsers] = useState<UserProfile[]>([])
  const [tasks, setTasks] = useState<SkillTask[]>([])
  const [packs, setPacks] = useState<SkillPack[]>([])
  const [conversations, setConversations] = useState<ConversationEntry[]>([])
  const [refreshing, setRefreshing] = useState(false)

  const refreshData = async () => {
    try {
      setRefreshing(true)
      const [nextStats, nextUsers, nextTasks, nextPacks, nextConversations] = await Promise.all([
        getAdminStats(),
        listAdminUsers(),
        listAdminTasks(),
        listAdminSkillPacks(),
        listAdminConversations(),
      ])
      setStats(nextStats)
      setUsers(nextUsers)
      setTasks(nextTasks)
      setPacks(nextPacks)
      setConversations(nextConversations)
    } catch (error) {
      console.error('Failed to load admin data:', error)
      toast.error(error instanceof Error ? error.message : '加载管理数据失败')
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    refreshData().catch(() => undefined)
  }, [])

  const handleToggleAdmin = async (user: UserProfile) => {
    try {
      const updated = await updateAdminUser(user.id, { isAdmin: !user.isAdmin })
      setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, ...updated } : item)))
      toast.success(updated.isAdmin ? '已设为管理员' : '已取消管理员')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '更新失败')
    }
  }

  const handleToggleUserStatus = async (user: UserProfile) => {
    try {
      const nextStatus = user.status === 'active' ? 'disabled' : 'active'
      const updated = await updateAdminUser(user.id, { status: nextStatus })
      setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, ...updated } : item)))
      toast.success(nextStatus === 'active' ? '用户已恢复' : '用户已停用')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '更新失败')
    }
  }

  const handleTogglePackVisibility = async (pack: SkillPack) => {
    try {
      const nextVisibility = pack.visibility === 'public' ? 'private' : 'public'
      const updated = await updateAdminSkillPackVisibility(pack.id, nextVisibility)
      setPacks((current) => current.map((item) => (item.id === pack.id ? { ...item, ...updated } : item)))
      toast.success(nextVisibility === 'public' ? '已公开到广场' : '已设为私有')
      refreshData().catch(() => undefined)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '更新失败')
    }
  }

  const handleDeleteTask = async (taskId: string) => {
    try {
      await deleteAdminTask(taskId)
      setTasks((current) => current.filter((item) => item.id !== taskId))
      toast.success('任务已删除')
      refreshData().catch(() => undefined)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '删除任务失败')
    }
  }

  const handleDeleteConversation = async (conversationId: string) => {
    try {
      await deleteAdminConversation(conversationId)
      setConversations((current) => current.filter((item) => item.id !== conversationId))
      toast.success('对话已删除')
      refreshData().catch(() => undefined)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '删除对话失败')
    }
  }

  return (
    <div className="flex flex-col h-full bg-background overflow-y-auto">
      <div className="max-w-5xl mx-auto w-full p-6 md:p-8">
        {/* Header */}
        <div className="flex flex-col gap-3 mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">管理控制台</h1>
            <Button
              variant="outline"
              className="rounded-md h-9 px-4 border-border/50 shadow-sm"
              onClick={() => refreshData()}
              disabled={refreshing}
            >
              {refreshing ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              刷新数据
            </Button>
          </div>
          <p className="text-sm text-muted-foreground max-w-2xl">全局概览，掌控系统的所有数据、用户与资源运行状态。</p>
        </div>

        {/* Stats Dashboard - Compact engineering style */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <div className="bg-muted/30 border border-border/50 rounded-md p-4 flex flex-col gap-1">
            <div className="text-muted-foreground text-sm font-medium mb-1 flex items-center gap-2">
              <Users className="w-4 h-4" /> 用户
            </div>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {stats.activeUsers} <span className="text-sm font-normal text-muted-foreground">/ {stats.users}</span>
            </div>
            <div className="text-xs text-muted-foreground">活跃 / 总计</div>
          </div>

          <div className="bg-muted/30 border border-border/50 rounded-md p-4 flex flex-col gap-1">
            <div className="text-muted-foreground text-sm font-medium mb-1 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" /> 对话
            </div>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {stats.conversations}
            </div>
            <div className="text-xs text-muted-foreground">全局对话总数</div>
          </div>

          <div className="bg-muted/30 border border-border/50 rounded-md p-4 flex flex-col gap-1">
            <div className="text-muted-foreground text-sm font-medium mb-1 flex items-center gap-2">
              <ListTodo className="w-4 h-4" /> 任务
            </div>
            <div className="text-2xl font-bold tracking-tight text-foreground">{stats.tasks}</div>
            <div className="text-xs text-muted-foreground">解析任务总计</div>
          </div>

          <div className="bg-muted/30 border border-border/50 rounded-md p-4 flex flex-col gap-1">
            <div className="text-muted-foreground text-sm font-medium mb-1 flex items-center gap-2">
              <Package className="w-4 h-4" /> 技能包
            </div>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {stats.publicSkillPacks}{' '}
              <span className="text-sm font-normal text-muted-foreground">/ {stats.skillPacks}</span>
            </div>
            <div className="text-xs text-muted-foreground">公开 / 总计</div>
          </div>
        </div>

        {/* Unified Lists with Compact Zebra Tables */}
        <div className="flex flex-col">
          <Tabs defaultValue="users" className="w-full">
            <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-2 scrollbar-none">
              <TabsList className="bg-transparent h-auto p-0 gap-2">
                {(['users', 'packs', 'tasks', 'conversations'] as const).map((tab) => (
                  <TabsTrigger
                    key={tab}
                    value={tab}
                    className="px-4 py-2 rounded-md text-sm font-medium transition-colors data-[state=active]:bg-foreground data-[state=active]:text-background data-[state=inactive]:bg-muted/30 data-[state=inactive]:text-muted-foreground data-[state=inactive]:hover:bg-muted/50 data-[state=active]:shadow-none border border-transparent data-[state=inactive]:border-border/50"
                  >
                    {tab === 'users'
                      ? '用户管理'
                      : tab === 'packs'
                        ? '技能包'
                        : tab === 'tasks'
                          ? '解析任务'
                          : '全局对话'}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>

            <TabsContent value="users" className="m-0 border-none outline-none">
              <div className="flex flex-col border border-border/50 rounded-md overflow-hidden bg-background">
                {users.map((user, i) => (
                  <div
                    key={user.id}
                    className={cn(
                      'flex flex-col sm:flex-row sm:items-center justify-between px-3 py-2 border-border/50 hover:bg-muted/5 transition-colors group',
                      i !== users.length - 1 && 'border-b',
                      i % 2 !== 0 && 'bg-muted/10',
                    )}
                  >
                    <div className="flex flex-col gap-1 w-full sm:w-auto">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{user.email}</span>
                        {user.isAdmin && (
                          <Badge
                            variant="outline"
                            className="h-5 font-normal px-2 bg-blue-50 text-blue-700 border-blue-200"
                          >
                            Admin
                          </Badge>
                        )}
                        {user.status !== 'active' ? (
                          <Badge
                            variant="outline"
                            className="h-5 font-normal px-2 bg-red-50 text-red-700 border-red-200"
                          >
                            已停用
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="h-5 font-normal px-2 bg-emerald-50 text-emerald-700 border-emerald-200"
                          >
                            正常
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground font-mono">
                        ID: {user.id.slice(0, 8)}... · 对话: {(user as any).conversationCount ?? 0} · 任务:{' '}
                        {(user as any).taskCount ?? 0}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 mt-3 sm:mt-0 opacity-100 sm:opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs font-medium"
                        onClick={() => handleToggleAdmin(user)}
                      >
                        {user.isAdmin ? (
                          <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />
                        ) : (
                          <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
                        )}
                        {user.isAdmin ? '取消管理' : '设为管理'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className={cn(
                          'h-8 text-xs font-medium',
                          user.status === 'active'
                            ? 'text-destructive hover:text-destructive hover:bg-destructive/10'
                            : 'text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50',
                        )}
                        onClick={() => handleToggleUserStatus(user)}
                      >
                        {user.status === 'active' ? (
                          <Ban className="w-3.5 h-3.5 mr-1.5" />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                        )}
                        {user.status === 'active' ? '停用' : '恢复'}
                      </Button>
                    </div>
                  </div>
                ))}
                {users.length === 0 && <div className="p-8 text-center text-muted-foreground text-sm">暂无数据</div>}
              </div>
            </TabsContent>

            <TabsContent value="packs" className="m-0 border-none outline-none">
              <div className="flex flex-col border border-border/50 rounded-md overflow-hidden bg-background">
                {packs.map((pack, i) => (
                  <div
                    key={pack.id}
                    className={cn(
                      'flex flex-col sm:flex-row sm:items-center justify-between px-3 py-2 border-border/50 hover:bg-muted/5 transition-colors group',
                      i !== packs.length - 1 && 'border-b',
                      i % 2 !== 0 && 'bg-muted/10',
                    )}
                  >
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">
                          {resolveSkillPackDisplayTitle(pack)}
                        </span>
                        <Badge
                          variant="outline"
                          className={cn(
                            'h-5 font-normal px-2',
                            pack.visibility === 'public'
                              ? 'border-emerald-200 text-emerald-700 bg-emerald-50'
                              : 'border-border text-muted-foreground bg-muted/50',
                          )}
                        >
                          {pack.visibility === 'public' ? '公开' : '私有'}
                        </Badge>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        用户: {pack.ownerEmail || '未知'} · 技能数: {pack.verifiedCount || 0}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 mt-3 sm:mt-0 opacity-100 sm:opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs font-medium"
                        onClick={() => handleTogglePackVisibility(pack)}
                      >
                        {pack.visibility === 'public' ? (
                          <Lock className="w-3.5 h-3.5 mr-1.5" />
                        ) : (
                          <Globe className="w-3.5 h-3.5 mr-1.5" />
                        )}
                        {pack.visibility === 'public' ? '转为私有' : '公开至广场'}
                      </Button>
                    </div>
                  </div>
                ))}
                {packs.length === 0 && <div className="p-8 text-center text-muted-foreground text-sm">暂无数据</div>}
              </div>
            </TabsContent>

            <TabsContent value="tasks" className="m-0 border-none outline-none">
              <div className="flex flex-col border border-border/50 rounded-md overflow-hidden bg-background">
                {tasks.map((task, i) => (
                  <div
                    key={task.id}
                    className={cn(
                      'flex flex-col sm:flex-row sm:items-center justify-between px-3 py-2 border-border/50 hover:bg-muted/5 transition-colors group',
                      i !== tasks.length - 1 && 'border-b',
                      i % 2 !== 0 && 'bg-muted/10',
                    )}
                  >
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{resolveTaskDisplayTitle(task)}</span>
                        <Badge
                          variant="outline"
                          className={cn(
                            'h-5 font-normal px-2 capitalize',
                            task.status === 'completed'
                              ? 'border-emerald-200 text-emerald-700 bg-emerald-50'
                              : task.status === 'failed'
                                ? 'border-red-200 text-red-700 bg-red-50'
                                : 'border-blue-200 text-blue-700 bg-blue-50',
                          )}
                        >
                          {task.status}
                        </Badge>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        文件: {task.fileName} ({(task.fileSize / 1024 / 1024).toFixed(2)}MB) · 用户:{' '}
                        {task.ownerEmail || '未知'}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 mt-3 sm:mt-0 opacity-100 sm:opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        onClick={() => handleDeleteTask(task.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
                {tasks.length === 0 && <div className="p-8 text-center text-muted-foreground text-sm">暂无数据</div>}
              </div>
            </TabsContent>

            <TabsContent value="conversations" className="m-0 border-none outline-none">
              <div className="flex flex-col border border-border/50 rounded-md overflow-hidden bg-background">
                {conversations.map((conv, i) => (
                  <div
                    key={conv.id}
                    className={cn(
                      'flex flex-col sm:flex-row sm:items-center justify-between px-3 py-2 border-border/50 hover:bg-muted/5 transition-colors group',
                      i !== conversations.length - 1 && 'border-b',
                      i % 2 !== 0 && 'bg-muted/10',
                    )}
                  >
                    <div className="flex flex-col gap-1 min-w-0 pr-4">
                      <span className="text-sm font-medium text-foreground truncate">
                        {conv.firstMessage || '未命名对话'}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        用户: {conv.ownerEmail || '未知'} · {new Date(conv.timestamp).toLocaleDateString()}
                      </span>
                    </div>

                    <div className="shrink-0 flex items-center gap-2 mt-3 sm:mt-0 opacity-100 sm:opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        onClick={() => handleDeleteConversation(conv.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
                {conversations.length === 0 && (
                  <div className="p-8 text-center text-muted-foreground text-sm">暂无数据</div>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
