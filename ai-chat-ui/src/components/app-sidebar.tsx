import { BookOpen, CirclePlus, LogOut, MessageCircle, Shield, Sparkles, Store, Trash2 } from 'lucide-react'
import type React from 'react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useConversationIdFromUrl } from '@/hooks/useConversationIdFromUrl'
import { cn } from '@/lib/utils'
import type { ConversationEntry, UserProfile } from '@/types'
import { getConversations, deleteConversation as deleteConv } from '@/lib/chat-db'
import { stripBasePath, withBasePath } from '@/lib/base-path'
import { ModeToggle } from './mode-toggle'
import { GuideDialog } from './guide-dialog'

function useConversations(): ConversationEntry[] {
  const [conversations, setConversations] = useState<ConversationEntry[]>([])

  useEffect(() => {
    const loadConversations = () => {
      getConversations()
        .then(setConversations)
        .catch((err: unknown) => {
          console.error('Failed to load conversations:', err)
        })
    }

    loadConversations()

    window.addEventListener('conversations-changed', loadConversations)

    return () => {
      window.removeEventListener('conversations-changed', loadConversations)
    }
  }, [])

  return conversations
}

function doLocalNavigation(e: React.MouseEvent) {
  if (e.button !== 0 || e.metaKey || e.ctrlKey) {
    return
  }
  const path = new URL((e.currentTarget as HTMLAnchorElement).href).pathname
  window.history.pushState({}, '', path)
  window.dispatchEvent(new Event('history-state-changed'))
  e.preventDefault()
}

function deleteConversation(conversationId: string) {
  return deleteConv(conversationId).then(() => {
    window.dispatchEvent(new Event('conversations-changed'))

    const currentPath = stripBasePath(window.location.pathname)
    if (currentPath === conversationId) {
      window.history.pushState({}, '', withBasePath('/'))
      window.dispatchEvent(new Event('history-state-changed'))
    }
  })
}

