export function createLatestRequestGuard() {
  let generation = 0;

  return {
    begin() {
      generation += 1;
      return generation;
    },
    invalidate() {
      generation += 1;
    },
    isLatest(requestGeneration: number) {
      return requestGeneration === generation;
    },
  };
}
