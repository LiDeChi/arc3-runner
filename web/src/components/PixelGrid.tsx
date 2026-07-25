import { useEffect, useRef } from 'react'

const palette = [
  '#08090b', '#1a1c20', '#2e3036', '#464950', '#6f737c', '#9ca0a8', '#d5d7dc',
  '#f4f4f2', '#ef3340', '#ff765f', '#f2c14e', '#32c787', '#5a86ff', '#9b6dff',
  '#22b8cf', '#d96bc2',
]

interface PixelGridProps {
  frame: number[][]
  beforeFrame?: number[][] | null
  showDiff?: boolean
  label: string
}

export function PixelGrid({ frame, beforeFrame, showDiff = false, label }: PixelGridProps) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || frame.length === 0 || frame[0].length === 0) return
    const context = canvas.getContext('2d')
    if (!context) return

    const height = frame.length
    const width = frame[0].length
    const scale = Math.max(1, Math.floor(640 / Math.max(width, height)))
    canvas.width = width * scale
    canvas.height = height * scale
    context.imageSmoothingEnabled = false

    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const value = frame[y][x] ?? 0
        context.fillStyle = palette[Math.abs(value) % palette.length]
        context.fillRect(x * scale, y * scale, scale, scale)
        if (showDiff && beforeFrame?.[y]?.[x] !== undefined && beforeFrame[y][x] !== value) {
          context.strokeStyle = '#ffffff'
          context.lineWidth = Math.max(1, scale / 8)
          context.strokeRect(x * scale + 1, y * scale + 1, scale - 2, scale - 2)
        }
      }
    }
  }, [beforeFrame, frame, showDiff])

  return <canvas ref={ref} className="pixel-grid" role="img" aria-label={label} />
}

