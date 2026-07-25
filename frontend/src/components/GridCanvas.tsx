import { useEffect, useMemo, useRef } from "react";
import type { Grid } from "../types";

export const TILE_PALETTE = [
  "#000000",
  "#0074D9",
  "#FF4136",
  "#2ECC40",
  "#FFDC00",
  "#AAAAAA",
  "#F012BE",
  "#FF851B",
  "#7FDBFF",
  "#870C25",
  "#4B0082",
  "#2F4F4F",
  "#8B4513",
  "#556B2F",
  "#C71585",
  "#FFFFFF"
];

export interface GridOverlay {
  ghostGrids?: Grid[];
  predictedGrid?: Grid;
  actualGrid?: Grid;
  showDiff?: boolean;
}

interface GridCanvasProps {
  grid?: Grid;
  cellSize?: number;
  overlay?: GridOverlay;
  label?: string;
  mini?: boolean;
}

function gridSize(grid?: Grid) {
  const rows = grid?.length ?? 0;
  const cols = grid?.reduce((max, row) => Math.max(max, row.length), 0) ?? 0;
  return { rows, cols };
}

function tileColor(value: number): string {
  return TILE_PALETTE[Math.abs(value) % TILE_PALETTE.length] ?? TILE_PALETTE[0];
}

export function GridCanvas({ grid, cellSize, overlay, label, mini = false }: GridCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { rows, cols } = gridSize(grid);
  const computedCell = useMemo(() => {
    if (cellSize) return cellSize;
    const maxDim = Math.max(rows, cols, 1);
    if (mini) return Math.max(5, Math.min(9, Math.floor(80 / maxDim)));
    return Math.max(8, Math.min(30, Math.floor(420 / maxDim)));
  }, [cellSize, cols, mini, rows]);

  const width = cols * computedCell;
  const height = rows * computedCell;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !grid || !rows || !cols) return;

    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(width * ratio));
    canvas.height = Math.max(1, Math.floor(height * ratio));
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#05070a";
    ctx.fillRect(0, 0, width, height);

    for (let y = 0; y < rows; y += 1) {
      for (let x = 0; x < cols; x += 1) {
        const value = grid[y]?.[x] ?? 0;
        ctx.fillStyle = tileColor(value);
        ctx.fillRect(x * computedCell, y * computedCell, computedCell, computedCell);
        ctx.strokeStyle = "rgba(255,255,255,0.08)";
        ctx.lineWidth = 1;
        ctx.strokeRect(x * computedCell + 0.5, y * computedCell + 0.5, computedCell - 1, computedCell - 1);
      }
    }

    for (const [index, ghost] of overlay?.ghostGrids?.entries() ?? []) {
      const alpha = Math.min(0.42, 0.16 + index * 0.08);
      for (let y = 0; y < rows; y += 1) {
        for (let x = 0; x < cols; x += 1) {
          const value = ghost[y]?.[x] ?? 0;
          if (value !== 0 && value !== (grid[y]?.[x] ?? 0)) {
            ctx.fillStyle = tileColor(value);
            ctx.globalAlpha = alpha;
            ctx.fillRect(x * computedCell, y * computedCell, computedCell, computedCell);
            ctx.globalAlpha = 1;
          }
        }
      }
    }

    if (overlay?.showDiff && overlay.predictedGrid && overlay.actualGrid) {
      for (let y = 0; y < rows; y += 1) {
        for (let x = 0; x < cols; x += 1) {
          const predicted = overlay.predictedGrid[y]?.[x] ?? 0;
          const actual = overlay.actualGrid[y]?.[x] ?? 0;
          if (predicted !== actual) {
            ctx.fillStyle = "rgba(255, 61, 80, 0.52)";
            ctx.fillRect(x * computedCell, y * computedCell, computedCell, computedCell);
          } else if (actual !== 0) {
            ctx.fillStyle = "rgba(46, 204, 64, 0.22)";
            ctx.fillRect(x * computedCell, y * computedCell, computedCell, computedCell);
          }
        }
      }
    }
  }, [cols, computedCell, grid, height, overlay, rows, width]);

  if (!grid || rows === 0 || cols === 0) {
    return <div className={`grid-empty ${mini ? "grid-empty-mini" : ""}`}>No grid</div>;
  }

  return (
    <figure className={`grid-canvas-wrap ${mini ? "grid-canvas-mini" : ""}`}>
      <div className="grid-scroll">
        <canvas ref={canvasRef} aria-label={label ?? "ARC grid"} />
      </div>
      {label ? <figcaption>{label}</figcaption> : null}
    </figure>
  );
}