export function AppSidebar({ currentUser, onLogout }: { currentUser: UserProfile; onLogout: () => void }) {
  const conversations = useConversations()
  const [conversationId] = useConversationIdFromUrl()
  const normalizedId = conversationId.replace(/^\//, '')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState<ConversationEntry | null>(null)

  const navigationItems = useMemo(
    () => [
      {
        href: withBasePath('skills'),
        label: '我的技能',
        icon: Sparkles,
        active: normalizedId === 'skills',
      },
      {
        href: withBasePath('plaza'),
        label: '技能广场',
        icon: Store,
        active: normalizedId === 'plaza',
      },
      ...(currentUser.isAdmin
        ? [
            {
              href: withBasePath('admin'),
              label: '管理控制台',
              icon: Shield,
              active: normalizedId === 'admin',
            },
          ]
        : []),
      {
        href: withBasePath('/'),
        label: '新建对话',
        icon: CirclePlus,
        active: normalizedId === '',
      },
    ],
    [currentUser.isAdmin, normalizedId],
  )

  const handleDeleteClick = (e: React.MouseEvent, conversation: ConversationEntry) => {
    e.preventDefault()
    e.stopPropagation()
    setConversationToDelete(conversation)
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = () => {
    if (conversationToDelete) {
      deleteConversation(conversationToDelete.id)
        .then(() => {
          setDeleteDialogOpen(false)
          setConversationToDelete(null)
          toast.success('会话已删除')
        })
        .catch((err: unknown) => {
          console.error('Failed to delete conversation:', err)
          toast.error('删除会话失败')
        })
    }
  }

  return (
    <TooltipProvider>
      <Sidebar collapsible="icon" className="border-r border-border/40">
        <SidebarHeader className="flex-row items-center justify-between gap-2 py-4 px-4 group-data-[state=collapsed]:justify-center group-data-[state=collapsed]:px-0">
          <div className="flex min-w-0 items-center group-data-[state=collapsed]:hidden">
            <h1 className="truncate whitespace-nowrap text-lg font-semibold tracking-tight text-foreground lowercase">
              skillchat
            </h1>
          </div>
          <SidebarTrigger className="shrink-0 text-muted-foreground hover:text-foreground" />
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarMenu className="mb-4">
              {navigationItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    tooltip={item.label}
                    className={cn('font-medium transition-colors hover:bg-muted/50', {
                      'bg-muted text-foreground': item.active,
                      'text-muted-foreground': !item.active,
                    })}
                  >
                    <a href={item.href} onClick={doLocalNavigation}>
                      <item.icon className={cn('opacity-70', { 'opacity-100': item.active })} />
                      <span>{item.label}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>

            <SidebarGroupContent>
              <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/50 group-data-[state=collapsed]:hidden">
                历史对话
              </div>
              <SidebarMenu>
                {conversations.map((conversation, index) => (
                  <SidebarMenuItem key={index} className="group/sidebar-menu-item">
                    <div className="relative flex items-center gap-1 h-auto">
                      <SidebarMenuButton
                        asChild
                        tooltip={conversation.firstMessage}
                        className="flex-1 rounded-lg transition-colors hover:bg-muted/50"
                      >
                        <a
                          href={withBasePath(conversation.id)}
                          onClick={doLocalNavigation}
                          className={cn('h-auto flex items-start py-2 px-3 gap-3', {
                            'bg-muted/80 text-foreground pointer-events-none': conversation.id === conversationId,
                            'text-muted-foreground': conversation.id !== conversationId,
                          })}
                        >
                          <MessageCircle
                            className={cn('size-3.5 mt-0.5 shrink-0 opacity-50', {
                              'opacity-100': conversation.id === conversationId,
                            })}
                          />
                          <span className="flex flex-col items-start min-w-0">
                            <span className="truncate w-full font-medium leading-none text-sm mb-1.5">
                              {conversation.firstMessage || '未命名对话'}
                            </span>
                            <span className="text-[10px] opacity-60 leading-none">
                              {new Date(conversation.timestamp).toLocaleDateString()}
                            </span>
                          </span>
                        </a>
                      </SidebarMenuButton>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 opacity-0 group-hover/sidebar-menu-item:opacity-100 transition-opacity group-data-[state=collapsed]:hidden absolute right-1 self-center text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            onClick={(e) => {
                              handleDeleteClick(e, conversation)
                            }}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>删除会话</TooltipContent>
                      </Tooltip>
                    </div>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter className="p-4">
          <div className="group-data-[state=collapsed]:hidden mb-4">
            <SidebarMenu>
              <SidebarMenuItem>
                <GuideDialog>
                  <SidebarMenuButton
                    tooltip="功能指南"
                    className="font-medium transition-colors hover:bg-muted/50 text-muted-foreground"
                  >
                    <BookOpen className="opacity-70" />
                    <span>功能指南</span>
                  </SidebarMenuButton>
                </GuideDialog>
              </SidebarMenuItem>
            </SidebarMenu>
          </div>
          <div className="flex items-center justify-between group-data-[state=collapsed]:hidden mb-4">
            <div className="flex flex-col min-w-0">
              <span className="truncate text-sm font-semibold text-foreground leading-tight">{currentUser.email}</span>
              <span className="text-xs text-muted-foreground mt-0.5">{currentUser.isAdmin ? 'Admin' : 'Member'}</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <ModeToggle />
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={onLogout}
              >
                <LogOut className="size-4" />
              </Button>
            </div>
          </div>
          {/* Fallback for collapsed state */}
          <div className="hidden group-data-[state=collapsed]:flex flex-col gap-2 items-center">
            <ModeToggle />
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={onLogout}
            >
              <LogOut className="size-4" />
            </Button>
          </div>
        </SidebarFooter>

        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent
            className="sm:max-w-md"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleConfirmDelete()
              }
            }}
          >
            <DialogHeader>
              <DialogTitle>删除会话？</DialogTitle>
              <DialogDescription>删除后无法恢复，该会话的消息也会一并删除。</DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0 mt-4">
              <Button variant="ghost" onClick={() => setDeleteDialogOpen(false)}>
                取消
              </Button>
              <Button variant="destructive" onClick={handleConfirmDelete} autoFocus className="rounded-full px-6">
                确认删除
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Sidebar>
    </TooltipProvider>
  )
}
