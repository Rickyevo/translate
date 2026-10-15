import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/index.css'
import i18n, { resolveLang } from './i18n'
import { applyUrlSettings, useSettings } from './store'
import App from './App'

applyUrlSettings()
i18n.changeLanguage(resolveLang(useSettings.getState().saved.uiLang))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
