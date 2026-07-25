import { useEffect, useState } from 'react'
import { fetchTrainingKnowledge } from '../api'
import type { TrainingKnowledge } from '../types'
import { readableTransform } from '../utils/transform'
import { ReliabilityChart } from './ReliabilityChart'
import { VectorFieldOverlay } from './VectorFieldOverlay'

function ratio(support: number, total: number): number {
  return total <= 0 ? 0 : Math.max(0, Math.min(1, support / total))
}

export function KnowledgeView() {
  const [knowledge, setKnowledge] = useState<TrainingKnowledge | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTrainingKnowledge()
      .then(setKnowledge)
      .catch((reason: Error) => setError(reason.message))
  }, [])

  if (error) return <section className="training-empty error">{error}</section>
  if (!knowledge) return <section className="training-empty">读取知识库…</section>

  return (
    <div className="knowledge-view">
      <section className="knowledge-table-panel">
        <div className="training-section-head">
          <div>
            <span className="section-label">KNOWLEDGE</span>
            <h3>空间变换先验</h3>
          </div>
          <span>{knowledge.priors.length} priors</span>
        </div>
        <div className="compact-table knowledge-table">
          <div className="compact-head"><span>ACTION</span><span>VECTOR</span><span>函数</span><span>SUPPORT</span></div>
          {knowledge.priors.map((prior) => {
            const readable = prior.readable || readableTransform(prior.family)
            return (
              <div className="compact-row" key={`${prior.action}-${readable}`}>
                <b>{prior.action}</b>
                <VectorFieldOverlay spec={prior.family} compact />
                <code>{readable}</code>
                <span className="support-meter">
                  <i style={{ width: `${ratio(prior.support, prior.total) * 100}%` }} />
                  <em>{prior.support}/{prior.total}</em>
                </span>
              </div>
            )
          })}
        </div>
      </section>
      <ReliabilityChart points={knowledge.reliability} />
    </div>
  )
}
