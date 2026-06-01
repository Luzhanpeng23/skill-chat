import { Conversation, ConversationContent, ConversationScrollButton } from '@/components/ai-elements/conversation'
import { Loader } from '@/components/ai-elements/loader'
import {
  PromptInput,
  PromptInputButton,
  PromptInputModelSelect,
  PromptInputModelSelectContent,
  PromptInputModelSelectItem,
  PromptInputModelSelectTrigger,
  PromptInputModelSelectValue,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
} from '@/components/ai-elements/prompt-input'
import { Source, Sources, SourcesContent, SourcesTrigger } from '@/components/ai-elements/sources'
import { EditMessageDialog } from '@/components/edit-message-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Switch } from '@/components/ui/switch'
import { useChat } from '@ai-sdk/react'
import { Check, Package, Settings2Icon } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from 'react'
import { toast } from 'sonner'
import { cn, resolveSkillPackDisplayTitle } from '@/lib/utils'

import { useQuery } from '@tanstack/react-query'
import { useThrottle } from '@uidotdev/usehooks'
import { nanoid } from 'nanoid'
import { useConversationIdFromUrl } from './hooks/useConversationIdFromUrl'
import { Part } from './Part'
import type { ConversationEntry } from './types'
import { getToolIcon } from '@/lib/tool-icons'
import { getConversations, getMessages, saveMessages, saveConversation } from '@/lib/chat-db'
import { stripBasePath } from '@/lib/base-path'
import { listSkillPacks, listSkillTasks } from '@/lib/skills'

interface ModelConfig {
  id: string
  name: string
  builtinTools: string[]
}

interface BuiltinTool {
  name: string
  id: string
}

interface RemoteConfig {
  models: ModelConfig[]
  builtinTools: BuiltinTool[]
}

const PENDING_SKILL_PACK_KEY = 'pending-skill-pack-id'

async function getModels() {
  const res = await fetch('/api/configure')
  return (await res.json()) as RemoteConfig
}

function normalizeSkillPackIds(value: string[] | undefined): string[] {
  return value?.filter((item, index, items) => item && items.indexOf(item) === index) ?? []
}

function getPendingSkillPackIds(): string[] {
  const value = window.sessionStorage.getItem(PENDING_SKILL_PACK_KEY)
  if (!value) return []

  try {
    const parsed = JSON.parse(value) as unknown
    if (Array.isArray(parsed)) {
      return normalizeSkillPackIds(parsed.filter((item): item is string => typeof item === 'string'))
    }
  } catch {
    return normalizeSkillPackIds([value])
  }

  return []
}

function getConversationSkillPackIds(conversationEntry: ConversationEntry | null): string[] {
  if (!conversationEntry) return []
  if (Array.isArray(conversationEntry.skillPackIds)) {
    return normalizeSkillPackIds(conversationEntry.skillPackIds)
  }
  return conversationEntry.skillPackId ? [conversationEntry.skillPackId] : []
}

