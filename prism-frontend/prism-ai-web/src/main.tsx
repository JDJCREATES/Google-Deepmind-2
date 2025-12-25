import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'onsenui/css/onsenui.css'
import 'onsenui/css/onsen-css-components.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
