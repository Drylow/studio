/** Reserve water from actual animated volumes before placing solid terrain. */
export function buildSwimClearance(THREE, animals, placeAnimals, cameraPosition, {
  duration = 24, sampleHz = 30, margin = .40,
} = {}) {
  const zones = [], roots = [animals.angler, animals.jelly, animals.fishSchool];
  const frames = Math.ceil(duration * sampleHz);
  for (let frame = 0; frame <= frames; frame++) {
    const t = Math.min(duration, frame / sampleHz);
    placeAnimals(t);
    for (const root of roots) {
      root.updateWorldMatrix(true, true);
      // Precise mode reads current deformed vertices, including fins and lure.
      zones.push(new THREE.Box3().setFromObject(root, true).expandByScalar(margin));
    }
    const camera = cameraPosition(t);
    zones.push(new THREE.Box3(camera.clone(), camera.clone()).expandByScalar(.55));
  }
  placeAnimals(0);
  return {
    intersects: bounds => zones.some(zone => zone.intersectsBox(bounds)),
    summary: { duration, sampleHz, margin, samples: frames + 1, reservedVolumes: zones.length },
  };
}
