import { useState } from 'react'
import { Toaster } from 'sonner'
import { Sidebar } from '@/components/layout/Sidebar'
import { MainContent } from '@/components/layout/MainContent'
import { AuthorFooter } from '@/components/layout/AuthorFooter'
import { CrawlerConfigPanel } from '@/components/config/CrawlerConfigPanel'
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel'
import { EnvironmentCheck, isEnvChecked } from '@/components/env/EnvironmentCheck'
import { LicenseDisclaimer, isLicenseAccepted } from '@/components/license/LicenseDisclaimer'

function App() {
  // Initialize by checking localStorage if license has been accepted
  const [licenseAccepted, setLicenseAccepted] = useState(() => isLicenseAccepted())
  // Initialize by checking localStorage if env check has passed
  const [envChecked, setEnvChecked] = useState(() => isEnvChecked())
  // State for showing disclaimer manually
  const [showDisclaimer, setShowDisclaimer] = useState(false)
  // 当前视图: crawler(爬虫控制台) | analysis(AI 内容分析)
  const [view, setView] = useState<'crawler' | 'analysis'>('crawler')

  const handleEnvCheckComplete = () => {
    setEnvChecked(true)
  }

  const handleLicenseAccept = () => {
    setLicenseAccepted(true)
    setShowDisclaimer(false)
  }

  const handleShowDisclaimer = () => {
    setShowDisclaimer(true)
  }

  return (
    <div className="flex flex-col h-screen cyber-grid overflow-hidden relative">
      {/* License Disclaimer Modal - Shows first or when triggered */}
      {(!licenseAccepted || showDisclaimer) && (
        <LicenseDisclaimer onAccept={handleLicenseAccept} />
      )}

      {/* Environment Check Modal - Shows after license accepted */}
      {licenseAccepted && !showDisclaimer && !envChecked && (
        <EnvironmentCheck onCheckComplete={handleEnvCheckComplete} />
      )}

      {/* Header Bar */}
      <Sidebar onShowDisclaimer={handleShowDisclaimer} />

      {/* Main Area */}
      <div className="flex-1 flex flex-col gap-4 p-4 overflow-hidden min-h-0">
        {/* 视图切换 */}
        <div className="flex gap-2 flex-shrink-0">
          <button
            className={`px-3 py-1 rounded text-sm border ${view === 'crawler' ? 'border-cyber-accent bg-cyber-accent/10 text-cyber-text-primary' : 'border-cyber-accent/20 text-cyber-text-secondary'}`}
            onClick={() => setView('crawler')}
          >
            🕷️ 爬虫控制台
          </button>
          <button
            className={`px-3 py-1 rounded text-sm border ${view === 'analysis' ? 'border-cyber-accent bg-cyber-accent/10 text-cyber-text-primary' : 'border-cyber-accent/20 text-cyber-text-secondary'}`}
            onClick={() => setView('analysis')}
          >
            🤖 内容分析
          </button>
        </div>

        {view === 'crawler' ? (
          <>
            {/* Config Panel - Primary Action Area (Always Expanded) */}
            <div className="flex-shrink-0">
              <CrawlerConfigPanel />
            </div>
            {/* Console - Collapsible Terminal */}
            <MainContent />
          </>
        ) : (
          <AnalysisPanel />
        )}
      </div>

      {/* Author Footer */}
      <AuthorFooter />

      {/* Toast notifications - Theme-aware style */}
      <Toaster
        position="top-right"
        toastOptions={{
          className: 'glass-panel font-mono text-cyber-text-primary',
          style: {
            fontFamily: 'JetBrains Mono, monospace',
          },
        }}
      />
    </div>
  )
}

export default App
