import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useSessionStore } from "../api/queries";
import { Button, Card, PageHeader } from "../components/ui";
import { toast } from "../components/toastStore";

const ACCEPTED_EXTENSIONS = [".ucs", ".qkview", ".conf"];

function isAcceptedFile(file: File): boolean {
  const lower = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

type FileResult = {
  file: File;
  status: "pending" | "uploading" | "success" | "failed";
  detail?: string;
  sessionId?: string;
};

export function UploadPage() {
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<FileResult[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);
  const setCurrentSessionId = useSessionStore((s) => s.setCurrentSessionId);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  function pickFiles(fileList: FileList | null) {
    if (!fileList) return;
    const files = Array.from(fileList).filter(isAcceptedFile);
    if (files.length === 0) {
      toast("error", "No .ucs, .qkview, or .conf files found in that selection.");
      return;
    }
    setResults(files.map((file) => ({ file, status: "pending" })));
  }

  async function handleUploadAll() {
    if (results.length === 0) return;
    setBusy(true);
    let successCount = 0;
    let lastSuccessId: string | null = null;

    for (let i = 0; i < results.length; i++) {
      setResults((prev) =>
        prev.map((r, idx) => (idx === i ? { ...r, status: "uploading" } : r)),
      );
      try {
        const session = await api.uploadSession(results[i].file);
        if (session.status === "failed") {
          setResults((prev) =>
            prev.map((r, idx) =>
              idx === i
                ? { ...r, status: "failed", detail: session.error_message ?? "Parsing failed" }
                : r,
            ),
          );
          continue;
        }
        successCount++;
        lastSuccessId = session.id;
        setResults((prev) =>
          prev.map((r, idx) =>
            idx === i
              ? {
                  ...r,
                  status: "success",
                  sessionId: session.id,
                  detail: `${session.vip_count} VIPs, ${session.pool_count} pools, ${session.node_count} nodes, ${session.vlan_count} VLANs`,
                }
              : r,
          ),
        );
      } catch (e) {
        setResults((prev) =>
          prev.map((r, idx) =>
            idx === i
              ? { ...r, status: "failed", detail: e instanceof Error ? e.message : "Upload failed" }
              : r,
          ),
        );
      }
    }

    queryClient.invalidateQueries({ queryKey: ["sessions"] });
    setBusy(false);

    if (successCount === 0) {
      toast("error", "All uploads failed to parse.");
      return;
    }
    toast(
      successCount === results.length ? "success" : "info",
      `${successCount}/${results.length} file(s) parsed successfully.`,
    );
    if (lastSuccessId) {
      setCurrentSessionId(lastSuccessId);
    }
    if (successCount === results.length) {
      navigate("/sessions");
    }
  }

  function clearSelection() {
    setResults([]);
    if (fileRef.current) fileRef.current.value = "";
    if (folderRef.current) folderRef.current.value = "";
  }

  const summaryText =
    results.length === 0
      ? "No files chosen — .ucs, .qkview, or .conf"
      : `${results.length} file${results.length === 1 ? "" : "s"} selected`;

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Upload configuration"
        subtitle="Upload one or more UCS archives, QKViews, or raw device configuration files — or an entire folder of them."
      />
      <Card className="p-6">
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".ucs,.qkview,.conf"
          onChange={(e) => pickFiles(e.target.files)}
          className="hidden"
          id="ucs-file-input"
        />
        <input
          ref={folderRef}
          type="file"
          multiple
          // @ts-expect-error non-standard attribute for folder selection (Chromium/Edge)
          webkitdirectory=""
          onChange={(e) => pickFiles(e.target.files)}
          className="hidden"
          id="ucs-folder-input"
        />
        <div className="flex items-center gap-3 border border-dashed border-slate-300 rounded-md px-4 py-3">
          <label
            htmlFor="ucs-file-input"
            className="neon-btn bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded-md shrink-0 cursor-pointer"
          >
            Choose file(s)
          </label>
          <label
            htmlFor="ucs-folder-input"
            className="neon-btn bg-slate-600 text-white text-xs font-medium px-3 py-1.5 rounded-md shrink-0 cursor-pointer"
          >
            Choose folder
          </label>
          <span className="text-sm text-slate-500 truncate">{summaryText}</span>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <Button onClick={handleUploadAll} disabled={busy || results.length === 0}>
            {busy ? "Parsing…" : `Upload & parse${results.length > 1 ? " all" : ""}`}
          </Button>
          {results.length > 0 && (
            <Button variant="ghost" onClick={clearSelection} disabled={busy}>
              Clear
            </Button>
          )}
        </div>

        {results.length > 0 && (
          <ul className="mt-5 divide-y divide-slate-100 border border-slate-100 rounded-md overflow-hidden">
            {results.map((r, idx) => (
              <li key={idx} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <span className="truncate text-slate-700">{r.file.name}</span>
                <span
                  className={`text-xs shrink-0 px-2 py-0.5 rounded border ${
                    r.status === "success"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : r.status === "failed"
                        ? "bg-red-50 text-red-700 border-red-200"
                        : r.status === "uploading"
                          ? "bg-blue-50 text-blue-700 border-blue-200"
                          : "bg-slate-50 text-slate-500 border-slate-200"
                  }`}
                  title={r.detail}
                >
                  {r.status === "pending" ? "queued" : r.status}
                </span>
              </li>
            ))}
          </ul>
        )}
        {results.some((r) => r.status === "failed") && (
          <div className="mt-2 text-xs text-red-600 space-y-1">
            {results
              .filter((r) => r.status === "failed")
              .map((r, i) => (
                <div key={i}>
                  {r.file.name}: {r.detail}
                </div>
              ))}
          </div>
        )}
      </Card>
    </div>
  );
}
