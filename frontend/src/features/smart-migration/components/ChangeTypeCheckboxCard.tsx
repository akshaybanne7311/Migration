import type { ReactNode } from "react";
import { Card, Checkbox } from "../../../components/ui";

export function ChangeTypeCheckboxCard({
  label,
  checked,
  onToggle,
  children,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
  children?: ReactNode;
}) {
  return (
    <Card className="p-4">
      <Checkbox checked={checked} onChange={onToggle} label={<span className="font-medium">{label}</span>} />
      {checked && children && <div className="mt-3 pl-6">{children}</div>}
    </Card>
  );
}

export function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block mb-2">
      <span className="text-xs text-slate-500">{label}</span>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full border border-slate-300 rounded-md px-2.5 py-1.5 text-sm"
      />
    </label>
  );
}
