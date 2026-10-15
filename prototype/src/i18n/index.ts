import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import zhCN from './locales/zh-CN.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'

export const UI_LANGS = ['zh-CN', 'en', 'ja', 'ko'] as const
export type UiLang = (typeof UI_LANGS)[number]
export type UiLangPref = UiLang | 'system'

/** Language names are always written in their own language. */
export const UI_LANG_NATIVE: Record<UiLang, string> = {
  'zh-CN': '简体中文',
  en: 'English',
  ja: '日本語',
  ko: '한국어',
}

/** Simulated OS language for “Follow system”. */
export function systemLang(): UiLang {
  const l = navigator.language.toLowerCase()
  if (l.startsWith('zh')) return 'zh-CN'
  if (l.startsWith('ja')) return 'ja'
  if (l.startsWith('ko')) return 'ko'
  return 'en'
}

export function resolveLang(p: UiLangPref): UiLang {
  return p === 'system' ? systemLang() : p
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    'zh-CN': { translation: zhCN },
    ja: { translation: ja },
    ko: { translation: ko },
  },
  lng: 'zh-CN',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
