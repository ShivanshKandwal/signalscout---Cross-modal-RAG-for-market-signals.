import { ShaderGradientCanvas, ShaderGradient } from "@shadergradient/react"

export default function ShaderBackground() {
  return (
    <ShaderGradientCanvas
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
      pixelDensity={1.2}
      fov={45}
    >
      <ShaderGradient
        control="props"
        color1="#000000"
        color2="#ff0085"
        color3="#d444ef"
        animate="on"
        cDistance={28}
        cPolarAngle={115}
        cAzimuthAngle={180}
        type="plane"
        grain="on"
        grainBlending={0.08}
        brightness={1.5}
        dampingFactor={0.08}
      />
    </ShaderGradientCanvas>
  )
}
