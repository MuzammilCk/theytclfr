import { useRef, type CSSProperties } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "../../lib/gsap";

interface CountUpProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  style?: CSSProperties;
  duration?: number;
}

/**
 * Animated number that counts up from 0 to `value` on mount / when `value`
 * changes. Falls back to the final value for reduced-motion users and SSR.
 */
export function CountUp({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  className,
  style,
  duration,
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null);

  useGSAP(
    () => {
      const el = ref.current;
      if (!el) return;
      const fmt = (v: number) => `${prefix}${v.toFixed(decimals)}${suffix}`;
      if (prefersReducedMotion()) {
        el.textContent = fmt(value);
        return;
      }
      const proxy = { v: 0 };
      gsap.to(proxy, {
        v: value,
        duration: duration ?? 0.9,
        ease: "power2.out",
        onUpdate: () => {
          el.textContent = fmt(proxy.v);
        },
      });
    },
    { dependencies: [value], scope: ref },
  );

  return (
    <span ref={ref} className={className} style={style}>
      {`${prefix}${value.toFixed(decimals)}${suffix}`}
    </span>
  );
}
