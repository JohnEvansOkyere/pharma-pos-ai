import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

export default function MainLayout() {
  const [isSidebarVisible, setIsSidebarVisible] = useState(true)

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

        <main className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
