import { useEffect, useMemo, useState } from 'react'
import Chat from './Chat.tsx'
import { AppSidebar } from './components/app-sidebar.tsx'
import { ThemeProvider } from './components/theme-provider.tsx'
import { SidebarProvider, SidebarTrigger } from './components/ui/sidebar.tsx'
import { Toaster } from './components/ui/sonner.tsx'
import { cn } from './lib/utils.ts'
import { useConversationIdFromUrl } from './hooks/useConversationIdFromUrl.tsx'
import { SkillManagerPage } from './components/skill-manager-page.tsx'
import { PlazaPage } from './components/plaza-page.tsx'
import { AdminPage } from './components/admin-page.tsx'
import { AuthPage } from './components/auth-page.tsx'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { getCurrentUser, logout } from './lib/auth.ts'
import type { UserProfile } from './types.ts'
import { Card, CardContent } from './components/ui/card.tsx'

const queryClient = new QueryClient()

function AuthSplash() {
  return (
    <div className="flex min-h-svh items-center justify-center bg-[#f7f5f1] px-6">
      <div className="text-center text-sm text-slate-500">正在加载账户信息…</div>
    </div>
  )
}

export default function App() {
  const [currentPath, setCurrentPath] = useConversationIdFromUrl()
  const [ready, setReady] = useState(false)
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null)

  useEffect(() => {
    getCurrentUser()
      .then((user) => {
        setCurrentUser(user)
      })
      .catch((err: unknown) => {
        console.error('Failed to load current user:', err)
      })
      .finally(() => {
        setReady(true)
      })
  }, [])

  const normalizedId = currentPath.replace(/^\//, '')
  const isLoginPage = normalizedId === 'login'
  const isRegisterPage = normalizedId === 'register'
  const isSkillsPage = normalizedId === 'skills'
  const isPlazaPage = normalizedId === 'plaza'
  const isAdminPage = normalizedId === 'admin'

  useEffect(() => {
    if (!currentUser) return
    if (isLoginPage || isRegisterPage) {
      setCurrentPath('/')
    }
  }, [currentUser, isLoginPage, isRegisterPage, setCurrentPath])

  const shellClassName = useMemo(() => {
    if (isSkillsPage || isPlazaPage || isAdminPage) {
      return 'max-w-7xl flex-1 h-full overflow-hidden'
    }
    return 'max-w-4xl overflow-hidden basis-[100svh] md:basis-[100vh] has-[.stick-to-bottom:empty]:overflow-visible has-[.stick-to-bottom:empty]:basis-0 transition-[flex-basis] duration-200'
  }, [isAdminPage, isPlazaPage, isSkillsPage])

  if (!ready) {
    return <AuthSplash />
  }

  if (!currentUser) {
    return (
      <QueryClientProvider client={queryClient}>
        <ThemeProvider defaultTheme="light" storageKey="skill-chat-theme">
          <AuthPage
            mode={isRegisterPage ? 'register' : 'login'}
            onModeChange={(mode) => setCurrentPath(mode === 'register' ? '/register' : '/login')}
            onAuthenticated={(user) => {
              setCurrentUser(user)
              setCurrentPath('/')
            }}
          />
          <Toaster richColors />
        </ThemeProvider>
      </QueryClientProvider>
    )
  }

  const handleLogout = async () => {
    try {
      await logout()
    } catch (error) {
      console.error('Failed to logout:', error)
    } finally {
      setCurrentUser(null)
      setCurrentPath('/login')
    }
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="light" storageKey="skill-chat-theme">
        <SidebarProvider defaultOpen>
          <AppSidebar currentUser={currentUser} onLogout={handleLogout} />

          <div className="relative flex h-svh flex-1 flex-col justify-center overflow-hidden md:h-screen">
            <div className="absolute inset-x-0 top-0 z-10 flex items-center gap-2 border-b bg-background/95 px-3 py-2 backdrop-blur md:hidden">
              <SidebarTrigger />
              <span className="text-sm font-medium truncate">Skill Chat</span>
            </div>
            <div className={cn('relative mx-auto flex w-full flex-col box-border pt-12 md:pt-0', shellClassName)}>
              {isSkillsPage ? (
                <SkillManagerPage />
              ) : isPlazaPage ? (
                <PlazaPage />
              ) : isAdminPage ? (
                currentUser.isAdmin ? (
                  <AdminPage />
                ) : (
                  <div className="flex h-full items-center justify-center bg-[#f8f7f3] p-8">
                    <Card className="max-w-md rounded-[1.75rem] border-slate-200 bg-white shadow-sm">
                      <CardContent className="space-y-3 py-10 text-center">
                        <div className="text-xl font-semibold text-slate-950">你没有访问管理后台的权限</div>
                        <div className="text-sm leading-6 text-slate-500">请使用管理员账户登录，或返回普通工作区继续使用。</div>
                      </CardContent>
                    </Card>
                  </div>
                )
              ) : (
                <Chat />
              )}
            </div>
          </div>
        </SidebarProvider>
      </ThemeProvider>
      <Toaster richColors />
    </QueryClientProvider>
  )
}
