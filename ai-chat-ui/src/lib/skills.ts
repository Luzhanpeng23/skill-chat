import type { SkillPack, SkillTask, SkillTaskEvent } from '@/types'

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
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

export async function createSkillTask(file: File): Promise<SkillTask> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/skill-tasks', {
    method: 'POST',
    body: formData,
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

  const result = (await response.json()) as { task: SkillTask }
  return result.task
}

export async function getSkillTask(taskId: string): Promise<{ task: SkillTask; events: SkillTaskEvent[] }> {
  return requestJson<{ task: SkillTask; events: SkillTaskEvent[] }>(`/api/skill-tasks/${encodeURIComponent(taskId)}`)
}

export async function listSkillTasks(): Promise<SkillTask[]> {
  const result = await requestJson<{ tasks: SkillTask[] }>('/api/skill-tasks')
  return result.tasks
}

export async function deleteSkillTask(taskId: string): Promise<void> {
  await requestJson(`/api/skill-tasks/${encodeURIComponent(taskId)}`, {
    method: 'DELETE',
  })
}

export async function listSkillPacks(): Promise<SkillPack[]> {
  const result = await requestJson<{ packs: SkillPack[] }>('/api/skill-packs')
  return result.packs
}

export async function listMySkillPacks(): Promise<SkillPack[]> {
  const result = await requestJson<{ packs: SkillPack[] }>('/api/skill-packs/mine')
  return result.packs
}

export async function listPublicSkillPacks(): Promise<SkillPack[]> {
  const result = await requestJson<{ packs: SkillPack[] }>('/api/plaza/skill-packs')
  return result.packs
}

export async function updateSkillPackVisibility(
  packId: string,
  visibility: 'private' | 'public',
): Promise<SkillPack> {
  const result = await requestJson<{ pack: SkillPack }>(`/api/skill-packs/${encodeURIComponent(packId)}/visibility`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ visibility }),
  })
  return result.pack
}

export function getSkillArchiveUrl(taskId: string): string {
  return `/api/skill-tasks/${encodeURIComponent(taskId)}/download`
}

export function subscribeSkillTaskEvents(
  taskId: string,
  onEvent: (event: SkillTaskEvent) => void,
  lastEventIndex = 0,
): () => void {
  const eventSource = new EventSource(
    `/api/skill-tasks/${encodeURIComponent(taskId)}/events/stream?lastEventIndex=${lastEventIndex}`,
  )

  eventSource.onmessage = (messageEvent) => {
    const payload = JSON.parse(messageEvent.data) as SkillTaskEvent
    onEvent(payload)
  }

  return () => {
    eventSource.close()
  }
}

export async function copySkillPackToMyLibrary(packId: string): Promise<SkillPack> {
  const result = await requestJson<{ pack: SkillPack }>(
    `/api/plaza/skill-packs/${encodeURIComponent(packId)}/copy`,
    {
      method: 'POST',
    },
  )
  return result.pack
}

export async function deleteSkillPack(packId: string): Promise<void> {
  await requestJson(`/api/skill-packs/${encodeURIComponent(packId)}`, {
    method: 'DELETE',
  })
}
