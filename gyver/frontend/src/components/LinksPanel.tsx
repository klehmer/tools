import { useEffect, useRef, useState } from "react";
import { ExternalLink, Link2, Pencil, Plus, Trash2 } from "lucide-react";
import type { Link } from "../types";
import { getLinks, createLink, updateLink, deleteLink } from "../services/api";

function ensureProtocol(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  return `https://${url}`;
}

function faviconUrl(url: string): string | null {
  try {
    const u = new URL(url);
    return `${u.origin}/favicon.ico`;
  } catch {
    return null;
  }
}

function displayHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export default function LinksPanel() {
  const [links, setLinks] = useState<Link[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUrl, setEditUrl] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const urlInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchLinks();
  }, []);

  useEffect(() => {
    if (adding && urlInputRef.current) urlInputRef.current.focus();
  }, [adding]);

  const fetchLinks = async () => {
    setLoading(true);
    try {
      setLinks(await getLinks());
    } catch {
      setLinks([]);
    }
    setLoading(false);
  };

  const handleAdd = async () => {
    const url = ensureProtocol(newUrl.trim());
    if (!newUrl.trim()) return;
    const title = newTitle.trim() || displayHost(url);
    const link = await createLink(url, title);
    setLinks((prev) => [link, ...prev]);
    setNewUrl("");
    setNewTitle("");
    setAdding(false);
  };

  const handleSave = async (link: Link) => {
    const url = editUrl.trim() ? ensureProtocol(editUrl.trim()) : link.url;
    const title = editTitle.trim() || link.title;
    if (url === link.url && title === link.title) {
      setEditingId(null);
      return;
    }
    const updated = await updateLink(link.id, { url, title });
    setLinks((prev) => prev.map((l) => (l.id === link.id ? updated : l)));
    setEditingId(null);
  };

  const handleDelete = async (id: string) => {
    await deleteLink(id);
    setLinks((prev) => prev.filter((l) => l.id !== id));
    if (editingId === id) setEditingId(null);
  };

  if (loading) return <p className="text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-800">Links</h2>
        <button
          onClick={() => { setAdding(true); setNewUrl(""); setNewTitle(""); }}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus size={16} />
          Add Link
        </button>
      </div>

      {/* Add form */}
      {adding && (
        <div className="bg-white border-2 border-indigo-300 rounded-xl p-4 shadow-sm space-y-3">
          <input
            ref={urlInputRef}
            type="url"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
              if (e.key === "Escape") setAdding(false);
            }}
            placeholder="https://..."
            className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          />
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
              if (e.key === "Escape") setAdding(false);
            }}
            placeholder="Title (optional, auto-detected from URL)"
            className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={handleAdd}
              className="px-3 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Add
            </button>
            <button
              onClick={() => setAdding(false)}
              className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Links list */}
      {links.length === 0 && !adding && (
        <div className="text-center py-12 text-slate-400">
          <Link2 size={40} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No bookmarked links yet. Add one to get started.</p>
        </div>
      )}

      <div className="space-y-2">
        {links.map((link) => {
          const isEditing = editingId === link.id;
          const favicon = faviconUrl(link.url);

          if (isEditing) {
            return (
              <div
                key={link.id}
                className="bg-white border-2 border-indigo-300 rounded-xl p-4 shadow-sm space-y-3"
              >
                <input
                  type="url"
                  value={editUrl}
                  onChange={(e) => setEditUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSave(link);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-indigo-400"
                  autoFocus
                />
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSave(link);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  placeholder="Title"
                  className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-indigo-400"
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleSave(link)}
                    className="px-3 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            );
          }

          return (
            <div
              key={link.id}
              className="group flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-3 hover:border-slate-300 transition-colors"
            >
              {favicon && (
                <img
                  src={favicon}
                  alt=""
                  className="w-4 h-4 flex-shrink-0"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              )}
              <div className="flex-1 min-w-0">
                <a
                  href={ensureProtocol(link.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:underline truncate block"
                >
                  {link.title || displayHost(link.url)}
                  <ExternalLink size={12} className="inline ml-1 opacity-50" />
                </a>
                <span className="text-[11px] text-slate-400 truncate block">{link.url}</span>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                <button
                  onClick={() => {
                    setEditingId(link.id);
                    setEditUrl(link.url);
                    setEditTitle(link.title);
                  }}
                  className="p-1.5 text-slate-300 hover:text-indigo-600 transition-colors"
                  title="Edit"
                >
                  <Pencil size={14} />
                </button>
                <button
                  onClick={() => handleDelete(link.id)}
                  className="p-1.5 text-slate-300 hover:text-red-500 transition-colors"
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
