export const SIZE = 5;
export const WALLS = new Set([6, 12, 23]);
export const GLIMMERS = [4, 8, 16];

export function startRun(hasPass) {
  return { tile: 20, remaining: new Set(GLIMMERS), moves: hasPass ? 11 : 8 };
}

export function canMove(run, target) {
  if (!run.moves || !run.remaining.size || target < 0 || target >= SIZE * SIZE || WALLS.has(target)) return false;
  const rowDistance = Math.abs(Math.floor(run.tile / SIZE) - Math.floor(target / SIZE));
  const columnDistance = Math.abs(run.tile % SIZE - target % SIZE);
  return rowDistance + columnDistance === 1;
}

export function move(run, target) {
  if (!canMove(run, target)) return run;
  const remaining = new Set(run.remaining);
  remaining.delete(target);
  return { tile: target, remaining, moves: run.moves - 1 };
}
