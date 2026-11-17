"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

function OrganicWaveMesh() {
  const meshRef = useRef<THREE.Mesh>(null);

  const geometry = useMemo(() => {
    const geo = new THREE.PlaneGeometry(18, 12, 44, 28);
    geo.rotateX(-Math.PI * 0.34);
    return geo;
  }, []);

  const initialPositions = useMemo(() => {
    const pos = geometry.attributes.position as THREE.BufferAttribute;
    return Float32Array.from(pos.array as Float32Array);
  }, [geometry]);

  useFrame(({ clock }) => {
    const mesh = meshRef.current;
    if (!mesh) return;

    const time = clock.getElapsedTime() * 0.22;
    const pos = mesh.geometry.attributes.position as THREE.BufferAttribute;
    const arr = pos.array as Float32Array;

    for (let i = 0; i < pos.count; i++) {
      const ix = i * 3;
      const x = initialPositions[ix];
      const y = initialPositions[ix + 1];
      const z = initialPositions[ix + 2];

      const waveA = Math.sin(x * 0.4 + time) * 0.32;
      const waveB = Math.cos(z * 0.35 - time * 0.8) * 0.22;
      arr[ix + 1] = y + waveA + waveB;
    }

    pos.needsUpdate = true;
    mesh.rotation.z = Math.sin(time * 0.2) * 0.025;
  });

  return (
    <mesh ref={meshRef} geometry={geometry} position={[0, -1.4, -2.5]}>
      <meshStandardMaterial
        color="#c8d6cb"
        wireframe
        transparent
        opacity={0.35}
        roughness={0.7}
        metalness={0.1}
      />
    </mesh>
  );
}

export function BackgroundScene() {
  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 -z-10 pointer-events-none bg-[#F7F7F5]"
    >
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 55% at 50% 0%, rgba(92, 138, 103, 0.06), transparent 70%)",
        }}
      />
      <Canvas
        camera={{ position: [0, 1.8, 6.2], fov: 42 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      >
        <ambientLight intensity={0.85} />
        <directionalLight position={[4, 6, 4]} intensity={0.6} color="#ffffff" />
        <OrganicWaveMesh />
      </Canvas>
    </div>
  );
}
