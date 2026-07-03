import { ShaderGradientCanvas, ShaderGradient } from "@shadergradient/react"

export default function ShaderBackground() {
  return (
    <ShaderGradientCanvas
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        zIndex: -2,
        pointerEvents: "none",
      }}
    >
      <ShaderGradient
        control="props"
        type="waterPlane"
        animate="on"
        color1="#ff0085"
        color2="#d444ef"
        color3="#000000"
        bgColor1="#000000"
        bgColor2="#000000"
        brightness={1.0}
        uDensity={1.2}
        uFrequency={5.5}
        uSpeed={0.12}
        grain="on"
        cDistance={3.6}
        cPolarAngle={90}
        cAzimuthAngle={180}
        cameraZoom={1.0}
      />
    </ShaderGradientCanvas>
  )
}
