/**
 * Permission checking composable for frontend role-based access control
 *
 * Hierarchies:
 * - Global: admin > member
 * - Project: owner (4) > admin (3) > member (2) > viewer (1)
 */
import { computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useProjectStore } from '@/store/project'

// Permission levels
export const ProjectAccessLevel = {
  OWNER: 4,
  ADMIN: 3,
  MEMBER: 2,
  VIEWER: 1,
  NONE: 0,
}

/**
 * Get the numeric permission level for a project role
 */
export function getRoleLevel(role: string | null | undefined): number {
  if (!role) return ProjectAccessLevel.NONE
  const levels: Record<string, number> = {
    owner: ProjectAccessLevel.OWNER,
    admin: ProjectAccessLevel.ADMIN,
    member: ProjectAccessLevel.MEMBER,
    viewer: ProjectAccessLevel.VIEWER,
  }
  return levels[role] ?? ProjectAccessLevel.NONE
}

/**
 * Composable for permission checks within a project
 */
export function useProjectPermission(projectId: string | (() => string)) {
  const authStore = useAuthStore()
  const projectStore = useProjectStore()

  // Get project ID (reactive support)
  const getProjectId = () => typeof projectId === 'function' ? projectId() : projectId

  // Get current user's role in this project
  const currentUserRole = computed(() => {
    const pid = getProjectId()
    if (!pid) return null

    const member = projectStore.projectMembers.find(m => m.user_id === authStore.user?.id)
    return member?.role ?? null
  })

  const currentUserLevel = computed(() => getRoleLevel(currentUserRole.value))

  // Permission checks
  const isOwner = computed(() => currentUserLevel.value === ProjectAccessLevel.OWNER)
  const isAdmin = computed(() => currentUserLevel.value >= ProjectAccessLevel.ADMIN)
  const isMember = computed(() => currentUserLevel.value >= ProjectAccessLevel.MEMBER)
  const isViewer = computed(() => currentUserLevel.value >= ProjectAccessLevel.VIEWER)

  // Feature access (completely hide if not allowed)
  const canUpload = computed(() => isMember.value)
  const canDelete = computed(() => isAdmin.value)
  const canDetectAnnotations = computed(() => isMember.value)
  const canEditAnnotations = computed(() => isMember.value)
  const canViewProjectSettings = computed(() => true) // All can view
  const canEditProjectSettings = computed(() => isAdmin.value)
  const canManageMembers = computed(() => isAdmin.value)
  const canManageAssociations = computed(() => isMember.value)
  const canShare = computed(() => isMember.value)
  const canDeleteFile = computed(() => isAdmin.value)

  // Generic permission check
  const hasPermission = (minRole: string): boolean => {
    const minLevel = getRoleLevel(minRole)
    return currentUserLevel.value >= minLevel
  }

  const requirePermission = (minRole: string): boolean => {
    if (!hasPermission(minRole)) {
      console.warn(`Permission denied: require ${minRole}, but user has ${currentUserRole.value}`)
      return false
    }
    return true
  }

  return {
    // States
    currentUserRole,
    currentUserLevel,

    // Role checks
    isOwner,
    isAdmin,
    isMember,
    isViewer,

    // Feature access
    canUpload,
    canDelete,
    canDetectAnnotations,
    canEditAnnotations,
    canViewProjectSettings,
    canEditProjectSettings,
    canManageMembers,
    canManageAssociations,
    canShare,
    canDeleteFile,

    // Generic checks
    hasPermission,
    requirePermission,
  }
}
