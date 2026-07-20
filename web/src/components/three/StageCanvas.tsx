import { Suspense, useRef, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Stars, ContactShadows, AdaptiveDpr } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";
import { Lights } from "./Lights";
import { CameraRig } from "./CameraRig";

interface StageCanvasProps {
  children: ReactNode;
  camera?: [number, number, number];
  autoRotate?: boolean;
  enablePan?: boolean;
}

// Shared immersive stage: deep-ink background, a single-hue indigo key + soft
// studio reflections (no violet rim), a calm contact shadow, and a *restrained*
// bloom so only the brightest cores glow — the scene reads precise, not neon.
export function StageCanvas({
  children,
  camera = [0, 1.5, 9],
  autoRotate = false,
  enablePan = false,
}: StageCanvasProps) {
  const controlsRef = useRef<any>(null);

  return (
    <Canvas
      camera={{ position: camera, fov: 50 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
      style={{ width: "100%", height: "100%" }}
    >
      <color attach="background" args={["#06080f"]} />
      <fog attach="fog" args={["#06080f", 18, 38]} />

      <Lights />

      <Suspense fallback={null}>
        <Stars radius={70} depth={45} count={1200} factor={2.2} saturation={0} fade speed={0.3} />
        {children}
        <ContactShadows
          position={[0, -2.2, 0]}
          opacity={0.4}
          scale={26}
          blur={2.6}
          far={9}
          color="#000000"
        />
      </Suspense>

      <OrbitControls
        ref={controlsRef}
        enablePan={enablePan}
        enableDamping
        dampingFactor={0.08}
        autoRotate={autoRotate}
        autoRotateSpeed={0.45}
        minDistance={3.5}
        maxDistance={24}
      />
      <CameraRig controlsRef={controlsRef} cameraPos={camera} autoRotate={autoRotate} />

      <EffectComposer>
        <Bloom intensity={0.25} luminanceThreshold={0.55} luminanceSmoothing={0.9} mipmapBlur />
        <Vignette eskil={false} offset={0.3} darkness={0.7} />
      </EffectComposer>

      <AdaptiveDpr pixelated />
    </Canvas>
  );
}