const Chat = () => {
  const [input, setInput] = useState('')
  const [model, setModel] = useState('')
  const [enabledTools, setEnabledTools] = useState<string[]>([])
  const { messages, sendMessage, status, setMessages, regenerate, error } = useChat()
  const throttledMessages = useThrottle(messages, 500)
  const [conversationId, setConversationId] = useConversationIdFromUrl()
  const [conversationEntry, setConversationEntry] = useState<ConversationEntry | null>(null)
  const [hydratedConversationId, setHydratedConversationId] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const editDraftsRef = useRef(new Map<string, string>())
  const [pendingEdit, setPendingEdit] = useState<{ messageId: string; text: string } | null>(null)
  const pendingSendRef = useRef<{
    text: string
    model: string
    builtinTools: string[]
    skillPackIds?: string[]
  } | null>(null)
  const [sendTrigger, setSendTrigger] = useState(0)
  const [pendingPackIds, setPendingPackIds] = useState<string[]>(getPendingSkillPackIds())

  const configQuery = useQuery({
    queryFn: getModels,
    queryKey: ['models'],
  })

  const packsQuery = useQuery({
    queryFn: listSkillPacks,
    queryKey: ['skill-packs'],
  })

  const tasksQuery = useQuery({
    queryFn: listSkillTasks,
    queryKey: ['skill-tasks'],
  })

  const activeSkillPackIds = conversationEntry ? getConversationSkillPackIds(conversationEntry) : pendingPackIds
  const activeSkillPacks =
    packsQuery.data?.filter((pack) => activeSkillPackIds.includes(pack.id)) ?? []
  const activeSkillPackTitles = activeSkillPacks.map((pack) => {
    const relatedTask = tasksQuery.data?.find((task) => task.id === pack.taskId)
    return resolveSkillPackDisplayTitle(pack, relatedTask)
  })
  const activeSkillPackLabel =
    activeSkillPackTitles.length === 0
      ? null
      : activeSkillPackTitles.length === 1
        ? activeSkillPackTitles[0]
        : `Loaded ${activeSkillPackTitles.length} Books`

  const handleToggleSkillPack = useCallback(
    (skillPackId: string) => {
      const nextSkillPackIds = activeSkillPackIds.includes(skillPackId)
        ? activeSkillPackIds.filter((id) => id !== skillPackId)
        : [...activeSkillPackIds, skillPackId]

      if (!conversationEntry) {
        if (nextSkillPackIds.length > 0) {
          window.sessionStorage.setItem(PENDING_SKILL_PACK_KEY, JSON.stringify(nextSkillPackIds))
        } else {
          window.sessionStorage.removeItem(PENDING_SKILL_PACK_KEY)
        }
        setPendingPackIds(nextSkillPackIds)
        window.dispatchEvent(new Event('skill-packs-changed'))
      } else {
        const nextConversation: ConversationEntry = {
          ...conversationEntry,
          skillPackIds: nextSkillPackIds.length > 0 ? nextSkillPackIds : undefined,
          skillPackId: undefined,
        }
        setConversationEntry(nextConversation)
        saveConversation(nextConversation)
          .then(() => {
            window.dispatchEvent(new Event('conversations-changed'))
            window.dispatchEvent(new Event('skill-packs-changed'))
          })
          .catch((error: unknown) => {
            console.error('Failed to save conversation skill packs:', error)
            toast.error('Failed to update conversation skill packs')
          })
      }
    },
    [activeSkillPackIds, conversationEntry],
  )

  const handleClearSkillPacks = useCallback(() => {
    if (!conversationEntry) {
      window.sessionStorage.removeItem(PENDING_SKILL_PACK_KEY)
      setPendingPackIds([])
      window.dispatchEvent(new Event('skill-packs-changed'))
      return
    }

    const nextConversation: ConversationEntry = {
      ...conversationEntry,
      skillPackIds: undefined,
      skillPackId: undefined,
    }
    setConversationEntry(nextConversation)
    saveConversation(nextConversation)
      .then(() => {
        window.dispatchEvent(new Event('conversations-changed'))
        window.dispatchEvent(new Event('skill-packs-changed'))
      })
      .catch((error: unknown) => {
        console.error('Failed to clear conversation skill packs:', error)
        toast.error('Failed to clear conversation skill packs')
      })
  }, [conversationEntry])

  useEffect(() => {
    if (configQuery.data) {
      setModel(configQuery.data.models[0].id)
    }
  }, [configQuery.data])

  useEffect(() => {
    let cancelled = false

    setEditingMessageId(null)
    setHydratedConversationId(null)

    if (conversationId === '/') {
      setConversationEntry(null)
      setMessages([])
      setHydratedConversationId('/')
      textareaRef.current?.focus()
      return () => {
        cancelled = true
      }
    }

    setMessages([])

    getConversationEntry(conversationId)
      .then((entry) => {
        if (!cancelled) {
          setConversationEntry(entry)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          console.error('Failed to load conversation entry:', err)
        }
      })

    getMessages(conversationId)
      .then((storedMessages) => {
        if (cancelled) return

        setMessages(storedMessages ?? [])
        setHydratedConversationId(conversationId)
        if (pendingSendRef.current) {
          setSendTrigger((n) => n + 1)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          console.error('Failed to load messages:', err)
          setHydratedConversationId(conversationId)
        }
      })

    textareaRef.current?.focus()
    return () => {
      cancelled = true
    }
  }, [conversationId, setMessages])

  useEffect(() => {
    const reloadConversation = () => {
      setPendingPackIds(getPendingSkillPackIds())
      if (conversationId === '/') {
        setConversationEntry(null)
        return
      }

      getConversationEntry(conversationId)
        .then(setConversationEntry)
        .catch((err: unknown) => {
          console.error('Failed to refresh conversation entry:', err)
        })
    }

    window.addEventListener('conversations-changed', reloadConversation)
    window.addEventListener('skill-packs-changed', reloadConversation)
    return () => {
      window.removeEventListener('conversations-changed', reloadConversation)
      window.removeEventListener('skill-packs-changed', reloadConversation)
    }
  }, [conversationId])

  const handleSubmit = (e: SyntheticEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text) return

    if (stripBasePath(window.location.pathname) === '/') {
      const newConversationId = `/${nanoid()}`
      pendingSendRef.current = {
        text,
        model,
        builtinTools: enabledTools,
        skillPackIds: activeSkillPackIds,
      }
      setConversationId(newConversationId)
      saveConversationEntry(newConversationId, text, undefined, activeSkillPackIds)
      if (activeSkillPackIds.length > 0) {
        window.sessionStorage.removeItem(PENDING_SKILL_PACK_KEY)
        setPendingPackIds([])
        window.dispatchEvent(new Event('skill-packs-changed'))
      }
      setInput('')
      return
    }

    sendMessage(
      { text },
      {
        body: { model, builtinTools: enabledTools, skillPackIds: activeSkillPackIds },
      },
    ).catch((error: unknown) => {
      console.error('Error sending message:', error)
    })
    setInput('')
  }

  useEffect(() => {
    if (!pendingSendRef.current) return
    const pending = pendingSendRef.current
    pendingSendRef.current = null
    sendMessage(
      { text: pending.text },
      { body: { model: pending.model, builtinTools: pending.builtinTools, skillPackIds: pending.skillPackIds } },
    ).catch((error: unknown) => {
      console.error('Error sending deferred message:', error)
    })
  }, [sendTrigger])

  useEffect(() => {
    if (conversationId === '/' || hydratedConversationId !== conversationId) {
      return
    }

    saveMessages(conversationId, throttledMessages).catch((err: unknown) => {
      console.error('Failed to save messages:', err)
    })
  }, [throttledMessages, conversationId, hydratedConversationId])

  const handleStartEdit = useCallback((messageId: string) => {
    setEditingMessageId(messageId)
  }, [])

  const handleCancelEdit = useCallback((messageId: string, draft: string) => {
    editDraftsRef.current.set(messageId, draft)
    setEditingMessageId(null)
  }, [])

  const handleSubmitEdit = useCallback(
    (messageId: string, newText: string) => {
      const original = messages.find((m) => m.id === messageId)
      const originalText = original?.parts.find((p) => p.type === 'text')
      const unchanged = originalText && 'text' in originalText && originalText.text === newText
      editDraftsRef.current.delete(messageId)
      setEditingMessageId(null)
      if (unchanged) return
      setPendingEdit({ messageId, text: newText })
    },
    [messages],
  )

  const handleModify = useCallback(() => {
    if (!pendingEdit) return
    const messageIndex = messages.findIndex((m) => m.id === pendingEdit.messageId)
    if (messageIndex === -1) return
    pendingSendRef.current = {
      text: pendingEdit.text,
      model,
      builtinTools: enabledTools,
      skillPackIds: getConversationSkillPackIds(conversationEntry),
    }
    setMessages(messages.slice(0, messageIndex))
    setPendingEdit(null)
    setTimeout(() => {
      setSendTrigger((n) => n + 1)
    }, 0)
  }, [pendingEdit, messages, setMessages, model, enabledTools, conversationEntry])

  const handleFork = useCallback(() => {
    if (!pendingEdit) return
    if (conversationId === '/') return
    const messageIndex = messages.findIndex((m) => m.id === pendingEdit.messageId)
    if (messageIndex === -1) return
    const newConversationId = `/${nanoid()}`
    const forkedMessages = messages.slice(0, messageIndex)
    const firstUserMessage = forkedMessages.find((m) => m.role === 'user')
    const firstMessageText = firstUserMessage?.parts.find((p) => p.type === 'text')
    const originalText = firstMessageText && 'text' in firstMessageText ? firstMessageText.text : undefined
    const firstMessage = originalText ?? pendingEdit.text
    const conversationSkillPackIds = getConversationSkillPackIds(conversationEntry)
    saveConversationEntry(newConversationId, firstMessage, { conversationId, messageIndex }, conversationSkillPackIds)
    saveMessages(newConversationId, forkedMessages).catch((err: unknown) => {
      console.error('Failed to save forked messages:', err)
    })
    pendingSendRef.current = {
      text: pendingEdit.text,
      model,
      builtinTools: enabledTools,
      skillPackIds: conversationSkillPackIds,
    }
    setPendingEdit(null)
    setConversationId(newConversationId)
  }, [pendingEdit, messages, conversationId, model, enabledTools, setConversationId, conversationEntry])

  const handleNavigateToFork = useCallback(
    (targetConversationId: string) => {
      setConversationId(targetConversationId)
    },
    [setConversationId],
  )

  function regen(messageId: string) {
    regenerate({ messageId }).catch((error: unknown) => {
      console.error('Error regenerating message:', error)
    })
  }

  const availableTools = useMemo(() => {
    const enabledToolIds = configQuery.data?.models.find((entry) => entry.id === model)?.builtinTools ?? []
    return configQuery.data?.builtinTools.filter((tool) => enabledToolIds.includes(tool.id)) ?? []
  }, [configQuery.data, model])

  // 新建对话：空消息时显示居中布局
  if (messages.length === 0) {
    return (
      <>
        <div className="flex flex-1 flex-col items-center justify-center px-6 pb-8">
          <h1 className="text-2xl font-light tracking-wide text-foreground/70 mb-6">有什么想聊的？一本书、一个想法都可以</h1>
          <div className="w-full max-w-2xl">
            <PromptInput onSubmit={handleSubmit}>
              <PromptInputTextarea
                ref={textareaRef}
                onChange={(e) => setInput(e.target.value)}
                value={input}
                placeholder="输入消息开始对话..."
                autoFocus={true}
              />
              <PromptInputToolbar>
                <PromptInputTools>
                  {availableTools.length > 0 && (
                    <DropdownMenu>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <DropdownMenuTrigger asChild>
                            <PromptInputButton variant="outline">
                              <Settings2Icon className="size-4" />
                            </PromptInputButton>
                          </DropdownMenuTrigger>
                        </TooltipTrigger>
                        <TooltipContent>Tools</TooltipContent>
                      </Tooltip>
                      <DropdownMenuContent align="start">
                        {availableTools.map((tool) => (
                          <div
                            key={tool.id}
                            className="flex items-center justify-between gap-3 px-2 py-1.5 cursor-pointer hover:bg-accent rounded-sm"
                            onClick={() => {
                              setEnabledTools((prev) =>
                                prev.includes(tool.id) ? prev.filter((id) => id !== tool.id) : [...prev, tool.id],
                              )
                            }}
                          >
                            <div className="flex items-center gap-2">
                              {getToolIcon(tool.id)}
                              <span className="text-sm">{tool.name}</span>
                            </div>
                            <Switch
                              checked={enabledTools.includes(tool.id)}
                              onCheckedChange={(checked) => {
                                setEnabledTools((prev) =>
                                  checked ? [...prev, tool.id] : prev.filter((id) => id !== tool.id),
                                )
                              }}
                              onClick={(e) => e.stopPropagation()}
                            />
                          </div>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                  {configQuery.data && model && (
                    <PromptInputModelSelect
                      onValueChange={(value) => setModel(value)}
                      value={model}
                    >
                      <PromptInputModelSelectTrigger>
                        <PromptInputModelSelectValue />
                      </PromptInputModelSelectTrigger>
                      <PromptInputModelSelectContent>
                        {(configQuery.data as { models: { id: string; name: string }[] }).models.map((m) => (
                          <PromptInputModelSelectItem key={m.id} value={m.id}>
                            {m.name}
                          </PromptInputModelSelectItem>
                        ))}
                      </PromptInputModelSelectContent>
                    </PromptInputModelSelect>
                  )}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <PromptInputButton
                        variant="ghost"
                        className={cn(
                          'max-w-50 overflow-hidden',
                          activeSkillPackIds.length > 0 ? 'text-foreground' : 'text-muted-foreground',
                        )}
                      >
                        <Package className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{activeSkillPackLabel || 'Load Skill Pack...'}</span>
                      </PromptInputButton>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="start"
                      className="w-75 max-h-80 overflow-y-auto rounded-sm border-border shadow-sm"
                    >
                      {activeSkillPackIds.length > 0 && (
                        <>
                          <DropdownMenuItem
                            onSelect={(event) => event.preventDefault()}
                            onClick={handleClearSkillPacks}
                            className="cursor-pointer text-destructive focus:bg-destructive/10 focus:text-destructive rounded-sm"
                          >
                            Unload Selected Packs
                          </DropdownMenuItem>
                          <div className="my-1 h-px bg-border/50" />
                        </>
                      )}
                      {packsQuery.data?.length === 0 ? (
                        <div className="px-3 py-6 text-center">
                          <Package className="h-8 w-8 mx-auto text-muted-foreground/30 mb-2" />
                          <p className="text-xs text-muted-foreground">还没有技能包</p>
                          <p className="text-xs text-muted-foreground/60 mt-1">前往「技能广场」添加公开技能包后即可在此使用</p>
                        </div>
                      ) : (
                        packsQuery.data?.map((pack) => {
                          const relatedTask = tasksQuery.data?.find((task) => task.id === pack.taskId)
                          const packTitle = resolveSkillPackDisplayTitle(pack, relatedTask)
                          const isActive = activeSkillPackIds.includes(pack.id)

                          return (
                            <DropdownMenuItem
                              key={pack.id}
                              onSelect={(event) => event.preventDefault()}
                              onClick={() => handleToggleSkillPack(pack.id)}
                              className={cn(
                                'cursor-pointer flex flex-col items-start gap-1 py-2 px-3 rounded-sm',
                                isActive && 'bg-muted/50',
                              )}
                            >
                              <div className="flex items-center gap-2 w-full min-w-0">
                                {isActive ? (
                                  <Check className="h-4 w-4 shrink-0 text-foreground" />
                                ) : (
                                  <Package className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                                )}
                                <span
                                  className={cn(
                                    'truncate text-sm',
                                    isActive ? 'font-medium text-foreground' : 'text-muted-foreground',
                                  )}
                                >
                                  {packTitle}
                                </span>
                              </div>
                              {pack.description && (
                                <p className="text-xs text-muted-foreground/60 truncate w-full pl-6">
                                  {pack.description}
                                </p>
                              )}
                            </DropdownMenuItem>
                          )
                        })
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </PromptInputTools>
                <PromptInputSubmit disabled={!input} status={status} />
              </PromptInputToolbar>
            </PromptInput>
          </div>
        </div>

        <EditMessageDialog
          open={pendingEdit !== null}
          onOpenChange={(open) => {
            if (!open) setPendingEdit(null)
          }}
          onModify={handleModify}
          onFork={handleFork}
        />
      </>
    )
  }

  return (
    <>
      <Conversation className="h-full">
        <ConversationContent>
          {messages.map((message, messageIndex) => (
            <div key={message.id} className={message.role === 'user' ? 'group/user-message' : undefined}>
              {message.role === 'assistant' &&
                message.parts.filter((part) => part.type === 'source-url').length > 0 && (
                  <Sources>
                    <SourcesTrigger count={message.parts.filter((part) => part.type === 'source-url').length} />
                    {message.parts
                      .filter((part) => part.type === 'source-url')
                      .map((part, i) => (
                        <SourcesContent key={`${message.id}-${i}`}>
                          <Source key={`${message.id}-${i}`} href={part.url} title={part.url} />
                        </SourcesContent>
                      ))}
                  </Sources>
                )}
              {message.parts.map((part, i) => (
                <Part
                  key={`${message.id}-${i}`}
                  part={part}
                  message={message}
                  status={status}
                  index={i}
                  regen={regen}
                  lastMessage={message.id === messages.at(-1)?.id}
                  isEditing={editingMessageId === message.id}
                  editDraft={editDraftsRef.current.get(message.id)}
                  onStartEdit={handleStartEdit}
                  onCancelEdit={handleCancelEdit}
                  onSubmitEdit={handleSubmitEdit}
                  conversationId={conversationId}
                  messageIndex={messageIndex}
                  onNavigateToFork={handleNavigateToFork}
                />
              ))}
            </div>
          ))}
          {status === 'submitted' && <Loader />}
          {status === 'error' && error && (
            <div className="px-4 py-3 mx-4 my-2 bg-destructive/10 border border-destructive/20 rounded-md text-destructive text-sm">
              <strong>Error:</strong> {error.message}
            </div>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="sticky bottom-0 p-3">
        <PromptInput onSubmit={handleSubmit}>
          <PromptInputTextarea
            ref={textareaRef}
            onChange={(e) => {
              setInput(e.target.value)
            }}
            value={input}
            autoFocus={true}
          />
          <PromptInputToolbar>
            <PromptInputTools>
              {availableTools.length > 0 && (
                <DropdownMenu>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <PromptInputButton variant="outline">
                          <Settings2Icon className="size-4" />
                        </PromptInputButton>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <TooltipContent>Tools</TooltipContent>
                  </Tooltip>
                  <DropdownMenuContent align="start">
                    {availableTools.map((tool) => (
                      <div
                        key={tool.id}
                        className="flex items-center justify-between gap-3 px-2 py-1.5 cursor-pointer hover:bg-accent rounded-sm"
                        onClick={() => {
                          setEnabledTools((prev) =>
                            prev.includes(tool.id) ? prev.filter((id) => id !== tool.id) : [...prev, tool.id],
                          )
                        }}
                      >
                        <div className="flex items-center gap-2">
                          {getToolIcon(tool.id)}
                          <span className="text-sm">{tool.name}</span>
                        </div>
                        <Switch
                          checked={enabledTools.includes(tool.id)}
                          onCheckedChange={(checked) => {
                            setEnabledTools((prev) =>
                              checked ? [...prev, tool.id] : prev.filter((id) => id !== tool.id),
                            )
                          }}
                          onClick={(e) => {
                            e.stopPropagation()
                          }}
                        />
                      </div>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
              {configQuery.data && model && (
                <PromptInputModelSelect
                  onValueChange={(value) => {
                    setModel(value)
                  }}
                  value={model}
                >
                  <PromptInputModelSelectTrigger>
                    <PromptInputModelSelectValue />
                  </PromptInputModelSelectTrigger>
                  <PromptInputModelSelectContent>
                    {(configQuery.data as { models: { id: string; name: string }[] }).models.map((model) => (
                      <PromptInputModelSelectItem key={model.id} value={model.id}>
                        {model.name}
                      </PromptInputModelSelectItem>
                    ))}
                  </PromptInputModelSelectContent>
                </PromptInputModelSelect>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <PromptInputButton
                    variant="ghost"
                    className={cn(
                      'max-w-50 overflow-hidden',
                      activeSkillPackIds.length > 0 ? 'text-foreground' : 'text-muted-foreground',
                    )}
                  >
                    <Package className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{activeSkillPackLabel || 'Load Skill Pack...'}</span>
                  </PromptInputButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  className="w-75 max-h-80 overflow-y-auto rounded-sm border-border shadow-sm"
                >
                  {activeSkillPackIds.length > 0 && (
                    <>
                      <DropdownMenuItem
                        onSelect={(event) => event.preventDefault()}
                        onClick={handleClearSkillPacks}
                        className="cursor-pointer text-destructive focus:bg-destructive/10 focus:text-destructive rounded-sm"
                      >
                        Unload Selected Packs
                      </DropdownMenuItem>
                      <div className="my-1 h-px bg-border/50" />
                    </>
                  )}
                  {packsQuery.data?.map((pack) => {
                    const relatedTask = tasksQuery.data?.find((task) => task.id === pack.taskId)
                    const packTitle = resolveSkillPackDisplayTitle(pack, relatedTask)
                    const isActive = activeSkillPackIds.includes(pack.id)

                    return (
                      <DropdownMenuItem
                        key={pack.id}
                        onSelect={(event) => event.preventDefault()}
                        onClick={() => handleToggleSkillPack(pack.id)}
                        className={cn(
                          'cursor-pointer flex flex-col items-start gap-1 py-2 px-3 rounded-sm',
                          isActive && 'bg-muted/50',
                        )}
                      >
                        <div className="flex items-center gap-2 w-full min-w-0">
                          {isActive ? (
                            <Check className="h-4 w-4 shrink-0 text-foreground" />
                          ) : (
                            <Package className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                          )}
                          <span
                            className={cn(
                              'truncate text-sm',
                              isActive ? 'font-medium text-foreground' : 'text-muted-foreground',
                            )}
                          >
                            {packTitle}
                          </span>
                        </div>
                      </DropdownMenuItem>
                    )
                  })}
                  {packsQuery.data?.length === 0 && (
                    <div className="p-4 text-center text-xs text-muted-foreground space-y-1">
                      <div>暂无技能包</div>
                      <div className="text-muted-foreground/60">前往「技能广场」添加公开技能包后即可在此使用</div>
                    </div>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </PromptInputTools>
            <PromptInputSubmit disabled={!input} status={status} />
          </PromptInputToolbar>
        </PromptInput>
      </div>

      <EditMessageDialog
        open={pendingEdit !== null}
        onOpenChange={(open) => {
          if (!open) setPendingEdit(null)
        }}
        onModify={handleModify}
        onFork={handleFork}
      />
    </>
  )
}

export default Chat

const MAX_FIRST_MESSAGE_LENGTH = 30

async function getConversationEntry(conversationId: string): Promise<ConversationEntry | null> {
  const conversations = await getConversations()
  return conversations.find((conversation) => conversation.id === conversationId) ?? null
}

function saveConversationEntry(
  newConversationId: string,
  firstMessage: string,
  forkOf?: ConversationEntry['forkOf'],
  skillPackIds?: string[],
) {
  const trimmedFirstMessage =
    firstMessage.length > MAX_FIRST_MESSAGE_LENGTH
      ? firstMessage.slice(0, MAX_FIRST_MESSAGE_LENGTH) + '...'
      : firstMessage

  const entry: ConversationEntry = {
    id: newConversationId,
    firstMessage: trimmedFirstMessage,
    timestamp: Date.now(),
  }
  if (forkOf) {
    entry.forkOf = forkOf
  }
  if (skillPackIds && skillPackIds.length > 0) {
    entry.skillPackIds = normalizeSkillPackIds(skillPackIds)
  }

  saveConversation(entry)
    .then(() => window.dispatchEvent(new Event('conversations-changed')))
    .catch((err: unknown) => {
      console.error('Failed to save conversation:', err)
    })
}
