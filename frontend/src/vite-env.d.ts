/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_APP_MODE?: string
  readonly VITE_POS_DEPLOYMENT_PROFILE?: string
  readonly VITE_CUSTOMER_RETENTION_ENABLED?: string
  readonly VITE_OFFLINE_QUEUE_ENABLED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
