import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useSessionStore } from "../api/queries";
import { Button, Card, PageHeader } from "../components/ui";
import { toast } from "../components/toastStore";

export function UploadPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const setCurrentSessionId = useSessionStore((s) => s.setCurrentSessionId);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.uploadSession(file);
      if (session.status === "failed") {
        setError(session.error_message ?? "Parsing failed");
        toast("error", session.error_message ?? "Parsing failed");
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setCurrentSessionId(session.id);
      toast(
        "success",
        `${session.name} parsed: ${session.vip_count} VIPs, ${session.pool_count} pools, ${session.node_count} nodes, ${session.vlan_count} VLANs`,
      );
      navigate("/sessions");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Upload configuration"
        subtitle="Upload a UCS archive, QKView, or a raw device configuration file."
      />
      <Card className="p-6">
        <input
          ref={fileRef}
          type="file"
          accept=".ucs,.qkview,.conf"
          onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)}
          className="hidden"
          id="ucs-file-input"
        />
        <label
          htmlFor="ucs-file-input"
          className="neon-btn flex items-center gap-3 border border-dashed border-slate-300 rounded-md px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors"
        >
          <span className="bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded-md shrink-0">
            Choose file
          </span>
          <span className="text-sm text-slate-500 truncate">
            {fileName ?? "No file chosen — .ucs, .qkview, or .conf"}
          </span>
        </label>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={handleUpload} disabled={busy}>
            {busy ? "Parsing…" : "Upload & parse"}
          </Button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </Card>
    </div>
  );
}
