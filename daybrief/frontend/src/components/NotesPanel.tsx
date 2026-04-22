import { useEffect, useRef, useState } from "react";
import { Archive, ChevronDown, FileText, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import type { Note } from "../types";
import { getNotes, createNote, updateNote, deleteNote } from "../services/api";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function NotesPanel() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [archivedNotes, setArchivedNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [showArchived, setShowArchived] = useState(true);
  const [viewingArchivedId, setViewingArchivedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const newTitleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchAll();
  }, []);

  useEffect(() => {
    if (creating && newTitleRef.current) newTitleRef.current.focus();
  }, [creating]);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [active, archived] = await Promise.all([
        getNotes(false),
        getNotes(true),
      ]);
      setNotes(active);
      setArchivedNotes(archived);
    } catch {
      setNotes([]);
      setArchivedNotes([]);
    }
    setLoading(false);
  };

  const handleCreate = async () => {
    const title = newTitle.trim();
    if (!title) return;
    const note = await createNote(title);
    setNotes((prev) => [note, ...prev]);
    setNewTitle("");
    setCreating(false);
    setEditingId(note.id);
    setEditTitle(note.title);
    setEditContent(note.content);
  };

  const handleSave = async (note: Note) => {
    const title = editTitle.trim() || note.title;
    const content = editContent;
    if (title === note.title && content === note.content) {
      setEditingId(null);
      return;
    }
    const updated = await updateNote(note.id, { title, content });
    setNotes((prev) => prev.map((n) => (n.id === note.id ? updated : n)));
    setEditingId(null);
  };

  const handleArchive = async (note: Note) => {
    const updated = await updateNote(note.id, { archived: true });
    setNotes((prev) => prev.filter((n) => n.id !== note.id));
    setArchivedNotes((prev) => [updated, ...prev]);
    if (editingId === note.id) setEditingId(null);
  };

  const handleUnarchive = async (note: Note) => {
    const updated = await updateNote(note.id, { archived: false });
    setArchivedNotes((prev) => prev.filter((n) => n.id !== note.id));
    setNotes((prev) => [updated, ...prev]);
    setViewingArchivedId(null);
  };

  const handleDelete = async (note: Note) => {
    await deleteNote(note.id);
    setNotes((prev) => prev.filter((n) => n.id !== note.id));
    setArchivedNotes((prev) => prev.filter((n) => n.id !== note.id));
    if (editingId === note.id) setEditingId(null);
    if (viewingArchivedId === note.id) setViewingArchivedId(null);
  };

  if (loading) return <p className="text-slate-500">Loading...</p>;

  const viewingArchived = archivedNotes.find((n) => n.id === viewingArchivedId);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-800">Notes</h2>
        <button
          onClick={() => { setCreating(true); setNewTitle(""); }}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus size={16} />
          New Note
        </button>
      </div>

      {/* Create form */}
      {creating && (
        <div className="bg-white border-2 border-indigo-300 rounded-xl p-4 shadow-sm">
          <input
            ref={newTitleRef}
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreate();
              if (e.key === "Escape") setCreating(false);
            }}
            placeholder="Note title..."
            className="w-full text-lg font-semibold border-none outline-none placeholder-slate-300"
          />
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={handleCreate}
              className="px-3 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Create
            </button>
            <button
              onClick={() => setCreating(false)}
              className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Active notes */}
      {notes.length === 0 && !creating && (
        <div className="text-center py-12 text-slate-400">
          <FileText size={40} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No notes yet. Create one to get started.</p>
        </div>
      )}

      <div className="space-y-4">
        {notes.map((note) => {
          const isEditing = editingId === note.id;
          return (
            <div
              key={note.id}
              className={`bg-white border rounded-xl p-5 shadow-sm transition-all ${
                isEditing ? "border-indigo-300 ring-1 ring-indigo-200" : "border-slate-200"
              }`}
            >
              {/* Note header */}
              <div className="flex items-start justify-between gap-3 mb-2">
                {isEditing ? (
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="flex-1 text-lg font-semibold border-b-2 border-indigo-400 outline-none bg-transparent"
                    autoFocus
                  />
                ) : (
                  <h3
                    className="text-lg font-semibold text-slate-800 cursor-pointer hover:text-indigo-600"
                    onClick={() => {
                      setEditingId(note.id);
                      setEditTitle(note.title);
                      setEditContent(note.content);
                    }}
                  >
                    {note.title}
                  </h3>
                )}
                <div className="flex items-center gap-1 flex-shrink-0">
                  {!isEditing && (
                    <button
                      onClick={() => {
                        setEditingId(note.id);
                        setEditTitle(note.title);
                        setEditContent(note.content);
                      }}
                      className="p-1.5 text-slate-300 hover:text-indigo-600 transition-colors"
                      title="Edit"
                    >
                      <Pencil size={15} />
                    </button>
                  )}
                  <button
                    onClick={() => handleArchive(note)}
                    className="p-1.5 text-slate-300 hover:text-amber-600 transition-colors"
                    title="Archive"
                  >
                    <Archive size={15} />
                  </button>
                  <button
                    onClick={() => handleDelete(note)}
                    className="p-1.5 text-slate-300 hover:text-red-500 transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              {/* Timestamp */}
              <p className="text-[11px] text-slate-400 mb-3">
                Updated {timeAgo(note.updated_at)} &middot; Created {timeAgo(note.created_at)}
              </p>

              {/* Note content */}
              {isEditing ? (
                <div>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={8}
                    className="w-full text-sm text-slate-700 border border-slate-200 rounded-lg p-3 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200 resize-y"
                    placeholder="Write your note..."
                  />
                  <div className="flex items-center gap-2 mt-3">
                    <button
                      onClick={() => handleSave(note)}
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
              ) : (
                <div
                  className="text-sm text-slate-600 whitespace-pre-wrap cursor-pointer"
                  onClick={() => {
                    setEditingId(note.id);
                    setEditTitle(note.title);
                    setEditContent(note.content);
                  }}
                >
                  {note.content || (
                    <span className="text-slate-300 italic">Click to add content...</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Archived notes */}
      {archivedNotes.length > 0 && (
        <div className="border-t border-slate-200 pt-6">
          <button
            onClick={() => setShowArchived(!showArchived)}
            className="flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-700 mb-3"
          >
            <Archive size={15} />
            <ChevronDown
              size={14}
              className={`transition-transform ${showArchived ? "" : "-rotate-90"}`}
            />
            Archived ({archivedNotes.length})
          </button>

          {showArchived && (
            <div className="space-y-1">
              {archivedNotes.map((note) => (
                <div key={note.id}>
                  <div
                    className="group flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-50 cursor-pointer"
                    onDoubleClick={() =>
                      setViewingArchivedId(viewingArchivedId === note.id ? null : note.id)
                    }
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-slate-600 truncate block">
                        {note.title}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        Archived {timeAgo(note.updated_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleUnarchive(note); }}
                        className="p-1 text-slate-400 hover:text-indigo-600 transition-colors"
                        title="Unarchive"
                      >
                        <RotateCcw size={14} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(note); }}
                        className="p-1 text-slate-400 hover:text-red-500 transition-colors"
                        title="Delete permanently"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Expanded archived note view */}
                  {viewingArchivedId === note.id && (
                    <div className="mx-3 mb-2 p-4 bg-slate-50 border border-slate-200 rounded-lg">
                      <h4 className="font-semibold text-slate-700 mb-1">{note.title}</h4>
                      <p className="text-[11px] text-slate-400 mb-2">
                        Updated {timeAgo(note.updated_at)} &middot; Created {timeAgo(note.created_at)}
                      </p>
                      <div className="text-sm text-slate-600 whitespace-pre-wrap">
                        {note.content || <span className="italic text-slate-400">No content</span>}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
