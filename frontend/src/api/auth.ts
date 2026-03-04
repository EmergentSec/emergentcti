import axios from 'axios'

export async function validateApiKey(key: string): Promise<boolean> {
  try {
    await axios.get('/api/v1/health', {
      headers: { 'X-API-Key': key },
    })
    return true
  } catch {
    return false
  }
}
