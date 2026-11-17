"use client";

import { ReactNode } from "react";
import { ReactLenis } from "lenis/react";

interface SmoothScrollProps {
  children: ReactNode;
}

export function SmoothScroll({ children }: SmoothScrollProps) {
  return (
    <ReactLenis
      root
      options={{
        lerp: 0.085,
        duration: 1.25,
        smoothWheel: true,
      }}
    >
      {children}
    </ReactLenis>
  );
}
