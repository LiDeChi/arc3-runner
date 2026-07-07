import { Beaker, Braces, Play, RefreshCw, ShieldAlert } from 'lucide-react'
import type { SynthSpec } from '../types'
import { CompactJson } from './CompactJson'

interface SynthFactoryProps {
  specs: SynthSpec[]
  loading: boolean
  selectedSpecId?: string
  onRefresh: () => void
  onCreate: (template: 'T1' | 'T6') => void
  onRun: (specId: string) => void
}

export function SynthFactory({
  specs,
  loading,
  selectedSpecId,
  onRefresh,
  onCreate,
  onRun,
}: SynthFactoryProps) {
  const trapCounts = specs.reduce<Record<string, number>>((acc, spec) => {
    const trap = spec.traps[0]?.template ?? 'synth'
    acc[trap] = (acc[trap] ?? 0) + 1
    return acc
  }, {})

  return (
    <section className="synth-factory">
      <div className="training-panel-head">
        <div>
          <span className="section-label">TRAINING / SYNTH FACTORY</span>
          <h2>对抗工厂</h2>
        </div>
        <div className="training-actions">
          <button onClick={onRefresh} disabled={loading}><RefreshCw size={12} className={loading ? 'spin' : ''} />刷新</button>
          <button onClick={() => onCreate('T1')}><Beaker size={12} />生成 T1</button>
          <button onClick={() => onCreate('T6')}><ShieldAlert size={12} />生成 T6</button>
        </div>
      </div>

      <div className="synth-summary-row">
        <div><span>SPECS</span><b>{specs.length}</b></div>
        <div><span>T1</span><b>{trapCounts.T1 ?? 0}</b></div>
        <div><span>T6</span><b>{trapCounts.T6 ?? 0}</b></div>
        <p>合成环境与官方 runner 共用回放组件；点击运行会创建新的 synth-local run。</p>
      </div>

      <div className="synth-card-grid">
        {specs.map((spec) => {
          const trap = spec.traps[0]?.template ?? 'SYNTH'
          const params = spec.traps[0]?.params ?? {}
          return (
            <article className={`synth-card ${selectedSpecId === spec.spec_id ? 'selected' : ''}`} key={spec.spec_id}>
              <div className="synth-card-top">
                <span className={`trap-badge trap-${trap.toLowerCase()}`}>{trap}</span>
                <strong>{spec.spec_id}</strong>
              </div>
              <div className="synth-mini-grid" aria-label={`${spec.spec_id} preview`}>
                <i
                  className="synth-goal"
                  style={{ left: `${(spec.goal.target[0] / spec.grid) * 100}%`, top: `${(spec.goal.target[1] / spec.grid) * 100}%` }}
                />
                <i
                  className="synth-avatar"
                  style={{ left: `${(spec.avatar.start[0] / spec.grid) * 100}%`, top: `${(spec.avatar.start[1] / spec.grid) * 100}%` }}
                />
              </div>
              <div className="synth-meta">
                <span>grid {spec.grid}</span>
                <span>k={String(params.k ?? '—')}</span>
                <span>max {spec.max_steps}</span>
              </div>
              <p>{trap === 'T1' ? '前 k 步 ACTION1 向上，之后变向右。' : '前 k 步 ACTION1 向上，之后叠加右偏移。'}</p>
              <div className="synth-card-actions">
                <button onClick={() => onRun(spec.spec_id)}><Play size={11} />回放/运行</button>
                <details>
                  <summary><Braces size={11} />GameSpec</summary>
                  <CompactJson data={spec} expandDepth={2} />
                </details>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
