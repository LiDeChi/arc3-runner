import { useEffect, useState } from 'react'
import { fetchTrainingKnowledge } from '../api'
import type { TrainingKnowledge } from '../types'
import { ReliabilityChart } from './ReliabilityChart'
import { TrendChart } from './TrendChart'

export function CalibrationView() {
  const [knowledge, setKnowledge] = useState<TrainingKnowledge | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTrainingKnowledge()
      .then(setKnowledge)
      .catch((reason: Error) => setError(reason.message))
  }, [])

  if (error) return <section className="training-empty error">{error}</section>
  if (!knowledge) return <section className="training-empty">读取校准数据…</section>

  return (
    <div className="calibration-view">
      <ReliabilityChart points={knowledge.reliability} title="置信度可靠性" />
      <TrendChart
        title="惊奇时间线"
        subtitle="按训练回放顺序显示预测失误峰值"
        yDomain={[0, 1]}
        series={[
          {
            label: 'surprise',
            color: '#ef3340',
            points: knowledge.surprise_timeline.map((item, index) => ({
              x: index + 1,
              y: item.surprise,
            })),
          },
        ]}
      />
    </div>
  )
}
