import type { UserProfile } from '@/types'

interface AuthResponse {
  ok: boolean
  user: UserProfile
}

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

export async function getCurrentUser(): Promise<UserProfile | null> {
  const response = await fetch('/api/auth/me')
  if (response.status === 401) {
    return null
  }
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = (await response.json()) as AuthResponse
  return payload.user
}

export async function login(email: string, password: string): Promise<UserProfile> {
  const payload = await requestJson<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  return payload.user
}

export async function register(email: string, password: string, confirmPassword: string): Promise<UserProfile> {
  const payload = await requestJson<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, confirmPassword }),
  })
  return payload.user
}

export async function logout(): Promise<void> {
  await requestJson('/api/auth/logout', {
    method: 'POST',
  })
}
