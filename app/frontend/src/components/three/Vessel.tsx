/* Colours here are the Atlantic palette in its ON-BLUE form: the ground is
 * atlantic/deep water and the accent is sky, because sky is what the palette
 * defines as bright ink on blue. See src/utils/palette.ts.
 */
"use client";

/** Low-poly survey vessel built from primitive geometry only - no external
 * model asset is licensed for this build. Local +z is the direction the tow
 * gear trails (matches SonarSweep's z=6 offset in Scene3D), so the bow tapers
 * toward -z and the tow cable/towfish extend past the stern toward +z. */
export function Vessel() {
  return (
    <group>
      {/* Hull: flat midsection + tapered bow */}
      <mesh position={[0, 1.2, 1]}>
        <boxGeometry args={[3, 1.4, 7]} />
        <meshStandardMaterial color="#E4E7EB" roughness={0.6} metalness={0.1} />
      </mesh>
      <mesh position={[0, 1.2, -3.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <coneGeometry args={[1.55, 2.6, 4]} />
        <meshStandardMaterial color="#E4E7EB" roughness={0.6} metalness={0.1} />
      </mesh>

      {/* Bridge / deckhouse, set toward the bow like a real survey vessel */}
      <mesh position={[0, 2.4, -1.2]}>
        <boxGeometry args={[2, 1.4, 3]} />
        <meshStandardMaterial color="#0B3A58" roughness={0.5} />
      </mesh>
      <mesh position={[0, 3.05, -1.2]}>
        <boxGeometry args={[1.8, 0.1, 2.6]} />
        <meshStandardMaterial color="#072639" />
      </mesh>

      {/* Mast + radar bar + beacon */}
      <mesh position={[0, 3.7, -1.2]}>
        <cylinderGeometry args={[0.06, 0.06, 1.2, 8]} />
        <meshStandardMaterial color="#3D6C8A" />
      </mesh>
      <mesh position={[0, 4.1, -1.2]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.04, 0.04, 0.9, 6]} />
        <meshStandardMaterial color="#3D6C8A" />
      </mesh>
      <mesh position={[0, 4.4, -1.2]}>
        <sphereGeometry args={[0.14, 8, 8]} />
        <meshStandardMaterial color="#C4F8FF" emissive="#C4F8FF" emissiveIntensity={0.8} />
      </mesh>

      {/* Navigation lights: port (red, -x) / starboard (green, +x), real maritime
          convention -- deliberately NOT rethemed to the Atlantic palette. These two
          colours mean something outside this application. */}
      <mesh position={[-1.5, 1.6, -2.6]}>
        <sphereGeometry args={[0.09, 6, 6]} />
        <meshStandardMaterial color="#f87171" emissive="#f87171" emissiveIntensity={0.9} />
      </mesh>
      <mesh position={[1.5, 1.6, -2.6]}>
        <sphereGeometry args={[0.09, 6, 6]} />
        <meshStandardMaterial color="#4ade80" emissive="#4ade80" emissiveIntensity={0.9} />
      </mesh>

      {/* Tow cable + towfish, trailing aft toward the sonar swath */}
      <mesh position={[0, 0.6, 5.5]} rotation={[Math.PI / 2 - 0.05, 0, 0]}>
        <cylinderGeometry args={[0.03, 0.03, 5.2, 6]} />
        <meshStandardMaterial color="#072639" />
      </mesh>
      <mesh position={[0, 0.15, 8.1]}>
        <boxGeometry args={[0.4, 0.35, 1.3]} />
        <meshStandardMaterial color="#0F4B70" roughness={0.4} metalness={0.3} />
      </mesh>
      <mesh position={[0, 0.15, 8.75]}>
        <sphereGeometry args={[0.07, 6, 6]} />
        <meshStandardMaterial color="#C4F8FF" emissive="#C4F8FF" emissiveIntensity={1} />
      </mesh>
    </group>
  );
}
