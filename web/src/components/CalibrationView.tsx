import type { TrainingGeneration, TrainingKnowledge } from '../types'
import { ReliabilityChart } from './ReliabilityChart'
import { TrendChart } from './TrendChart'

export function CalibrationView({ knowledge, generations }: { knowledge?: TrainingKnowledge; generations: TrainingGeneration[] }) {
  const calibration = knowledge?.calibration ?? []
  const timeline = knowledge?.surprise_timeline ?? []

  return (
    <section className="training-dashboard">
      <div className="training-panel-head">
        <div>
          <span className="section-label">TRAINING / CALIBRATION</span>
          <h2>可信度与惊奇</h2>
        </div>
      </div>
      <div className="calibration-grid">
        <ReliabilityChart points={calibration} title="置信度可靠性" />
        <TrendChart
          title="逐代 ECE"
          yDomain={[0, 1]}
          series={[
            {
              label: 'ece',
              color: '#f2c14e',
              points: generations.map((generation) => ({
                x: generation.gen,
                y: Number(generation.agent_metrics.ece ?? 0),
              })),
            },
          ]}
        />
        <TrendChart
          title="惊奇时间线"
          subtitle="按训练回放顺序显示预测失误峰值"
          yDomain={[0, 1]}
          series={[
            {
              label: 'surprise',
              color: '#ef3340',
              points: timeline.map((item, index) => ({ x: index + 1, y: item.surprise })),
            },
          ]}
        />
      </div>
    </section>
  )
}
