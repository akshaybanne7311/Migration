import { useMemo, useState } from "react";
import type { GraphNode, VipDependencyGraph } from "../api/types";

const BOX_W = 232;
const BOX_H = 40;
const V_GAP = 10;
const GROUP_GAP = 22;
const COL_GAP = 140;
const COL_VIP_X = 24;

const TYPE_STYLE: Record<string, { bg: string; border: string; fg: string }> = {
  vip: { bg: "#fef3e2", border: "#d97706", fg: "#92400e" },
  pool: { bg: "#e0f2fe", border: "#0284c7", fg: "#075985" },
  node: { bg: "#dcfce7", border: "#16a34a", fg: "#14532d" },
  vlan: { bg: "#f3e8ff", border: "#9333ea", fg: "#581c87" },
  monitor: { bg: "#ccfbf1", border: "#0d9488", fg: "#134e4a" },
  profile: { bg: "#f1f5f9", border: "#64748b", fg: "#334155" },
};

function short(name: string): string {
  return name.replace("/Common/", "");
}

function attrLine(node: GraphNode): string | null {
  const a = node.attrs;
  if (node.type === "node" && a.address) return `${a.address}${a.port ? `:${a.port}` : ""}`;
  if (node.type === "vip" && a.destination) return `${a.destination}${a.port ? `:${a.port}` : ""}`;
  if (node.type === "vlan" && a.tag !== undefined && a.tag !== null) return `tag ${a.tag}`;
  return null;
}

interface Group {
  label: string;
  items: GraphNode[];
}

interface Box {
  node: GraphNode;
  x: number;
  y: number;
}

function layoutColumn(groups: Group[], x: number): { boxes: Box[]; labelYs: { label: string; y: number }[]; height: number } {
  const boxes: Box[] = [];
  const labelYs: { label: string; y: number }[] = [];
  let y = 0;
  for (const g of groups) {
    if (g.items.length === 0) continue;
    labelYs.push({ label: g.label, y });
    y += 18;
    for (const item of g.items) {
      boxes.push({ node: item, x, y });
      y += BOX_H + V_GAP;
    }
    y += GROUP_GAP - V_GAP;
  }
  return { boxes, labelYs, height: y };
}

export function DependencyGraphView({ graph }: { graph: VipDependencyGraph }) {
  const [hovered, setHovered] = useState<string | null>(null);

  const layout = useMemo(() => {
    const midX = COL_VIP_X + BOX_W + COL_GAP;
    const rightX = midX + BOX_W + COL_GAP;

    const mid = layoutColumn(
      [
        { label: "POOL", items: graph.pools },
        { label: "VLANS", items: graph.vlans },
        { label: "MONITORS", items: graph.monitors },
        { label: "PROFILES", items: graph.profiles },
      ],
      midX,
    );
    const right = layoutColumn([{ label: "NODES (POOL MEMBERS)", items: graph.nodes }], rightX);

    const totalHeight = Math.max(mid.height, right.height, BOX_H + 40);
    const vipBox: Box = { node: graph.vip, x: COL_VIP_X, y: totalHeight / 2 - BOX_H / 2 };

    return { midX, rightX, mid, right, vipBox, totalHeight, width: rightX + BOX_W + 24 };
  }, [graph]);

  function edgesFor(targetBoxes: Box[], fromBox: Box): { from: Box; to: Box }[] {
    return targetBoxes.map((to) => ({ from: fromBox, to }));
  }

  const vipToMid = edgesFor(layout.mid.boxes, layout.vipBox);
  const poolToNode = layout.right.boxes.map((nodeBox) => {
    const poolBox = layout.mid.boxes.find((b) => b.node.type === "pool");
    return { from: poolBox ?? layout.vipBox, to: nodeBox };
  });

  function path(from: Box, to: Box): string {
    const x1 = from.x + BOX_W;
    const y1 = from.y + BOX_H / 2;
    const x2 = to.x;
    const y2 = to.y + BOX_H / 2;
    const mx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
  }

  function renderBox(b: Box) {
    const style = TYPE_STYLE[b.node.type] ?? TYPE_STYLE.profile;
    const isHovered = hovered === `${b.node.type}:${b.node.name}`;
    const line2 = attrLine(b.node);
    return (
      <g
        key={`${b.node.type}:${b.node.name}`}
        transform={`translate(${b.x}, ${b.y})`}
        onMouseEnter={() => setHovered(`${b.node.type}:${b.node.name}`)}
        onMouseLeave={() => setHovered(null)}
        style={{ cursor: "default" }}
      >
        <rect
          width={BOX_W}
          height={BOX_H}
          rx={8}
          fill={style.bg}
          stroke={style.border}
          strokeWidth={isHovered ? 2.5 : 1.5}
        />
        <text x={10} y={line2 ? 16 : 25} fontSize={12} fontWeight={600} fill={style.fg}>
          {short(b.node.name).length > 30 ? `${short(b.node.name).slice(0, 29)}…` : short(b.node.name)}
        </text>
        {line2 && (
          <text x={10} y={31} fontSize={10.5} fontFamily="monospace" fill={style.fg} opacity={0.8}>
            {line2}
          </text>
        )}
      </g>
    );
  }

  return (
    <div className="overflow-auto border border-slate-200 rounded-lg bg-white" style={{ maxHeight: 640 }}>
      <svg width={layout.width} height={layout.totalHeight + 40} style={{ minWidth: "100%" }}>
        <g transform="translate(0, 20)">
          {vipToMid.map(({ from, to }, i) => (
            <path key={`vm-${i}`} d={path(from, to)} fill="none" stroke="#cbd5e1" strokeWidth={1.5} />
          ))}
          {poolToNode.map(({ from, to }, i) => (
            <path key={`pn-${i}`} d={path(from, to)} fill="none" stroke="#cbd5e1" strokeWidth={1.5} />
          ))}

          {layout.mid.labelYs.map((l) => (
            <text key={l.label} x={layout.midX} y={l.y + 10} fontSize={10} fontWeight={700} letterSpacing={0.5} fill="#94a3b8">
              {l.label}
            </text>
          ))}
          {layout.right.labelYs.map((l) => (
            <text key={l.label} x={layout.rightX} y={l.y + 10} fontSize={10} fontWeight={700} letterSpacing={0.5} fill="#94a3b8">
              {l.label}
            </text>
          ))}

          {renderBox(layout.vipBox)}
          {layout.mid.boxes.map(renderBox)}
          {layout.right.boxes.map(renderBox)}
        </g>
      </svg>
    </div>
  );
}
