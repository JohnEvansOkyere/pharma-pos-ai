import { useState, useEffect } from 'react'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { FiAlertCircle, FiPackage, FiInfo } from 'react-icons/fi'

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadNotifications()
  }, [])

  const loadNotifications = async () => {
    setIsLoading(true)
    try {
      const data = await api.getNotifications({ limit: 50 })
      setNotifications(data)
    } catch (error) {
      toast.error('Failed to load notifications')
    } finally {
      setIsLoading(false)
    }
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'expiry':
        return <FiAlertCircle className="h-5 w-5 text-red-600" />
      case 'low_stock':
        return <FiPackage className="h-5 w-5 text-yellow-600" />
      default:
        return <FiInfo className="h-5 w-5 text-blue-600" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Notifications
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            System alerts and warnings
          </p>
        </div>
        <button
          onClick={() => api.markAllNotificationsAsRead().then(loadNotifications)}
          className="btn-secondary"
        >
          Mark All as Read
        </button>
      </div>

      <div className="space-y-3">
        {notifications.map((notification) => (
          <div
            key={notification.id}
            className={`card p-4 ${
              !notification.is_read ? 'border-l-4 border-primary-600' : ''
            }`}
          >
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 mt-1">{getIcon(notification.type)}</div>
              <div className="flex-1">
                <h3 className="font-medium text-gray-900 dark:text-gray-100">
                  {notification.title}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {notification.message}
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  {new Date(notification.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        ))}

        {notifications.length === 0 && (
          <div className="card p-12 text-center text-gray-400">
            <p>No notifications</p>
          </div>
        )}
      </div>
    </div>
  )
}
