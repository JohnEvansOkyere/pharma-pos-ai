import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { lazy, Suspense, useEffect } from 'react'
import { useAuthStore } from './stores/authStore'
import {
  getDefaultAuthenticatedPath,
  isCloudReportingMode,
  isCustomerRetentionEnabled,
  isOfflineQueueEnabled,
  isPosMode,
} from './config/appMode'

// Pages
const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const CloudDashboardPage = lazy(() => import('./pages/CloudDashboardPage'))
const AuditLogsPage = lazy(() => import('./pages/AuditLogsPage'))
const ProductsPage = lazy(() => import('./pages/ProductsPage'))
const POSPage = lazy(() => import('./pages/POSPage'))
const SalesPage = lazy(() => import('./pages/SalesPage'))
const SuppliersPage = lazy(() => import('./pages/SuppliersPage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const StockAdjustmentsPage = lazy(() => import('./pages/StockAdjustmentsPage'))
const ClientsPage = lazy(() => import('./pages/ClientsPage'))
const CustomersPage = lazy(() => import('./pages/CustomersPage'))
const CustomerAnalyticsPage = lazy(() => import('./pages/CustomerAnalyticsPage'))
const FollowUpDashboard = lazy(() => import('./pages/FollowUpDashboard'))
const OfflineQueuePage = lazy(() => import('./pages/OfflineQueuePage'))

// Layout
import MainLayout from './components/layout/MainLayout'

// Protected route component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Admin-only route component
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user?.role !== 'admin') {
    return <Navigate to={getDefaultAuthenticatedPath(user)} replace />
  }

  return <>{children}</>
}

// Vendor-admin-only route: role=admin AND no organization (not a pharmacy client)
function VendorRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user?.role !== 'admin' || user.organization_id) {
    return <Navigate to={getDefaultAuthenticatedPath(user)} replace />
  }

  return <>{children}</>
}

// Admin or Manager route component
function AdminOrManagerRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user?.role !== 'admin' && user?.role !== 'manager') {
    return <Navigate to={getDefaultAuthenticatedPath(user)} replace />
  }

  return <>{children}</>
}

function DefaultAuthenticatedRoute() {
  const { user } = useAuthStore()
  return <Navigate to={getDefaultAuthenticatedPath(user)} replace />
}

function DisabledLocalRoute() {
  const { user } = useAuthStore()
  return <Navigate to={getDefaultAuthenticatedPath(user)} replace />
}

function App() {
  const { loadUser } = useAuthStore()

  useEffect(() => {
    loadUser()
  }, [loadUser])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#363636',
            color: '#fff',
          },
        }}
      />
      <Suspense fallback={<div className="p-6 text-sm text-gray-500">Loading...</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DefaultAuthenticatedRoute />} />
            {isPosMode && (
              <Route path="dashboard" element={
                <AdminRoute>
                  <DashboardPage />
                </AdminRoute>
              } />
            )}
            <Route path="cloud-dashboard" element={
              <AdminOrManagerRoute>
                <CloudDashboardPage />
              </AdminOrManagerRoute>
            } />
            <Route path="audit-logs" element={
              <AdminRoute>
                <AuditLogsPage />
              </AdminRoute>
            } />
            {isPosMode ? (
              <>
                <Route path="products" element={<ProductsPage />} />
                <Route path="pos" element={<POSPage />} />
                <Route path="sales" element={<SalesPage />} />
                <Route path="stock-adjustments" element={
                  <AdminOrManagerRoute>
                    <StockAdjustmentsPage />
                  </AdminOrManagerRoute>
                } />
                <Route path="suppliers" element={<SuppliersPage />} />
                <Route path="notifications" element={<NotificationsPage />} />
                <Route path="settings" element={
                  <AdminOrManagerRoute>
                    <SettingsPage />
                  </AdminOrManagerRoute>
                } />
                {isCustomerRetentionEnabled && (
                  <>
                    <Route path="customers" element={<CustomersPage />} />
                    <Route path="customer-analytics" element={
                      <AdminOrManagerRoute>
                        <CustomerAnalyticsPage />
                      </AdminOrManagerRoute>
                    } />
                    <Route path="follow-ups" element={
                      <AdminOrManagerRoute>
                        <FollowUpDashboard />
                      </AdminOrManagerRoute>
                    } />
                  </>
                )}
                {isOfflineQueueEnabled && (
                  <Route path="offline-queue" element={
                    <AdminOrManagerRoute>
                      <OfflineQueuePage />
                    </AdminOrManagerRoute>
                  } />
                )}
              </>
            ) : (
              <>
                <Route path="dashboard" element={<DisabledLocalRoute />} />
                <Route path="products" element={<DisabledLocalRoute />} />
                <Route path="pos" element={<DisabledLocalRoute />} />
                <Route path="sales" element={<DisabledLocalRoute />} />
                <Route path="stock-adjustments" element={<DisabledLocalRoute />} />
                <Route path="suppliers" element={<DisabledLocalRoute />} />
                <Route path="notifications" element={<DisabledLocalRoute />} />
                <Route path="settings" element={<DisabledLocalRoute />} />
              </>
            )}
            <Route path="clients" element={
              <VendorRoute>
                <ClientsPage />
              </VendorRoute>
            } />
          </Route>

          <Route path="*" element={<DefaultAuthenticatedRoute />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
