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
            <li>选择环境与 Transform-Aware 策略，再启动运行。</li>
            <li>“本步决策”汇总动作函数、置信度、门控和预测误差。</li>
            <li>事件详情可以展开轨迹、假设、想象帧和原始审计事件。</li>
            <li>红色惊奇提示代表预测失误，优先检查 IMAGINED 与 ACTUAL 的差异。</li>
          </ol>
        </section>
        <section>
          <h3>训练模式</h3>
          <ol>
            <li>设置世代数、每代局数和陷阱类型后启动训练。</li>
            <li>趋势图观察通关率、预测精确度、ECE 和 fool_score。</li>
            <li>选择世代和 episode，下钻查看逐步决策与惊奇峰值。</li>
            <li>可信度页的点越接近 y=x，对外声称的置信度越可靠。</li>
          </ol>
        </section>
      </aside>
    </div>
  )
}
