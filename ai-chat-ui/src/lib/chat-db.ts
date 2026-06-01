import type { ConversationEntry } from '@/types'
import type { UIMessage } from 'ai'
import { toast } from 'sonner'

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  return (await response.json()) as T
}

export async function getConversations(): Promise<ConversationEntry[]> {
  const conversations = await requestJson<ConversationEntry[]>('/api/conversations', {
    method: 'GET',
  })
  conversations.sort((a, b) => b.timestamp - a.timestamp)
  return conversations
}

export async function saveConversation(conversation: ConversationEntry): Promise<void> {
  try {
    await requestJson<{ ok: boolean }>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify(conversation),
    })
  } catch (error) {
    toast.error('Failed to save conversation to server.')
    throw error
  }
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await requestJson<{ ok: boolean }>(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
  })
}

export async function getMessages(conversationId: string): Promise<UIMessage[] | null> {
  const result = await requestJson<{ messages: UIMessage[] | null }>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: 'GET',
    },
  )
  return result.messages ?? null
}

export async function saveMessages(conversationId: string, messages: UIMessage[]): Promise<void> {
  try {
    await requestJson<{ ok: boolean }>(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ messages }),
    })
  } catch (error) {
    toast.error('Failed to save messages to server.')
    throw error
  }
}

export async function migrateFromLocalStorage(): Promise<boolean> {
  const migrationKey = 'server-storage-migration-complete'
  if (localStorage.getItem(migrationKey)) {
    return false
  }

  const conversationsJson = localStorage.getItem('conversationIds')
  if (!conversationsJson) {
    localStorage.setItem(migrationKey, 'true')
    return false
  }

  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment -- JSON.parse returns untyped data
  const conversations: ConversationEntry[] = JSON.parse(conversationsJson)
  const migratedKeys: string[] = []

  for (const conv of conversations) {
    await saveConversation(conv)

    const messagesJson = localStorage.getItem(conv.id)
    if (messagesJson) {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment -- JSON.parse returns untyped data
      const messages: UIMessage[] = JSON.parse(messagesJson)
      await saveMessages(conv.id, messages)
      migratedKeys.push(conv.id)
    }
  }

  // Clean up localStorage only after all IDB writes succeeded
  for (const key of migratedKeys) {
    localStorage.removeItem(key)
  }
  localStorage.removeItem('conversationIds')
  localStorage.setItem(migrationKey, 'true')

  return true
}
