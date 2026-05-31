import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import OfflineBanner from './OfflineBanner'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'

export default function MainLayout() {
  const [isSidebarVisible, setIsSidebarVisible] = useState(true)
  const onlineStatus = useOnlineStatus()

  return (
    <div className="h-screen flex bg-gray-50 dark:bg-gray-900 overflow-hidden">
      {isSidebarVisible && (
        <Sidebar onHide={() => setIsSidebarVisible(false)} />
      )}

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          isSidebarVisible={isSidebarVisible}
          onToggleSidebar={() => setIsSidebarVisible((current) => !current)}
        />

        {/* Offline fallback banner — only renders in online_pos mode */}
        <OfflineBanner onlineStatus={onlineStatus} />

        <main className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <div className="max-w-screen-xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
