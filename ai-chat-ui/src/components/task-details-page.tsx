import { useEffect, useState, useMemo } from 'react'
import { ArrowLeft, Check, Loader2, Circle, X } from 'lucide-react'
import type { SkillTask, SkillTaskEvent } from '@/types'
import { getSkillArchiveUrl, listSkillTasks, subscribeSkillTaskEvents } from '@/lib/skills'
import { cn, resolveTaskDisplayTitle } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'

const STEPS = [
  { id: 'parser', label: 'Parse document' },
  { id: 'overview', label: 'Generate overview' },
  { id: 'extract', label: 'Extract candidates' },
  { id: 'verify', label: 'Verify candidates' },
  { id: 'relate', label: 'Relate skills' },
  { id: 'ria', label: 'Generate RIA skills' },
  { id: 'index', label: 'Index skill pack' },
]

export function TaskDetailsPage({ taskId, onBack }: { taskId: string; onBack: () => void }) {
  const [task, setTask] = useState<SkillTask | null>(null)
  const [events, setEvents] = useState<SkillTaskEvent[]>([])
  const [currentPhase, setCurrentPhase] = useState<string>('parser')

  useEffect(() => {
    listSkillTasks().then((tasks) => {
      const found = tasks.find((t) => t.id === taskId)
      if (found) {
        setTask(found)
        if (found.phase) setCurrentPhase(found.phase.toLowerCase())
      }
    })

    const unsubscribe = subscribeSkillTaskEvents(taskId, (event) => {
      setEvents((curr) => [...curr, event])
      if (typeof event.payload?.phase === 'string') {
        setCurrentPhase(event.payload.phase.toLowerCase())
      }
      if (event.event === 'task_completed' || event.event === 'task_failed') {
        listSkillTasks().then((tasks) => {
          const found = tasks.find((t) => t.id === taskId)
          if (found) setTask(found)
        })
      }
    })
    return () => unsubscribe()
  }, [taskId])

  const stats = useMemo(() => {
    let extracted = 0
    let verified = 0
    let rejected = 0
    let generated = 0

    events.forEach((e) => {
      if (e.event === 'candidates_extracted') extracted = Number(e.payload.count ?? 0)
      if (e.event === 'skill_verified') verified++
      if (e.event === 'skill_rejected') rejected++
      if (e.event === 'ria_completed') generated++
    })

    return { extracted, verified, rejected, generated }
  }, [events])

  if (!task) return null

  const isCompleted = task.status === 'completed'
  const isFailed = task.status === 'failed'
  const isRunning = task.status === 'running' || task.status === 'pending'

  const currentStepIndex = isCompleted ? STEPS.length - 1 : STEPS.findIndex((s) => s.id === currentPhase)
  const title = resolveTaskDisplayTitle(task)
  const fileSizeMB = (task.fileSize / 1024 / 1024).toFixed(2)

  return (
    <div className="flex flex-col h-full bg-background overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full p-8 md:p-12">
        {/* Top Nav */}
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-12 group w-fit"
        >
          <div className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-muted transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </div>
        </button>

        {/* Hero Profile */}
        <div className="flex flex-col gap-4 mb-16">
          <h1 className="text-4xl font-bold tracking-tight text-foreground">{title}</h1>
          <p className="text-lg text-muted-foreground max-w-2xl">提取书籍结构与核心知识，转化为结构化的技能集合。</p>
          <div className="flex items-center gap-3 mt-2">
            <Button
              size="lg"
              className="rounded-full px-8 bg-foreground text-background hover:bg-foreground/90 font-medium"
              disabled={!isCompleted}
              onClick={() => {
                if (isCompleted) window.open(getSkillArchiveUrl(task.id), '_blank')
              }}
            >
              {isCompleted ? '下载技能包' : isFailed ? '处理失败' : '正在处理...'}
            </Button>
          </div>
        </div>

        {/* Visuals / Processing Status */}
        {!isCompleted && (
          <>
            <div className="mb-16">
              <h2 className="text-xl font-semibold mb-6">处理进度</h2>
              <div className="flex flex-col gap-4">
                {/* Steps Visualizer Card */}
                <div className="bg-muted/30 border border-border/50 rounded-3xl p-6 md:p-8 flex flex-col gap-4 relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl" />
                  <div className="relative flex flex-col gap-4">
                    {STEPS.map((step, i) => {
                      const isPast = i < currentStepIndex || isCompleted
                      const isCurrent = i === currentStepIndex && isRunning

                      let Icon = Circle
                      let iconClass = 'w-4 h-4 text-muted-foreground/30'
                      let textClass = 'text-muted-foreground'

                      if (isPast) {
                        Icon = Check
                        iconClass = 'w-4 h-4 text-foreground'
                        textClass = 'text-foreground font-medium'
                      } else if (isCurrent) {
                        Icon = Loader2
                        iconClass = 'w-4 h-4 text-blue-500 animate-spin'
                        textClass = 'text-foreground font-medium'
                      } else if (isFailed && i === currentStepIndex) {
                        Icon = X
                        iconClass = 'w-4 h-4 text-destructive'
                        textClass = 'text-destructive font-medium'
                      }

                      return (
                        <div key={step.id} className="flex items-start gap-4 group">
                          <div className="mt-0.5 shrink-0">
                            <Icon className={iconClass} />
                          </div>
                          <div className="flex flex-col gap-0.5 min-w-0">
                            <span className={cn('text-sm', textClass)}>{step.label}</span>
                            {/* Stats */}
                            {step.id === 'extract' && stats.extracted > 0 && (isPast || isCurrent) && (
                              <span className="text-xs text-muted-foreground">Found {stats.extracted} candidates</span>
                            )}
                            {step.id === 'verify' && stats.verified > 0 && (isPast || isCurrent) && (
                              <span className="text-xs text-muted-foreground">
                                Verified {stats.verified} / Rejected {stats.rejected}
                              </span>
                            )}
                            {step.id === 'ria' && stats.generated > 0 && (isPast || isCurrent) && (
                              <span className="text-xs text-muted-foreground">Generated {stats.generated} skills</span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {isFailed && task.error && (
                  <div className="bg-red-50 border border-red-100 rounded-3xl p-6 text-sm text-red-600 font-medium">
                    错误信息: {task.error}
                  </div>
                )}
              </div>
            </div>
            <Separator className="my-8 opacity-50" />
          </>
        )}

        {/* Information Table */}
        <div>
          <h2 className="text-xl font-semibold mb-4">信息</h2>
          <div className="flex flex-col border border-border/50 rounded-2xl overflow-hidden bg-background">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/50">
              <span className="text-sm text-muted-foreground">类别</span>
              <span className="text-sm font-medium">设计</span>
            </div>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/50 bg-muted/10">
              <span className="text-sm text-muted-foreground">功能</span>
              <span className="text-sm font-medium">交互式, 写入</span>
            </div>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/50">
              <span className="text-sm text-muted-foreground">状态</span>
              <Badge
                variant="outline"
                className={cn(
                  'font-normal h-6',
                  isCompleted
                    ? 'border-emerald-200 text-emerald-700 bg-emerald-50'
                    : isFailed
                      ? 'border-red-200 text-red-700 bg-red-50'
                      : 'border-blue-200 text-blue-700 bg-blue-50',
                )}
              >
                {task.status.charAt(0).toUpperCase() + task.status.slice(1)}
              </Badge>
            </div>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/50 bg-muted/10">
              <span className="text-sm text-muted-foreground">提取片段</span>
              <span className="text-sm font-medium">{stats.extracted || '-'}</span>
            </div>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/50">
              <span className="text-sm text-muted-foreground">有效片段</span>
              <span className="text-sm font-medium">{stats.verified || '-'}</span>
            </div>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/50 bg-muted/10">
              <span className="text-sm text-muted-foreground">生成卡片</span>
              <span className="text-sm font-medium text-blue-600">{stats.generated || '-'}</span>
            </div>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/50">
              <span className="text-sm text-muted-foreground">大小</span>
              <span className="text-sm font-medium">{fileSizeMB} MB</span>
            </div>
            <div className="flex items-center justify-between px-4 py-2.5 border-border/50 bg-muted/10">
              <span className="text-sm text-muted-foreground">任务 ID</span>
              <span className="text-xs font-medium font-mono text-muted-foreground">{task.id}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
