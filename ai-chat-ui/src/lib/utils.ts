import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

import type { SkillPack, SkillTask } from '@/types'

const GENERATED_TASK_ID_RE = /^skill-task-[a-z0-9]+$/i
const NOISY_SOURCE_SUFFIX_RE = /\s*\((?:z-library|1lib|z-lib|annas-archive|libgen)[^)]*\)\s*$/i

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function isGeneratedTaskLabel(value?: string | null) {
  return Boolean(value && GENERATED_TASK_ID_RE.test(value.trim()))
}

export function deriveBookTitleFromFileName(fileName?: string | null) {
  if (!fileName) return undefined

  let value = fileName.trim().replace(/\.[^.]+$/, '')
  while (NOISY_SOURCE_SUFFIX_RE.test(value)) {
    value = value.replace(NOISY_SOURCE_SUFFIX_RE, '').trim()
  }

  return value || undefined
}

export function resolveTaskDisplayTitle(task?: SkillTask | null) {
  const bookTitle = task?.result?.bookTitle?.trim()
  if (bookTitle && !isGeneratedTaskLabel(bookTitle)) {
    return bookTitle
  }

  return deriveBookTitleFromFileName(task?.fileName) || bookTitle || task?.id || 'Untitled book'
}

export function resolveSkillPackDisplayTitle(pack?: SkillPack | null, relatedTask?: SkillTask | null) {
  const packTitle = pack?.title?.trim()
  if (packTitle && !isGeneratedTaskLabel(packTitle)) {
    return packTitle
  }

  const taskTitle = relatedTask?.result?.bookTitle?.trim()
  if (taskTitle && !isGeneratedTaskLabel(taskTitle)) {
    return taskTitle
  }

  return deriveBookTitleFromFileName(relatedTask?.fileName) || packTitle || pack?.id || 'Untitled pack'
}
