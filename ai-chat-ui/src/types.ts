export interface UserProfile {
  id: string
  email: string
  isAdmin: boolean
  status: 'active' | 'disabled'
}

export interface ConversationEntry {
  id: string
  firstMessage?: string
  timestamp: number
  skillPackId?: string
  skillPackIds?: string[]
  ownerEmail?: string
  forkOf?: {
    conversationId: string
    messageIndex: number
  }
}

export interface SkillTaskEvent {
  index?: number
  event: string
  timestamp: string
  payload: Record<string, unknown>
  taskId?: string
}

export interface SkillPackSnapshotSkill {
  id: string
  path: string
  testsPath: string
}

export interface SkillPackSnapshot {
  files?: Array<{ name: string; path: string }>
  skills?: SkillPackSnapshotSkill[]
  rejectedReadme?: string
}

export interface SkillTaskResult {
  taskId: string
  bookTitle: string
  bookAuthor: string
  bookDirName?: string
  outputDir: string
  archivePath?: string | null
  publishedPaths: string[]
  finalSkills: string[]
  verifiedCount: number
  rejectedCount: number
  errors: string[]
  packId?: string
  snapshot?: SkillPackSnapshot
  stats: {
    rawChars: number
    finalCount: number
    ratio?: string
    startTime?: string
    endTime?: string
    tokenUsage?: {
      input_tokens: number
      output_tokens: number
      total_tokens: number
      successful_calls: number
    }
  }
}

export interface SkillTask {
  id: string
  type: 'book2skill'
  status: 'pending' | 'running' | 'completed' | 'failed'
  phase?: string
  createdAt: string
  updatedAt: string
  startedAt?: string
  completedAt?: string
  fileName: string
  filePath: string
  fileSize: number
  mimeType: string
  error?: string
  ownerUserId?: string
  ownerEmail?: string
  result?: SkillTaskResult
  packId?: string
}

export interface SkillPack {
  id: string
  taskId: string
  title: string
  author: string
  description?: string
  createdAt: string
  archivePath?: string | null
  outputDir: string
  publishedPaths: string[]
  snapshot?: SkillPackSnapshot
  verifiedCount: number
  visibility?: 'private' | 'public'
  ownerUserId?: string
  ownerEmail?: string
}

export interface AdminStats {
  users: number
  conversations: number
  tasks: number
  skillPacks: number
  publicSkillPacks: number
  activeUsers: number
}
