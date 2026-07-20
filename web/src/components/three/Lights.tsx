import { Environment, Lightformer } from "@react-three/drei";

/**
 * Single-hue indigo lighting rig for the premium-minimal stage. One key light,
 * a soft cool fill, and a small studio `Environment` (Lightformers) so PBR
 * materials pick up gentle reflections — no violet rim, no neon glow.
 */
export function Lights() {
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 9, 6]} intensity={1.15} color="#c7d2fe" />
      <directionalLight position={[-6, 2, -4]} intensity={0.45} color="#a5b4fc" />

      <Environment resolution={256} frames={1}>
        <Lightformer intensity={1.4} position={[0, 4, 3]} scale={[9, 4, 1]} color="#818cf8" />
        <Lightformer intensity={0.8} position={[-5, 1, 4]} scale={[4, 5, 1]} color="#a5b4fc" />
        <Lightformer intensity={0.6} position={[5, -2, 3]} scale={[4, 5, 1]} color="#6366f1" />
        <Lightformer intensity={0.5} position={[0, -4, -3]} scale={[10, 3, 1]} color="#1e293b" />
      </Environment>
    </>
  );
}
