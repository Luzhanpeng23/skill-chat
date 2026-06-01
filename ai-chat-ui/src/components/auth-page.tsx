import { useMemo, useState } from 'react'
import { Loader2, LockKeyhole, Mail, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { login, register } from '@/lib/auth'
import type { UserProfile } from '@/types'

interface AuthPageProps {
  mode: 'login' | 'register'
  onModeChange: (mode: 'login' | 'register') => void
  onAuthenticated: (user: UserProfile) => void
}

export function AuthPage({ mode, onModeChange, onAuthenticated }: AuthPageProps) {
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [registerEmail, setRegisterEmail] = useState('')
  const [registerPassword, setRegisterPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const headerCopy = useMemo(
    () =>
      mode === 'login'
        ? {
            title: 'Welcome back.',
            description: '登录你的工作区，进入私有对话与技能广场。',
            action: '登录',
          }
        : {
            title: 'Create workspace.',
            description: '注册账户，拥有完全隔离的独立对话与专属技能库。',
            action: '注册',
          },
    [mode],
  )

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setSubmitting(true)
      const user = await login(loginEmail, loginPassword)
      toast.success('登录成功')
      onAuthenticated(user)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleRegister = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setSubmitting(true)
      const user = await register(registerEmail, registerPassword, confirmPassword)
      toast.success('注册成功')
      onAuthenticated(user)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '注册失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-svh bg-background text-foreground flex flex-col md:flex-row">
      {/* Left side - Typography & Brand */}
      <div className="flex-1 flex flex-col justify-center px-8 py-16 md:px-20 lg:px-32 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1/2 bg-gradient-to-b from-muted/30 to-transparent pointer-events-none" />
        <div className="relative z-10 max-w-2xl">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter text-foreground mb-8 leading-[1.1]">
            Skill Chat <br />
            <span className="text-muted-foreground">Focus on creation.</span>
          </h1>

          <div className="space-y-6 text-lg text-muted-foreground">
            <div className="flex flex-col gap-2 border-l-2 border-border/50 pl-6">
              <span className="font-semibold text-foreground">私有对话</span>
              <span className="text-sm">每个用户拥有独立的数据空间，消息与上下文绝对隔离。</span>
            </div>
            <div className="flex flex-col gap-2 border-l-2 border-border/50 pl-6">
              <span className="font-semibold text-foreground">技能广场</span>
              <span className="text-sm">将私有拆书技能打包沉淀，发布至广场，团队一键复用。</span>
            </div>
            <div className="flex flex-col gap-2 border-l-2 border-border/50 pl-6">
              <span className="font-semibold text-foreground">极简架构</span>
              <span className="text-sm">专注任务流的纯净排版，消除视觉噪音，让注意力回归工具本身。</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="w-full md:w-[480px] lg:w-[560px] bg-background md:bg-muted/10 flex flex-col justify-center px-8 py-16 md:px-16 border-l border-border/40">
        <div className="max-w-sm w-full mx-auto space-y-10">
          <div className="space-y-2">
            <h2 className="text-3xl font-semibold tracking-tight">{headerCopy.title}</h2>
            <p className="text-muted-foreground text-sm">{headerCopy.description}</p>
          </div>

          <Tabs value={mode} onValueChange={(value) => onModeChange(value as 'login' | 'register')} className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-8 bg-muted/50 p-1 rounded-xl">
              <TabsTrigger value="login" className="rounded-lg text-sm">
                登录
              </TabsTrigger>
              <TabsTrigger value="register" className="rounded-lg text-sm">
                注册
              </TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="mt-0">
              <form className="space-y-5" onSubmit={handleLogin}>
                <div className="space-y-4">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground pl-1">邮箱</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
                      <Input
                        value={loginEmail}
                        onChange={(event) => setLoginEmail(event.target.value)}
                        placeholder="name@example.com"
                        className="pl-10 bg-background border-border/40 h-12 rounded-xl focus-visible:ring-1"
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground pl-1">密码</label>
                    <div className="relative">
                      <LockKeyhole className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
                      <Input
                        type="password"
                        value={loginPassword}
                        onChange={(event) => setLoginPassword(event.target.value)}
                        placeholder="••••••••"
                        className="pl-10 bg-background border-border/40 h-12 rounded-xl focus-visible:ring-1"
                        required
                      />
                    </div>
                  </div>
                </div>
                <Button
                  type="submit"
                  className="w-full h-12 rounded-xl text-base font-medium mt-4 group"
                  disabled={submitting}
                >
                  {submitting ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      进入系统{' '}
                      <ArrowRight className="w-4 h-4 ml-2 opacity-70 group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register" className="mt-0">
              <form className="space-y-5" onSubmit={handleRegister}>
                <div className="space-y-4">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground pl-1">邮箱</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
                      <Input
                        value={registerEmail}
                        onChange={(event) => setRegisterEmail(event.target.value)}
                        placeholder="name@example.com"
                        className="pl-10 bg-background border-border/40 h-12 rounded-xl focus-visible:ring-1"
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground pl-1">密码</label>
                    <div className="relative">
                      <LockKeyhole className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
                      <Input
                        type="password"
                        value={registerPassword}
                        onChange={(event) => setRegisterPassword(event.target.value)}
                        placeholder="至少 8 位"
                        className="pl-10 bg-background border-border/40 h-12 rounded-xl focus-visible:ring-1"
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground pl-1">确认密码</label>
                    <div className="relative">
                      <LockKeyhole className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
                      <Input
                        type="password"
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        placeholder="再次确认密码"
                        className="pl-10 bg-background border-border/40 h-12 rounded-xl focus-visible:ring-1"
                        required
                      />
                    </div>
                  </div>
                </div>
                <Button
                  type="submit"
                  className="w-full h-12 rounded-xl text-base font-medium mt-4 group"
                  disabled={submitting}
                >
                  {submitting ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      创建账户{' '}
                      <ArrowRight className="w-4 h-4 ml-2 opacity-70 group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
