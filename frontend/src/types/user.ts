export interface User {
  id: string
  email: string
  username: string
  full_name: string
  role: 'admin' | 'member'
  is_active: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
}

export interface UserCreate {
  email: string
  username: string
  full_name: string
  password: string
}

export interface UserUpdate {
  email?: string
  username?: string
  full_name?: string
  password?: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterCredentials {
  email: string
  username: string
  full_name: string
  password: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}