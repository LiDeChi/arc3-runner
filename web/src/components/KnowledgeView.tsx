import type { TrainingKnowledge } from '../types'

export function KnowledgeView({ knowledge }: { knowledge?: TrainingKnowledge }) {
  return (
    <section className="training-dashboard">
      <div className="training-panel-head">
        <div>
          <span className="section-label">TRAINING / KNOWLEDGE</span>
          <h2>知识库</h2>
        </div>
      </div>
      <div className="knowledge-grid">
        <KnowledgeTable title="动作先验" rows={knowledge?.priors ?? []} columns={['action_key', 'family', 'support', 'total']} />
        <KnowledgeTable title="校准表" rows={knowledge?.calibration ?? []} columns={['bucket', 'claimed', 'hit_rate', 'n']} />
        <KnowledgeTable title="陷阱前兆" rows={knowledge?.trap_signals ?? []} columns={['trap', 'signature', 'hits']} />
      </div>
    </section>
  )
}

function KnowledgeTable({
  title,
  rows,
  columns,
}: {
  title: string
  rows: Array<Record<string, unknown>>
  columns: string[]
}) {
  return (
    <div className="knowledge-table">
      <h3>{title}</h3>
      <div className="knowledge-head">
        {columns.map((column) => <span key={column}>{column}</span>)}
      </div>
      {rows.length ? rows.slice(0, 24).map((row, index) => (
        <div className="knowledge-row" key={index}>
          {columns.map((column) => <span key={column}>{String(row[column] ?? '—')}</span>)}
        </div>
      )) : <p className="training-empty">暂无数据</p>}
    </div>
  )
}
