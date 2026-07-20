import { createElement, useRef, type CSSProperties, type ElementType, type ReactNode } from "react";
import { gsap, useGSAP, MOTION, prefersReducedMotion } from "../../lib/gsap";

interface RevealProps {
  children: ReactNode;
  className?: string;
  as?: ElementType;
  /** Stagger the direct children of this element. */
  stagger?: boolean;
  /** Stagger descendants matching this selector instead of direct children. */
  staggerSelector?: string;
  delay?: number;
  /** Rise distance in px. */
  y?: number;
  duration?: number;
  style?: CSSProperties;
}

/**
 * GSAP entrance wrapper — fades + rises content on mount. Re-mount (via a
 * changing `key`) to replay the entrance (used when switching Inspector views).
 * Reduced-motion users get content shown immediately, no transform.
 */
export function Reveal({
  children,
  className,
  as = "div",
  stagger,
  staggerSelector,
  delay = 0,
  y = 12,
  duration,
  style,
}: RevealProps) {
  const ref = useRef<HTMLElement | null>(null);

  useGSAP(
    () => {
      const el = ref.current;
      if (!el) return;
      const targets: gsap.TweenTarget = staggerSelector
        ? el.querySelectorAll(staggerSelector)
        : stagger
          ? Array.from(el.children)
          : el;

      if (prefersReducedMotion()) {
        gsap.set(targets, { opacity: 1, y: 0, clearProps: "transform" });
        return;
      }

      gsap.from(targets, {
        opacity: 0,
        y,
        duration: duration ?? MOTION.enter,
        ease: MOTION.ease,
        delay,
        stagger: stagger || staggerSelector ? MOTION.stagger : 0,
      });
    },
    { scope: ref },
  );

  return createElement(as, { ref, className, style }, children);
}
