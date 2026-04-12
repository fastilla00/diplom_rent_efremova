import { defineStore } from 'pinia'
import { BLUR_PERSONAL_DATA } from '../config/privacy'

export const usePrivacyStore = defineStore('privacy', {
  state: () => ({
    /** Значение задаётся в `src/config/privacy.js` (NDA), не из UI */
    blurSensitive: BLUR_PERSONAL_DATA,
  }),
})
