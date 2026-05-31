/**
 * Offline transaction queue backed by IndexedDB.
 *
 * Only active in ``online_pos`` mode. In ``local_pos`` mode the POS writes
 * directly to the local PostgreSQL database and no queue is needed.
 *
 * Queue lifecycle:
 *   1. When connectivity is lost, the POS calls ``enqueue()`` instead of
 *      posting to the API.
 *   2. When connectivity returns, ``flush()`` drains the queue by posting
 *      each pending transaction to the API in FIFO order.
 *   3. If a flush fails (server rejects the payload) the item is marked
 *      ``failed`` after MAX_ATTEMPTS and skipped so the queue does not jam.
 *   4. Successful flushes remove the item from the queue permanently.
 *   5. Failed items can be inspected, individually retried, or exported
 *      (CSV / JSON) via the Offline Queue management page (/offline-queue).
 *
 * Durability notes:
 *   IndexedDB persists across page navigations and browser restarts but is
 *   wiped by "Clear site data". Operators should be warned via the Offline
 *   Queue page banner. For mission-critical deployments, use local_pos mode
 *   which writes directly to a local PostgreSQL database.
 */

const DB_NAME = 'pharma_offline_queue'
const DB_VERSION = 2  // bumped: added localInvoice field
const STORE_NAME = 'pending_sales'

export const MAX_ATTEMPTS = 3

export interface QueuedSale {
  id?: number           // auto-incremented by IndexedDB
  localInvoice: string  // provisional invoice number stamped at queue time
  payload: Record<string, unknown>
  queuedAt: string      // ISO timestamp
  attempts: number
  status: 'pending' | 'failed'
  lastError?: string
  flushedInvoice?: string  // server invoice number after successful flush
}

/** Generate a provisional invoice number for use before the sale reaches the server. */
export function generateLocalInvoice(): string {
  const now = new Date()
  const date = now.toISOString().slice(0, 10).replace(/-/g, '')
  const ms = String(now.getTime()).slice(-6)
  return `TMP-${date}-${ms}`
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        })
        store.createIndex('status', 'status', { unique: false })
        store.createIndex('queuedAt', 'queuedAt', { unique: false })
        store.createIndex('localInvoice', 'localInvoice', { unique: true })
      } else {
        // v1 → v2: add localInvoice index if upgrading
        const tx = (event.target as IDBOpenDBRequest).transaction!
        const store = tx.objectStore(STORE_NAME)
        if (!store.indexNames.contains('localInvoice')) {
          store.createIndex('localInvoice', 'localInvoice', { unique: false })
        }
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

/**
 * Add a sale payload to the offline queue.
 * Returns the locally-assigned provisional invoice number.
 */
export async function enqueue(
  payload: Record<string, unknown>,
  localInvoice?: string,
): Promise<{ id: number; localInvoice: string }> {
  const db = await openDB()
  const invoice = localInvoice ?? generateLocalInvoice()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const item: QueuedSale = {
      localInvoice: invoice,
      payload,
      queuedAt: new Date().toISOString(),
      attempts: 0,
      status: 'pending',
    }
    const req = store.add(item)
    req.onsuccess = () => resolve({ id: req.result as number, localInvoice: invoice })
    req.onerror = () => reject(req.error)
  })
}

/**
 * Return all items in the queue, ordered by insertion (FIFO).
 */
export async function list(): Promise<QueuedSale[]> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const index = store.index('queuedAt')
    const req = index.openCursor()
    const items: QueuedSale[] = []
    req.onsuccess = () => {
      const cursor = req.result
      if (cursor) {
        items.push(cursor.value as QueuedSale)
        cursor.continue()
      } else {
        resolve(items)
      }
    }
    req.onerror = () => reject(req.error)
  })
}

/**
 * Return the count of pending items in the queue.
 */
export async function pendingCount(): Promise<number> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const index = store.index('status')
    const req = index.count(IDBKeyRange.only('pending'))
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

/**
 * Return the count of failed items in the queue.
 */
