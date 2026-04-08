import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiClock, FiEdit, FiPlus, FiRefreshCw, FiTrash, FiX } from 'react-icons/fi'
import { useAuthStore } from '../stores/authStore'

interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
}

interface BackupStatus {
  platform: string
  backup_dir: string
  latest_backup_path?: string | null
  latest_backup_exists: boolean
  latest_backup_time?: string | null
  latest_backup_size_bytes?: number | null
  latest_backup_age_hours?: number | null
  backup_is_recent: boolean
  retention_days: number
  trigger_available: boolean
  schedule_helper_available: boolean
}

interface SystemDiagnostics {
  platform: string
  app_version: string
  environment: string
  database_backend: string
  database_connected: boolean
  scheduler_enabled: boolean
  scheduler_running: boolean
  scheduler_job_count: number
  backup_dir: string
  latest_backup_exists: boolean
  latest_backup_time?: string | null
  backup_is_recent: boolean
  frontend_dist_available: boolean
  windows_backup_task_helper_available: boolean
  linux_backup_cron_helper_available: boolean
}

export default function SettingsPage() {
  const { user: currentUser } = useAuthStore()
  const [users, setUsers] = useState<User[]>([])
  const [backupStatus, setBackupStatus] = useState<BackupStatus | null>(null)
  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingBackupStatus, setIsLoadingBackupStatus] = useState(false)
  const [isLoadingDiagnostics, setIsLoadingDiagnostics] = useState(false)
  const [isTriggeringBackup, setIsTriggeringBackup] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'cashier',
    is_active: true
  })

  useEffect(() => {
    loadUsers()
  }, [])

  useEffect(() => {
    if (currentUser?.role === 'admin' || currentUser?.role === 'manager') {
      loadBackupStatus()
      loadDiagnostics()
    }
  }, [currentUser?.role])

  const loadUsers = async () => {
    setIsLoading(true)
    try {
      const data = await api.getUsers()
      setUsers(data)
    } catch (error) {
      toast.error('Failed to load users')
    } finally {
      setIsLoading(false)
    }
  }

  const loadBackupStatus = async () => {
    setIsLoadingBackupStatus(true)
    try {
      const data = await api.getBackupStatus()
      setBackupStatus(data)
    } catch (error) {
      toast.error('Failed to load backup status')
    } finally {
      setIsLoadingBackupStatus(false)
    }
  }

  const loadDiagnostics = async () => {
    setIsLoadingDiagnostics(true)
    try {
      const data = await api.getSystemDiagnostics()
      setDiagnostics(data)
    } catch (error) {
      toast.error('Failed to load system diagnostics')
    } finally {
      setIsLoadingDiagnostics(false)
    }
  }

  const handleBackupNow = async () => {
    setIsTriggeringBackup(true)
    try {
      const result = await api.triggerBackupNow()
      setBackupStatus(result.backup)
      toast.success('Backup completed successfully')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Backup failed')
    } finally {
      setIsTriggeringBackup(false)
    }
  }

  const formatBytes = (value?: number | null) => {
    if (!value) return '-'
    if (value < 1024) return `${value} B`
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
    if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
    return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const payload = {
      ...formData,
      username: formData.username.trim(),
      email: formData.email.trim().toLowerCase(),
      full_name: formData.full_name.trim(),
    }

    if (!payload.password) {
      delete (payload as { password?: string }).password
    }

    try {
      if (editingUser) {
        await api.updateUser(editingUser.id, payload)
        toast.success('User updated successfully')
      } else {
        await api.createUser(payload)
        toast.success('User created successfully')
      }
      setShowModal(false)
      resetForm()
      loadUsers()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save user')
    }
  }

  const handleEdit = (user: User) => {
    setEditingUser(user)
    setFormData({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      password: '',
      role: user.role,
      is_active: user.is_active
    })
    setShowModal(true)
  }

  const handleDelete = async (userId: number) => {
    if (!window.confirm('Are you sure you want to delete this user?')) return

    try {
      await api.deleteUser(userId)
      toast.success('User deleted successfully')
      loadUsers()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to delete user')
    }
  }

  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      full_name: '',
      password: '',
      role: 'cashier',
      is_active: true
    })
    setEditingUser(null)
  }

  const closeModal = () => {
    setShowModal(false)
    resetForm()
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Settings
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage users and system settings
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="btn-primary flex items-center"
        >
          <FiPlus className="mr-2" />
          Add User
        </button>
      </div>

      {(currentUser?.role === 'admin' || currentUser?.role === 'manager') && (
        <div className="card p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                Backup Status
              </h2>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                This helps confirm whether the local installation is protecting pharmacy data.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={loadBackupStatus}
                className="btn-secondary flex items-center"
                disabled={isLoadingBackupStatus}
              >
                <FiRefreshCw className="mr-2" />
                Refresh
              </button>
              <button
                onClick={handleBackupNow}
                className="btn-primary flex items-center"
                disabled={isTriggeringBackup || !backupStatus?.trigger_available}
              >
                <FiClock className="mr-2" />
                {isTriggeringBackup ? 'Backing Up...' : 'Back Up Now'}
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Last Backup
              </p>
              <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                {backupStatus?.latest_backup_time
                  ? new Date(backupStatus.latest_backup_time).toLocaleString()
                  : isLoadingBackupStatus
                  ? 'Loading...'
                  : 'No backup found'}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Backup Health
              </p>
              <p className={`mt-2 text-sm font-semibold ${
                backupStatus?.backup_is_recent
                  ? 'text-green-700 dark:text-green-300'
                  : 'text-red-700 dark:text-red-300'
              }`}>
                {backupStatus?.backup_is_recent ? 'Recent and healthy' : 'Needs attention'}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Latest Backup Size
              </p>
              <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                {formatBytes(backupStatus?.latest_backup_size_bytes)}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Retention
              </p>
              <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                {backupStatus?.retention_days ?? '-'} day(s)
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-gray-200 px-4 py-3 dark:border-gray-700">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Backup Folder
              </p>
              <p className="mt-2 break-all text-sm text-gray-700 dark:text-gray-300">
                {backupStatus?.backup_dir || 'Unavailable'}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 px-4 py-3 dark:border-gray-700">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Latest Backup File
              </p>
              <p className="mt-2 break-all text-sm text-gray-700 dark:text-gray-300">
                {backupStatus?.latest_backup_path || 'Unavailable'}
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:bg-slate-900/20 dark:text-slate-300">
            Recommended operation: keep nightly backups automatic, use “Back Up Now” before upgrades, and keep an external copy of recent backups for recovery.
          </div>
        </div>
      )}

      {(currentUser?.role === 'admin' || currentUser?.role === 'manager') && (
        <div className="card p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                Local Diagnostics
              </h2>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                Use this before handover or support calls to confirm the local installation is healthy.
              </p>
            </div>
            <button
              onClick={loadDiagnostics}
              className="btn-secondary flex items-center"
              disabled={isLoadingDiagnostics}
            >
              <FiRefreshCw className="mr-2" />
              Refresh Diagnostics
            </button>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Database
              </p>
              <p className={`mt-2 text-sm font-semibold ${diagnostics?.database_connected ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                {diagnostics?.database_connected ? 'Connected' : isLoadingDiagnostics ? 'Loading...' : 'Connection failed'}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Scheduler
              </p>
              <p className={`mt-2 text-sm font-semibold ${diagnostics?.scheduler_running ? 'text-green-700 dark:text-green-300' : 'text-amber-700 dark:text-amber-300'}`}>
                {diagnostics?.scheduler_enabled
                  ? diagnostics?.scheduler_running
                    ? `Running (${diagnostics.scheduler_job_count} jobs)`
                    : 'Enabled but not running'
                  : 'Disabled'}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Frontend Build
              </p>
              <p className={`mt-2 text-sm font-semibold ${diagnostics?.frontend_dist_available ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                {diagnostics?.frontend_dist_available ? 'Available' : isLoadingDiagnostics ? 'Loading...' : 'Missing'}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/40">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Environment
              </p>
              <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                {diagnostics?.environment || (isLoadingDiagnostics ? 'Loading...' : '-')}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-gray-200 px-4 py-3 dark:border-gray-700">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Platform And Version
              </p>
              <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                {diagnostics ? `${diagnostics.platform} • v${diagnostics.app_version}` : isLoadingDiagnostics ? 'Loading...' : 'Unavailable'}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 px-4 py-3 dark:border-gray-700">
              <p className="text-xs uppercase text-gray-500 dark:text-gray-400">
                Scheduler Setup Helpers
              </p>
              <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                Windows: {diagnostics?.windows_backup_task_helper_available ? 'Available' : 'Missing'} | Linux: {diagnostics?.linux_backup_cron_helper_available ? 'Available' : 'Missing'}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Username
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Full Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Role
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {users.map((user) => (
                <tr key={user.id}>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {user.id}
                  </td>
                  <td className="px-6 py-4 font-medium text-gray-900 dark:text-gray-100">
                    {user.username}
                  </td>
                  <td className="px-6 py-4 text-gray-900 dark:text-gray-100">
                    {user.full_name}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                    {user.email}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs rounded-full capitalize ${
                      user.role === 'admin'
                        ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300'
                        : user.role === 'manager'
                        ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                        : 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                    }`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      user.is_active
                        ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                        : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                    }`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 space-x-2">
                    {(currentUser?.role === 'admin' || (currentUser?.role === 'manager' && user.role === 'cashier')) && (
                      <>
                        <button
                          onClick={() => handleEdit(user)}
                          className="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                        >
                          <FiEdit />
                        </button>
                        <button
                          onClick={() => handleDelete(user.id)}
                          className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                        >
                          <FiTrash />
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {users.length === 0 && !isLoading && (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              No users found
            </div>
          )}

          {isLoading && (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              Loading...
            </div>
          )}
        </div>
      </div>

      {/* User Form Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-md max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                {editingUser ? 'Edit User' : 'Add New User'}
              </h2>
              <button
                onClick={closeModal}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <FiX size={24} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Username
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="input w-full"
                  required
                  disabled={!!editingUser}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  className="input w-full"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Email
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="input w-full"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Password {editingUser && '(leave blank to keep current)'}
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="input w-full"
                  required={!editingUser}
                  minLength={6}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Role
                </label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="input w-full"
                  required
                  disabled={currentUser?.role === 'manager'}
                >
                  <option value="cashier">Cashier/Teller</option>
                  {currentUser?.role === 'admin' && (
                    <>
                      <option value="manager">Manager</option>
                      <option value="admin">Admin</option>
                    </>
                  )}
                </select>
                {currentUser?.role === 'manager' && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Managers can only create cashier users
                  </p>
                )}
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="mr-2"
                />
                <label htmlFor="is_active" className="text-sm text-gray-700 dark:text-gray-300">
                  Active
                </label>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={closeModal}
                  className="btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary flex-1"
                >
                  {editingUser ? 'Update' : 'Create'} User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
