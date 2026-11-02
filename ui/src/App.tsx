import { MotionConfig } from 'framer-motion'
import type { ReactNode } from 'react'
import Footer from './components/Footer'
import Header from './components/Header'
import {
  ActiveAgents,
  CoreGlobe,
  CoreOverview,
  IntelFeed,
  LlmStatus,
  MemoryInsights,
  MissionTimeline,
  QuickCommands,
  SystemMonitor,
} from './components/Panels'
import Sidebar from './components/Sidebar'
import { useJarvis } from './store'

function Slot({ span, children }: { span: string; children: ReactNode }) {
  return <div className={`flex min-h-0 min-w-0 *:min-w-0 *:flex-1 ${span}`}>{children}</div>
}

export default function App() {
  const focus = useJarvis((s) => s.focusMode)

  return (
    // "user": com Reduzir Movimento ligado no sistema, o framer-motion troca deslocamentos por cortes secos
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-full lg:h-full lg:min-h-[640px]">
        <Sidebar />
        <main className="flex min-w-0 flex-1 flex-col gap-2.5 px-3 py-3 lg:min-h-0">
          <Header />

          {/* desktop: 3 linhas que dividem a altura; telas estreitas: cartões empilhados */}
          <div
            className={`grid min-h-0 flex-1 grid-cols-1 gap-2.5 md:grid-cols-2 lg:grid-cols-12 ${
              focus ? 'lg:grid-rows-1' : 'lg:grid-rows-[1.4fr_1fr_1fr]'
            }`}
          >
            {!focus && (
              <Slot span="lg:col-span-3">
                <CoreOverview />
              </Slot>
            )}
            <Slot span={focus ? 'md:col-span-2 lg:col-span-8' : 'md:col-span-2 lg:col-span-5 md:order-first lg:order-none'}>
              <CoreGlobe />
            </Slot>
            <Slot span={focus ? 'md:col-span-2 lg:col-span-4' : 'lg:col-span-4'}>
              <IntelFeed />
            </Slot>
            {!focus &&
              [ActiveAgents, MissionTimeline, QuickCommands, SystemMonitor, MemoryInsights, LlmStatus].map((Panel, i) => (
                <Slot key={i} span="lg:col-span-4">
                  <Panel />
                </Slot>
              ))}
          </div>

          <Footer />
        </main>
      </div>
    </MotionConfig>
  )
}
