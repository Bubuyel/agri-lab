/**
 * Lets a screen intercept the Android/browser back button for an internal sub-view (e.g. a crop detail page)
 * before the app-level router pops a whole screen. The handler returns true when it consumed the event.
 */
let sub: (() => boolean) | null = null
export const setSubBackHandler = (f: (() => boolean) | null) => { sub = f }
export const runSubBack = () => (sub ? sub() : false)
