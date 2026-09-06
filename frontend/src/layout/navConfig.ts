import {
  LayoutDashboard,
  UploadCloud,
  FolderClock,
  Waypoints,
  Layers,
  Server,
  SlidersHorizontal,
  MonitorSmartphone,
  Wand2,
  ListChecks,
  Terminal,
  Download,
  Search,
  Share2,
  GitCompare,
  ShieldCheck,
  History,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { label: "Dashboard", path: "/", icon: LayoutDashboard },
      { label: "Upload", path: "/upload", icon: UploadCloud },
      { label: "Sessions", path: "/sessions", icon: FolderClock },
    ],
  },
  {
    label: "Configuration",
    items: [
      { label: "VIPs", path: "/vips", icon: Waypoints },
      { label: "Pools", path: "/pools", icon: Layers },
      { label: "Nodes", path: "/nodes", icon: Server },
      { label: "System Config", path: "/system-config", icon: SlidersHorizontal },
      { label: "GUI Preview", path: "/gui-preview", icon: MonitorSmartphone },
    ],
  },
  {
    label: "Migration",
    items: [
      { label: "Smart Migration", path: "/smart-migration", icon: Wand2 },
      { label: "Change Set", path: "/change-set", icon: ListChecks },
      { label: "TMSH Generator", path: "/tmsh-generator", icon: Terminal },
      { label: "Export", path: "/export", icon: Download },
    ],
  },
  {
    label: "Analysis",
    items: [
      { label: "Health Check", path: "/health-check", icon: ShieldCheck },
      { label: "Change History", path: "/change-history", icon: History },
      { label: "Search", path: "/search", icon: Search },
      { label: "Dependencies", path: "/dependencies", icon: Share2 },
      { label: "Compare", path: "/compare", icon: GitCompare },
    ],
  },
];

export const moreToolsGroup: NavGroup = {
  label: "More Tools",
  items: [],
};
