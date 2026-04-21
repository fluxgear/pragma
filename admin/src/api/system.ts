import { apiRequest } from '@/api/client'
import type { ReadinessResponse } from '@/api/types'

export function fetchReadinessStatus(): Promise<ReadinessResponse> {
  return apiRequest<ReadinessResponse>('/system/ready', {
    method: 'GET',
  })
}
