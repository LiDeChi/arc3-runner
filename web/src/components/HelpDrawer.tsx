import { X } from 'lucide-react'

interface HelpDrawerProps {
  open: boolean
  onClose: () => void
}

export function HelpDrawer({ open, onClose }: HelpDrawerProps) {
  if (!open) return null

  return (
    <div className="help-overlay" role="presentation" onMouseDown={onClose}>
      <aside className="help-drawer" role="dialog" aria-modal="true" aria-label="界面导览" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span className="section-label">GUIDE</span>
            <h2>界面导览</h2>
          </div>
          <button onClick={onClose} aria-label="关闭界面导览"><X size={15} /></button>
        </header>
        <section>
          <h3>运行模式</h3>
          <ol>
            <li>在顶栏选择一个环境方块，当前环境就是要运行的对象。</li>
            <li>策略选择 Transform-Aware，运行后会记录函数假设、想象帧、惊奇与可信度。</li>
            <li>在时间线选择任意一步，先看右侧“本步决策”卡片。</li>
            <li>点击“假设”页签查看全部动作函数表与向量示意。</li>
            <li>红色 tick 或红点代表预测失误，打开“想象”对比看 BEFORE / IMAGINED / ACTUAL。</li>
          </ol>
        </section>
        <section>
          <h3>训练模式</h3>
          <ol>
            <li>切到训练模式，先设世代数、每代局数和陷阱类型。</li>
            <li>开始训练后看通关率、预测精确度、ECE 和 fool_score 曲线。</li>
            <li>点击世代进入 episode，再选单步查看假设变化和惊奇峰值。</li>
            <li>知识库页用于检查学到的 `T(0,-1)` 这类先验和校准曲线。</li>
            <li>校准页用对角线判断 agent 声称置信度是否可靠。</li>
          </ol>
        </section>
      </aside>
    </div>
  )
}
