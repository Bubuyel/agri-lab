const R = 6371
const rad = (d: number) => (d * Math.PI) / 180

/** Great-circle distance in km. */
export function haversine(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLat = rad(lat2 - lat1)
  const dLon = rad(lon2 - lon1)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)))
}

/** Ask the phone's GPS (works without internet). */
export function getPosition(timeoutMs = 15000): Promise<{ lat: number; lon: number }> {
  return new Promise((res, rej) => {
    if (!navigator.geolocation) return rej(new Error('no-gps'))
    navigator.geolocation.getCurrentPosition(
      (p) => res({ lat: p.coords.latitude, lon: p.coords.longitude }),
      (e) => rej(e),
      { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: 10 * 60 * 1000 },
    )
  })
}
