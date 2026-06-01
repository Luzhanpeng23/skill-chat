import type { AdminStats, ConversationEntry, SkillPack, SkillTask, UserProfile } from '@/types'

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    let message = `Request failed: ${response.status}`
    try {
      const payload = (await response.json()) as { error?: string }
      if (payload.error) {
        message = payload.error
      }
    } catch {
      // noop
    }
    throw new Error(message)
  }

  return (await response.json()) as T
}

export async function getAdminStats(): Promise<AdminStats> {
  const payload = await requestJson<{ stats: AdminStats }>('/api/admin/overview')
  return payload.stats
}

export async function listAdminUsers(): Promise<UserProfile[]> {
  const payload = await requestJson<{ users: UserProfile[] }>('/api/admin/users')
  return payload.users
}

export async function updateAdminUser(
  userId: string,
  updates: Partial<Pick<UserProfile, 'isAdmin' | 'status'>>,
): Promise<UserProfile> {
  const payload = await requestJson<{ user: UserProfile }>(`/api/admin/users/${encodeURIComponent(userId)}`, {
    method: 'POST',
    body: JSON.stringify(updates),
  })
  return payload.user
}

export async function listAdminTasks(): Promise<SkillTask[]> {
  const payload = await requestJson<{ tasks: SkillTask[] }>('/api/admin/tasks')
  return payload.tasks
}

export async function deleteAdminTask(taskId: string): Promise<void> {
  await requestJson(`/api/admin/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' })
}

export async function listAdminSkillPacks(): Promise<SkillPack[]> {
  const payload = await requestJson<{ packs: SkillPack[] }>('/api/admin/skill-packs')
  return payload.packs
}

export async function updateAdminSkillPackVisibility(
  packId: string,
  visibility: 'private' | 'public',
): Promise<SkillPack> {
  const payload = await requestJson<{ pack: SkillPack }>(`/api/admin/skill-packs/${encodeURIComponent(packId)}/visibility`, {
    method: 'POST',
    body: JSON.stringify({ visibility }),
  })
  return payload.pack
}

export async function listAdminConversations(): Promise<ConversationEntry[]> {
  const payload = await requestJson<{ conversations: ConversationEntry[] }>('/api/admin/conversations')
  return payload.conversations
}

export async function deleteAdminConversation(conversationId: string): Promise<void> {
  await requestJson(`/api/admin/conversations/${encodeURIComponent(conversationId)}`, { method: 'DELETE' })
}
