import { useRef, type RefObject } from "react";
import { useThree } from "@react-three/fiber";
import { gsap, useGSAP, MOTION, prefersReducedMotion } from "../../lib/gsap";

interface CameraRigProps {
  /** OrbitControls instance ref (from drei). */
  controlsRef: RefObject<any>;
  /** Desired camera position for the active view. */
  cameraPos: [number, number, number];
  /** Desired orbit target. */
  target?: [number, number, number];
  /** Whether OrbitControls should auto-rotate once the move settles. */
  autoRotate?: boolean;
}

/**
 * Smoothly tweens the camera + orbit target when the active view changes, so
 * switching scenes reads as spatial continuity (not a hard cut). Auto-rotate is
 * paused during the tween and restored on completion.
 */
export function CameraRig({ controlsRef, cameraPos, target = [0, 0, 0], autoRotate = false }: CameraRigProps) {
  const camera = useThree((s) => s.camera);
  const tl = useRef<gsap.core.Timeline | null>(null);

  useGSAP(
    () => {
      const controls = controlsRef.current;
      if (!controls) return;

      const dest = { x: cameraPos[0], y: cameraPos[1], z: cameraPos[2] };
      const tgt = { x: target[0], y: target[1], z: target[2] };

      if (prefersReducedMotion()) {
        camera.position.set(dest.x, dest.y, dest.z);
        controls.target.set(tgt.x, tgt.y, tgt.z);
        controls.autoRotate = autoRotate;
        controls.update();
        return;
      }

      controls.autoRotate = false;
      tl.current?.kill();
      const t = gsap.timeline({
        onComplete: () => {
          controls.autoRotate = autoRotate;
        },
      });
      t.to(
        camera.position,
        { ...dest, duration: 0.9, ease: MOTION.easeCamera, onUpdate: () => controls.update() },
        0,
      );
      t.to(
        controls.target,
        { ...tgt, duration: 0.9, ease: MOTION.easeCamera, onUpdate: () => controls.update() },
        0,
      );
      tl.current = t;
    },
    {
      dependencies: [cameraPos[0], cameraPos[1], cameraPos[2], target[0], target[1], target[2], autoRotate],
    },
  );

  return null;
}
