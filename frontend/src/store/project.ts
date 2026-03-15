import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Project, ProjectMember, MediaFile } from '@/types/project'

const apiHeaders = () => ({
  'Authorization': `Bearer ${localStorage.getItem('token')}`,
  'Content-Type': 'application/json',
})

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const projectMembers = ref<ProjectMember[]>([])
  const projectFiles = ref<MediaFile[]>([])

  const fetchProjects = async () => {
    try {
      const r = await fetch('/api/v1/projects/', { headers: apiHeaders() })
      if (r.ok) {
        const data = await r.json()
        projects.value = Array.isArray(data) ? data : (data.items ?? [])
      }
    } catch (e) { console.error(e) }
  }

  const createProject = async (data: Partial<Project>) => {
    try {
      const r = await fetch('/api/v1/projects/', {
        method: 'POST', headers: apiHeaders(), body: JSON.stringify(data)
      })
      if (r.ok) {
        const p = await r.json()
        projects.value.unshift(p)
        return p
      }
      return null
    } catch { return null }
  }

  const updateProject = async (id: string, data: Partial<Project>) => {
    try {
      const r = await fetch(`/api/v1/projects/${id}`, {
        method: 'PUT', headers: apiHeaders(), body: JSON.stringify(data)
      })
      if (r.ok) {
        const p = await r.json()
        const idx = projects.value.findIndex(x => x.id === id)
        if (idx !== -1) projects.value[idx] = p
        if (currentProject.value?.id === id) currentProject.value = p
        return p
      }
      return null
    } catch { return null }
  }

  const deleteProject = async (id: string) => {
    try {
      const r = await fetch(`/api/v1/projects/${id}`, { method: 'DELETE', headers: apiHeaders() })
      if (r.ok) {
        projects.value = projects.value.filter(p => p.id !== id)
        return true
      }
      return false
    } catch { return false }
  }

  const fetchProjectDetail = async (id: string) => {
    try {
      const r = await fetch(`/api/v1/projects/${id}`, { headers: apiHeaders() })
      if (r.ok) currentProject.value = await r.json()
    } catch (e) { console.error(e) }
  }

  const fetchProjectMembers = async (id: string) => {
    try {
      const r = await fetch(`/api/v1/projects/${id}/members`, { headers: apiHeaders() })
      if (r.ok) {
        const data = await r.json()
        projectMembers.value = Array.isArray(data) ? data : (data.items ?? [])
      }
    } catch (e) { console.error(e) }
  }

  const fetchProjectFiles = async (id: string) => {
    try {
      // limit=500 确保能拿到所有文件（包括模拟生成的新文件）
      const r = await fetch(`/api/v1/projects/${id}/files?limit=500`, { headers: apiHeaders() })
      if (r.ok) {
        const data = await r.json()
        projectFiles.value = Array.isArray(data) ? data : (data.items ?? [])
      }
    } catch (e) { console.error(e) }
  }

  const uploadFile = async (projectId: string, file: File) => {
    try {
      const token = localStorage.getItem('token')
      const form = new FormData()
      form.append('file', file)
      const r = await fetch(`/api/v1/projects/${projectId}/files/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form
      })
      if (r.ok) {
        const f = await r.json()
        projectFiles.value.push(f)
        return f
      }
      return null
    } catch { return null }
  }

  const deleteFile = async (fileId: string) => {
    try {
      const r = await fetch(`/api/v1/files/${fileId}`, { method: 'DELETE', headers: apiHeaders() })
      if (r.ok) {
        projectFiles.value = projectFiles.value.filter(f => f.id !== fileId)
        return true
      }
      return false
    } catch { return false }
  }

  return {
    projects, currentProject, projectMembers, projectFiles,
    fetchProjects, createProject, updateProject, deleteProject,
    fetchProjectDetail, fetchProjectMembers, fetchProjectFiles, uploadFile, deleteFile
  }
})
