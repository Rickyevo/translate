/* Simulated candidate lists. Both directions render exactly this data. */

export type Target = 'en' | 'ja' | 'ko' | 'fr' | 'de' | 'es' | 'ru'
export const TARGETS: { id: Target; native: string }[] = [
  { id: 'en', native: 'English' },
  { id: 'ja', native: '日本語' },
  { id: 'ko', native: '한국어' },
  { id: 'fr', native: 'Français' },
  { id: 'de', native: 'Deutsch' },
  { id: 'es', native: 'Español' },
  { id: 'ru', native: 'Русский' },
]
/** Languages with full sample data in the prototype. Others fall back to English samples. */
export const SAMPLE_TARGETS: Target[] = ['en', 'ja', 'ko']

export type ItemState = 'loading' | 'done' | 'failed' | 'noEntry'
export type Source = 'cache' | 'dict' | 'ai'
export type Banner = 'offline' | 'localOnly' | 'failed' | 'auth' | 'paused' | null
export type Reason = 'timeout' | 'network' | 'noEntry' | 'noEntryLang'

export interface Candidate {
  text: string
  tr: Record<'en' | 'ja' | 'ko', string>
  /** Whether CC-CEDICT has this headword (words yes, long phrases no). */
  inDict: boolean
}

export interface Item {
  n: number
  text: string
  translation?: string
  state: ItemState
  source?: Source
  reason?: Reason
}

export interface CandidateList {
  gen: number
  pinyin: string
  items: Item[]
  banner: Banner
}

const SHIJIAN: Candidate[] = [
  { text: '时间', tr: { en: 'time', ja: '時間', ko: '시간' }, inDict: true },
  { text: '事件', tr: { en: 'event', ja: '出来事', ko: '사건' }, inDict: true },
  { text: '实践', tr: { en: 'practice', ja: '実践', ko: '실천' }, inDict: true },
  { text: '世间', tr: { en: 'the world', ja: '世の中', ko: '세상' }, inDict: true },
  { text: '试剑', tr: { en: 'test a sword', ja: '試し斬り', ko: '칼을 시험하다' }, inDict: false },
]

const LONG: Candidate[] = [
  {
    text: '这个问题我们明天再讨论',
    tr: {
      en: "Let's discuss this question again tomorrow",
      ja: 'この問題はまた明日話し合いましょう',
      ko: '이 문제는 내일 다시 논의합시다',
    },
    inDict: false,
  },
  {
    text: '这个问题我们',
    tr: { en: 'This question, we', ja: 'この問題は私たちが', ko: '이 문제는 우리가' },
    inDict: false,
  },
  { text: '这个问题', tr: { en: 'this question', ja: 'この問題', ko: '이 문제' }, inDict: false },
  { text: '这个', tr: { en: 'this', ja: 'これ', ko: '이것' }, inDict: true },
  { text: '这', tr: { en: 'this', ja: 'この', ko: '이' }, inDict: true },
]

export type ScenarioId =
  | 'short'
  | 'long'
  | 'loading'
  | 'partial'
  | 'failed'
  | 'offline'
  | 'localOnly'
  | 'auth'
  | 'paused'

export const SCENARIOS: { id: ScenarioId; label: string; pinyin: string }[] = [
  { id: 'short', label: 'Short', pinyin: "shi'jian" },
  { id: 'long', label: 'Long', pinyin: "zhe'ge'wen'ti'wo'men'ming'tian'zai'tao'lun" },
  { id: 'loading', label: 'Loading', pinyin: "shi'jian" },
  { id: 'partial', label: 'Partial', pinyin: "zhe'ge'wen'ti'wo'men'ming'tian'zai'tao'lun" },
  { id: 'failed', label: 'Failed', pinyin: "shi'jian" },
  { id: 'offline', label: 'Offline', pinyin: "shi'jian" },
  { id: 'localOnly', label: 'Local-only', pinyin: "zhe'ge'wen'ti'wo'men'ming'tian'zai'tao'lun" },
  { id: 'auth', label: 'Bad key', pinyin: "shi'jian" },
  { id: 'paused', label: 'Paused', pinyin: "shi'jian" },
]

let genCounter = 40

function trFor(c: Candidate, target: Target) {
  const k = (SAMPLE_TARGETS.includes(target) ? target : 'en') as 'en' | 'ja' | 'ko'
  return c.tr[k]
}

/** Local dictionary only covers zh → en headwords; everything else needs the service. */
function dictLookup(c: Candidate, target: Target): Pick<Item, 'state' | 'translation' | 'source' | 'reason'> {
  if (target !== 'en') return { state: 'noEntry', reason: 'noEntryLang' }
  if (!c.inDict) return { state: 'noEntry', reason: 'noEntry' }
  return { state: 'done', translation: trFor(c, target), source: 'dict' }
}

export function buildList(id: ScenarioId, target: Target, count = 5): CandidateList {
  const base = id === 'long' || id === 'partial' || id === 'localOnly' ? LONG : SHIJIAN
  const pinyin = SCENARIOS.find((s) => s.id === id)!.pinyin
  const cands = base.slice(0, count)
  let banner: Banner = null
  const items: Item[] = cands.map((c, i) => {
    const n = i + 1
    const done: Item = { n, text: c.text, state: 'done', translation: trFor(c, target), source: i === 0 ? 'cache' : 'ai' }
    switch (id) {
      case 'short':
      case 'long':
        return done
      case 'loading':
        return { n, text: c.text, state: 'loading' }
      case 'partial': {
        const pattern: ItemState[] = ['done', 'loading', 'done', 'failed', 'loading']
        const st = pattern[i] ?? 'loading'
        if (st === 'done') return done
        if (st === 'failed') return { n, text: c.text, state: 'failed', reason: 'timeout' }
        return { n, text: c.text, state: st }
      }
      case 'failed':
        banner = 'failed'
        return i === 0 ? done : { n, text: c.text, state: 'failed', reason: 'network' }
      case 'auth':
        banner = 'auth'
        return i === 0 ? done : { n, text: c.text, state: 'failed', reason: 'network' }
      case 'offline':
        banner = 'offline'
        return { n, text: c.text, ...dictLookup(c, target) }
      case 'localOnly':
        banner = 'localOnly'
        return { n, text: c.text, ...dictLookup(c, target) }
      case 'paused':
        banner = 'paused'
        return { n, text: c.text, state: 'done' }
    }
  })
  return { gen: ++genCounter, pinyin, items, banner }
}

/** Width estimate for a loading slot, so arrival doesn't jolt the layout. */
export function estimateWidth(text: string, target: Target) {
  const perChar = target === 'en' || target === 'fr' || target === 'de' || target === 'es' || target === 'ru' ? 2.2 : 1.1
  return Math.min(12, Math.max(3, Math.round(text.length * perChar * 1.2))) // in `ch`
}
