export interface Project {
  id: string
  name: string
  description: string
  owner_id: string
  is_public: boolean
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  is_public?: boolean
}

export interface ProjectUpdate {
  name?: string
  description?: string
  is_public?: boolean
}

export interface ProjectMember {
  id: string
  project_id: string
  user_id: string
  role: MemberRole
  user: {
    id: string
    username: string
    email: string
    full_name: string
  }
  created_at: string
}

export type MemberRole = 'owner' | 'admin' | 'member' | 'viewer'

export interface MediaFile {
  id: string
  project_id: string
  filename: string
  original_filename: string
  file_type: FileType
  file_size: number
  duration?: number // 音频/视频时长（秒）
  sample_rate?: number // 音频采样率（Hz）
  channels?: number // 音频通道数
  bit_depth?: number // 音频位深度
  width?: number // 视频宽度
  height?: number // 视频高度
  frame_rate?: number // 视频帧率
  metadata: Record<string, any>
  created_at: string
  updated_at: string
}

export type FileType = 'audio' | 'video' | 'ecg' | 'pcg' | 'other'

export interface Annotation {
  id: string
  file_id: string
  user_id: string
  annotation_type: AnnotationType
  start_time: number
  end_time: number
  label: string
  confidence?: number
  metadata: Record<string, any>
  created_at: string
  updated_at: string
}

export type AnnotationType = 's1' | 's2' | 'qrs' | 'p_wave' | 't_wave' | 'murmur' | 'other'

export interface AnalysisResult {
  id: string
  file_id: string
  analysis_type: string
  result_data: Record<string, any>
  created_at: string
}

export interface Workflow {
  id: string
  project_id: string
  name: string
  description: string
  steps: WorkflowStep[]
  status: WorkflowStatus
  created_at: string
  updated_at: string
}

export interface WorkflowStep {
  id: string
  name: string
  type: string
  config: Record<string, any>
  order: number
  dependencies?: string[]
}

export type WorkflowStatus = 'pending' | 'running' | 'completed' | 'failed'