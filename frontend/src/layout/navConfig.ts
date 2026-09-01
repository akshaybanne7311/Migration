export interface NavItem {
  label: string;
  path: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { label: "Dashboard", path: "/" },
      { label: "Upload", path: "/upload" },
      { label: "Sessions", path: "/sessions" },
    ],
  },
  {
    label: "Configuration",
    items: [
      { label: "VIPs", path: "/vips" },
      { label: "Pools", path: "/pools" },
      { label: "Nodes", path: "/nodes" },
      { label: "System Config", path: "/system-config" },
      { label: "F5 GUI Preview", path: "/f5-gui" },
    ],
  },
  {
    label: "Migration",
    items: [
      { label: "Smart Migration", path: "/smart-migration" },
      { label: "Change Set", path: "/change-set" },
      { label: "TMSH Generator", path: "/tmsh-generator" },
      { label: "Export", path: "/export" },
    ],
  },
  {
    label: "Analysis",
    items: [
      { label: "Search", path: "/search" },
      { label: "Dependencies", path: "/dependencies" },
      { label: "Compare", path: "/compare" },
    ],
  },
];

export const moreToolsGroup: NavGroup = {
  label: "More Tools",
  items: [],
};