export async function failedCount(): Promise<number> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const index = store.index('status')
    const req = index.count(IDBKeyRange.only('failed'))
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function deleteItem(db: IDBDatabase, id: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.delete(id)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

function updateItem(db: IDBDatabase, item: QueuedSale): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.put(item)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

export interface FlushResult {
  flushed: number
  failed: number
  remaining: number
}

/**
 * Drain the queue by posting each pending item to the API.
 *
 * @param postSale - A function that accepts the sale payload and POSTs it to
 *   the backend. Should resolve on success and reject on failure.
 * @param onProgress - Optional callback called after each item is processed.
 */
export async function flush(
  postSale: (payload: Record<string, unknown>) => Promise<unknown>,
  onProgress?: (result: FlushResult) => void,
): Promise<FlushResult> {
  const db = await openDB()
  const items = await list()
  const pending = items.filter((i) => i.status === 'pending')

  let flushed = 0
  let failed = 0

  for (const item of pending) {
    try {
      await postSale(item.payload)
      await deleteItem(db, item.id!)
      flushed++
    } catch (err: unknown) {
      item.attempts++
      item.lastError = err instanceof Error ? err.message : String(err)
      // After MAX_ATTEMPTS, mark as failed so the queue does not jam.
      if (item.attempts >= MAX_ATTEMPTS) {
        item.status = 'failed'
        failed++
      }
      await updateItem(db, item)
    }
    if (onProgress) {
      const remaining = (await pendingCount()) - flushed
      onProgress({ flushed, failed, remaining })
    }
  }

  const remaining = await pendingCount()
  return { flushed, failed, remaining }
}

/**
 * Reset a failed item back to pending so it can be retried.
 * Resets attempt counter to 0.
 */
export async function retryFailed(id: number): Promise<void> {
  const db = await openDB()
  const items = await list()
  const item = items.find((i) => i.id === id)
  if (!item) throw new Error(`Queue item #${id} not found`)
  item.status = 'pending'
  item.attempts = 0
  item.lastError = undefined
  await updateItem(db, item)
}

/**
 * Reset ALL failed items back to pending.
 */
export async function retryAllFailed(): Promise<number> {
  const items = await list()
  const failed = items.filter((i) => i.status === 'failed')
  const db = await openDB()
  for (const item of failed) {
    item.status = 'pending'
    item.attempts = 0
    item.lastError = undefined
    await updateItem(db, item)
  }
  return failed.length
}

/**
 * Remove a single item from the queue by ID (operator-initiated).
 */
export async function removeItem(id: number): Promise<void> {
  const db = await openDB()
  await deleteItem(db, id)
}

/**
 * Remove all failed items from the queue (operator-initiated cleanup).
 */
export async function clearFailed(): Promise<number> {
  const db = await openDB()
  const items = await list()
  const failed = items.filter((i) => i.status === 'failed')
  for (const item of failed) {
    await deleteItem(db, item.id!)
  }
  return failed.length
}

/**
 * Export all failed items as a downloadable JSON file for manual reconciliation.
 * Triggers a browser download. Returns the count of exported items.
 */
export async function exportFailed(): Promise<number> {
  const items = await list()
  const failed = items.filter((i) => i.status === 'failed')
  if (failed.length === 0) return 0

  const exportData = {
    exportedAt: new Date().toISOString(),
    device: navigator.userAgent,
    count: failed.length,
    items: failed.map((item) => ({
      localInvoice: item.localInvoice,
      queuedAt: item.queuedAt,
      attempts: item.attempts,
      lastError: item.lastError,
      payload: item.payload,
    })),
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `pharma-failed-sales-${new Date().toISOString().slice(0, 10)}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  return failed.length
}

/**
 * Export all queue items (pending + failed) as JSON — for full reconciliation.
 */
export async function exportAll(): Promise<number> {
  const items = await list()
  if (items.length === 0) return 0

  const exportData = {
    exportedAt: new Date().toISOString(),
    device: navigator.userAgent,
    count: items.length,
    items: items.map((item) => ({
      localInvoice: item.localInvoice,
      status: item.status,
      queuedAt: item.queuedAt,
      attempts: item.attempts,
      lastError: item.lastError,
      payload: item.payload,
    })),
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `pharma-offline-queue-${new Date().toISOString().slice(0, 10)}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  return items.length
}
