import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'

const METRIC_COLORS = {
  faithfulness: '#6382ff',
  answer_relevancy: '#34d399',
  context_recall: '#f59e0b',
  context_precision: '#a78bfa',
}

export default function ConfidencePanel({ confidence }) {
  if (!confidence) return null

  const metrics = [
    { label: 'Faithfulness', key: 'faithfulness' },
    { label: 'Relevancy', key: 'answer_relevancy' },
    { label: 'Context Recall', key: 'context_recall' },
    { label: 'Precision', key: 'context_precision' },
  ]

  const radarData = metrics.map(m => ({
    metric: m.label,
    score: Math.round((confidence[m.key] || 0) * 100),
    fullMark: 100,
  }))

  const overall = confidence.overall || 0

  return (
    <div className="card">
      <div className="card-header">
        <span>🎯</span> Confidence
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '14px', color: overall > 0.7 ? 'var(--accent-secondary)' : overall > 0.5 ? 'var(--accent-warning)' : 'var(--accent-danger)' }}>
          {(overall * 100).toFixed(0)}%
        </span>
      </div>
      <div className="card-body">
        <ResponsiveContainer width="100%" height={160}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="rgba(255,255,255,0.06)" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fill: '#8b99b8', fontSize: 10 }}
            />
            <Radar
              name="Score"
              dataKey="score"
              stroke="#6382ff"
              fill="#6382ff"
              fillOpacity={0.2}
              strokeWidth={2}
            />
            <Tooltip
              contentStyle={{ background: '#0d1525', border: '1px solid rgba(99,130,255,0.3)', borderRadius: '8px', fontSize: '12px' }}
              formatter={(val) => [`${val}%`, '']}
            />
          </RadarChart>
        </ResponsiveContainer>

        <div className="confidence-grid">
          {metrics.map(m => {
            const val = confidence[m.key] || 0
            const color = METRIC_COLORS[m.key]
            return (
              <div key={m.key} className="confidence-metric">
                <span className="metric-label">{m.label}</span>
                <div className="metric-bar-track">
                  <div
                    className="metric-bar-fill"
                    style={{ width: `${val * 100}%`, background: color }}
                  />
                </div>
                <span className="metric-value" style={{ color, fontSize: '14px' }}>
                  {(val * 100).toFixed(0)}%
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
