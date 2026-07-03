import * as React from "react"
import { cn } from "../../lib/utils"

export const PALETTES = {
  colorful: {
    dark: {
      h: [
        { color: [255, 50, 100], op: 0.38 },
        { color: [40, 180, 220], op: 0.35 },
        { color: [50, 200, 80], op: 0.38 },
        { color: [180, 40, 240], op: 0.35 },
        { color: [255, 160, 30], op: 0.38 },
        { color: [100, 70, 255], op: 0.35 },
      ],
      v: [
        { color: [40, 140, 255], op: 0.38 },
        { color: [240, 50, 180], op: 0.35 },
        { color: [30, 185, 170], op: 0.38 },
        { color: [255, 120, 40], op: 0.38 },
        { color: [100, 70, 255], op: 0.35 },
        { color: [50, 200, 80], op: 0.38 },
      ],
    },
  },
}

function useBeamCanvas(canvasRef, config) {
  const animRef = React.useRef(null)
  const startRef = React.useRef(null)

  React.useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    
    const ctx = canvas.getContext("2d", { alpha: true })
    if (!ctx) return
    
    const dpr = window.devicePixelRatio || 1

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    startRef.current = performance.now()

    const draw = (now) => {
      const {
        rows,
        cols,
        palette,
        active,
        duration,
        strength,
        breathe,
      } = config.current
      const rect = canvas.getBoundingClientRect()
      const w = rect.width
      const h = rect.height
      ctx.clearRect(0, 0, w, h)

      if (!active) {
        animRef.current = requestAnimationFrame(draw)
        return
      }

      const elapsed = (now - (startRef.current ?? now)) / 1000
      let fade = 1
      const cellW = w / cols
      const cellH = h / rows
      const gs = fade * strength
      const br = breathe
        ? 0.85 + 0.3 * Math.sin(elapsed * 1.4) + 0.1 * Math.sin(elapsed * 2.3)
        : 1

      const rgba = (r, g, b, a) =>
        `rgba(${r},${g},${b},${Math.max(0, a).toFixed(4)})`

      for (let r = 1; r < rows; r++) {
        const y = r * cellH
        const pal = palette.h[r % palette.h.length]
        const [cr, cg, cb] = pal.color
        const op = pal.op
        const speed = 1 + (r % 3) * 0.12
        const offset = r * 0.21 + (r % 2) * 0.35
        const t = ((elapsed * speed) / duration + offset) % 1
        const x = t * w

        const bloomLen = cellW * 0.6 * br
        const bloomH = 4
        const bloomGrad = ctx.createRadialGradient(x, y, 0, x, y, bloomLen)
        bloomGrad.addColorStop(0, rgba(cr, cg, cb, op * 0.3 * gs))
        bloomGrad.addColorStop(0.4, rgba(cr, cg, cb, op * 0.12 * gs))
        bloomGrad.addColorStop(1, "transparent")
        ctx.save()
        ctx.scale(1, bloomH / bloomLen)
        ctx.fillStyle = bloomGrad
        ctx.beginPath()
        ctx.arc(x, (y * bloomLen) / bloomH, bloomLen, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()

        const coreLen = cellW * 0.55 * br
        const lineGrad = ctx.createLinearGradient(x - coreLen, y, x + coreLen, y)
        lineGrad.addColorStop(0, "transparent")
        lineGrad.addColorStop(0.12, rgba(cr, cg, cb, op * 0.4 * gs))
        lineGrad.addColorStop(0.35, rgba(Math.min(255, cr + 60), Math.min(255, cg + 60), Math.min(255, cb + 60), op * 0.8 * gs))
        lineGrad.addColorStop(0.5, rgba(Math.min(255, cr + 100), Math.min(255, cg + 100), Math.min(255, cb + 100), op * 1.0 * gs))
        lineGrad.addColorStop(0.65, rgba(Math.min(255, cr + 60), Math.min(255, cg + 60), Math.min(255, cb + 60), op * 0.8 * gs))
        lineGrad.addColorStop(0.88, rgba(cr, cg, cb, op * 0.4 * gs))
        lineGrad.addColorStop(1, "transparent")
        ctx.strokeStyle = lineGrad
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(x - coreLen, y)
        ctx.lineTo(x + coreLen, y)
        ctx.stroke()
      }

      for (let c = 1; c < cols; c++) {
        const x = c * cellW
        const pal = palette.v[c % palette.v.length]
        const [cr, cg, cb] = pal.color
        const op = pal.op
        const speed = 1 + (c % 3) * 0.1
        const offset = c * 0.26 + (c % 2) * 0.4
        const t = ((elapsed * speed) / (duration * 1.2) + offset) % 1
        const y = t * h

        const bloomLen = cellH * 0.6 * br
        const bloomW = 4
        const bloomGrad = ctx.createRadialGradient(x, y, 0, x, y, bloomLen)
        bloomGrad.addColorStop(0, rgba(cr, cg, cb, op * 0.3 * gs))
        bloomGrad.addColorStop(0.4, rgba(cr, cg, cb, op * 0.12 * gs))
        bloomGrad.addColorStop(1, "transparent")
        ctx.save()
        ctx.scale(bloomW / bloomLen, 1)
        ctx.fillStyle = bloomGrad
        ctx.beginPath()
        ctx.arc((x * bloomLen) / bloomW, y, bloomLen, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()

        const coreLen = cellH * 0.55 * br
        const lineGrad = ctx.createLinearGradient(x, y - coreLen, x, y + coreLen)
        lineGrad.addColorStop(0, "transparent")
        lineGrad.addColorStop(0.12, rgba(cr, cg, cb, op * 0.4 * gs))
        lineGrad.addColorStop(0.35, rgba(Math.min(255, cr + 60), Math.min(255, cg + 60), Math.min(255, cb + 60), op * 0.8 * gs))
        lineGrad.addColorStop(0.5, rgba(Math.min(255, cr + 100), Math.min(255, cg + 100), Math.min(255, cb + 100), op * 1.0 * gs))
        lineGrad.addColorStop(0.65, rgba(Math.min(255, cr + 60), Math.min(255, cg + 60), Math.min(255, cb + 60), op * 0.8 * gs))
        lineGrad.addColorStop(0.88, rgba(cr, cg, cb, op * 0.4 * gs))
        lineGrad.addColorStop(1, "transparent")
        ctx.strokeStyle = lineGrad
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(x, y - coreLen)
        ctx.lineTo(x, y + coreLen)
        ctx.stroke()
      }

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => {
      if (animRef.current !== null) cancelAnimationFrame(animRef.current)
      ro.disconnect()
    }
  }, [canvasRef])
}

export function GridBeam({
  children,
  className,
  rows = 4,
  cols = 5,
  colorVariant = "colorful",
  active = true,
  duration = 4,
  strength = 0.5,
  breathe = true,
  ...props
}) {
  const canvasRef = React.useRef(null)
  const palette = PALETTES[colorVariant]?.dark || PALETTES.colorful.dark

  const configRef = React.useRef({
    rows,
    cols,
    palette,
    active,
    duration,
    strength,
    breathe,
  })

  configRef.current = {
    rows,
    cols,
    palette,
    active,
    duration,
    strength,
    breathe,
  }

  useBeamCanvas(canvasRef, configRef)

  return (
    <div className={cn("relative overflow-hidden w-full h-full", className)} {...props}>
      {/* SVG grid lines */}
      <svg aria-hidden className="pointer-events-none absolute inset-0 z-1 h-full w-full stroke-white/[0.04] dark:stroke-white/[0.02]" preserveAspectRatio="none">
        {Array.from({ length: rows - 1 }, (_, r) => {
          const y = `${((r + 1) / rows) * 100}%`
          return <line key={`h-${y}`} x1="0" x2="100%" y1={y} y2={y} />
        })}
        {Array.from({ length: cols - 1 }, (_, c) => {
          const x = `${((c + 1) / cols) * 100}%`
          return <line key={`v-${x}`} x1={x} x2={x} y1="0" y2="100%" />
        })}
      </svg>
      <canvas aria-hidden className="pointer-events-none absolute inset-0 z-2 h-full w-full" ref={canvasRef} />
      <div className="relative z-10 w-full h-full">{children}</div>
    </div>
  )
}
