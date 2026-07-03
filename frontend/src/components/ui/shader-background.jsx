import React, { useEffect, useRef } from "react"

export default function ShaderBackground() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const gl = canvas.getContext("webgl")
    if (!gl) return

    // Vertex Shader Source
    const vsSource = `
      attribute vec2 position;
      void main() {
        gl_Position = vec4(position, 0.0, 1.0);
      }
    `

    // Fragment Shader Source - Highly vibrant, organic black-pink liquid noise with film grain
    const fsSource = `
      precision mediump float;
      uniform float u_time;
      uniform vec2 u_resolution;

      // Pseudo-random noise generator
      float rand(vec2 co) {
        return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
      }

      // Fractional Brownian Motion-like 2D noise
      float noise(vec2 p) {
        vec2 ip = floor(p);
        vec2 fp = fract(p);
        float d00 = rand(ip);
        float d10 = rand(ip + vec2(1.0, 0.0));
        float d01 = rand(ip + vec2(0.0, 1.0));
        float d11 = rand(ip + vec2(1.0, 1.0));
        vec2 u = fp * fp * (3.0 - 2.0 * fp);
        return mix(mix(d00, d10, u.x), mix(d01, d11, u.x), u.y);
      }

      void main() {
        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
        
        // Scale UV space for fluid coordinate mapping
        vec2 p = uv * 2.0 - 1.0;
        p.x *= u_resolution.x / u_resolution.y;

        float t = u_time * 0.18;

        // Multilayer organic wave displacements
        for(float i = 1.0; i < 4.0; i++) {
          p.x += sin(p.y * 1.6 + t * i + 0.8) * 0.38 / i;
          p.y += cos(p.x * 1.4 - t * i + 1.2) * 0.28 / i;
        }

        // Additional high-contrast blob distortion
        p.x += cos(p.y * 2.5 + t) * 0.15;
        p.y += sin(p.x * 2.2 - t) * 0.15;

        // Shape thresholds
        float blobVal = sin(p.x * 1.8) * cos(p.y * 1.8) * 0.5 + 0.5;
        blobVal += sin(p.y * 0.9 + t) * 0.25 + 0.25;
        blobVal = clamp(blobVal, 0.0, 1.0);

        // Core Glowing Paint & Metal Shades
        vec3 deepBlack = vec3(0.0, 0.0, 0.0);
        vec3 neonPink = vec3(1.0, 0.0, 0.52); // #ff0085 (Super bright magenta)
        vec3 violetPink = vec3(0.83, 0.27, 0.94); // #d444ef
        vec3 secondaryBlue = vec3(0.12, 0.56, 1.0); // Neon cyan highlight for contrast

        // Create high-contrast glowing fluid boundaries
        vec3 col = mix(deepBlack, violetPink, smoothstep(0.32, 0.72, blobVal));
        col = mix(col, neonPink, smoothstep(0.55, 0.92, blobVal));
        
        // Add neon blue-violet secondary accents at specific thresholds
        float accentTrack = 1.0 - smoothstep(0.0, 0.18, abs(blobVal - 0.48));
        col += secondaryBlue * accentTrack * 0.15;

        // Add a bright wave highlight along borders
        float highlight = 1.0 - smoothstep(0.0, 0.09, abs(blobVal - 0.62));
        col += neonPink * highlight * 0.35;

        // Add a premium granular film noise overlay (dithered look)
        float grain = (rand(uv + fract(u_time * 0.02)) - 0.5) * 0.075;
        col += vec3(grain);

        gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
      }
    `

    // Create shader logic
    const createShader = (gl, type, source) => {
      const shader = gl.createShader(type)
      gl.shaderSource(shader, source)
      gl.compileShader(shader)
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error("Shader compilation error:", gl.getShaderInfoLog(shader))
        gl.deleteShader(shader)
        return null
      }
      return shader
    }

    const vertexShader = createShader(gl, gl.VERTEX_SHADER, vsSource)
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fsSource)
    if (!vertexShader || !fragmentShader) return

    const program = gl.createProgram()
    gl.attachShader(program, vertexShader)
    gl.attachShader(program, fragmentShader)
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error("Program linking error:", gl.getProgramInfoLog(program))
      return
    }

    // Quad coordinates
    const vertices = new Float32Array([
      -1, -1,
       1, -1,
      -1,  1,
      -1,  1,
       1, -1,
       1,  1,
    ])

    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW)

    const positionLoc = gl.getAttribLocation(program, "position")
    gl.enableVertexAttribArray(positionLoc)
    gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0)

    gl.useProgram(program)

    const timeLoc = gl.getUniformLocation(program, "u_time")
    const resolutionLoc = gl.getUniformLocation(program, "u_resolution")

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width
      canvas.height = rect.height
      gl.viewport(0, 0, canvas.width, canvas.height)
      gl.uniform2f(resolutionLoc, canvas.width, canvas.height)
    }
    resize()
    window.addEventListener("resize", resize)

    let animId
    const render = (time) => {
      gl.uniform1f(timeLoc, time * 0.001)
      gl.drawArrays(gl.TRIANGLES, 0, 6)
      animId = requestAnimationFrame(render)
    }
    animId = requestAnimationFrame(render)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener("resize", resize)
      gl.deleteBuffer(buffer)
      gl.deleteProgram(program)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none select-none"
      style={{ display: "block" }}
    />
  )
}
