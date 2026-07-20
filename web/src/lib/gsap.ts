import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

// Premium-minimal motion language (per ui-ux-pro-max "standard" tier + impeccable
// anti-pattern rules): enter 220-380ms power3.out, exit ~65% of enter, stagger
// 40-50ms. NEVER use elastic / back / bounce easing — those read as "AI slop".
export const MOTION = {
  enter: 0.34,
  exit: 0.22,
  stagger: 0.045,
  ease: "power3.out",
  easeExit: "power2.in",
  easeCamera: "power2.inOut",
} as const;

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export { gsap, useGSAP };
