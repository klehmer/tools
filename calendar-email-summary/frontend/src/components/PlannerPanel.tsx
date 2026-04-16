import { useEffect, useRef, useState, type DragEvent } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  EyeOff,
  GripVertical,
  Star,
  Trash2,
} from "lucide-react";
import type { ChecklistItem } from "../types";
import {
  getChecklist,
  getConfig,
  createChecklistItem,
  updateChecklistItem,
  deleteChecklistItem,
  reorderChecklist,
} from "../services/api";

function fmt(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function startOfWeek(d: Date): Date {
  const r = new Date(d);
  r.setDate(r.getDate() - r.getDay());
  return r;
}

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const COLORS = [
  { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-800", dot: "bg-blue-400" },
  { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-800", dot: "bg-emerald-400" },
  { bg: "bg-violet-50", border: "border-violet-200", text: "text-violet-800", dot: "bg-violet-400" },
  { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-800", dot: "bg-amber-400" },
  { bg: "bg-rose-50", border: "border-rose-200", text: "text-rose-800", dot: "bg-rose-400" },
  { bg: "bg-cyan-50", border: "border-cyan-200", text: "text-cyan-800", dot: "bg-cyan-400" },
  { bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-800", dot: "bg-orange-400" },
];

const PRIORITY_COLOR = {
  bg: "bg-amber-100",
  border: "border-amber-400",
  text: "text-amber-900",
};

function itemColor(item: ChecklistItem, index: number) {
  if (item.priority) return PRIORITY_COLOR;
  return COLORS[index % COLORS.length];
}

export default function PlannerPanel({ settingsRev = 0 }: { settingsRev?: number }) {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeInput, setActiveInput] = useState<string | null>(null);
  const [newText, setNewText] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [dragItem, setDragItem] = useState<ChecklistItem | null>(null);
  const [dropTarget, setDropTarget] = useState<{ date: string; index: number } | null>(null);
  const [columnWidth, setColumnWidth] = useState(220);
  const [privateOpen, setPrivateOpen] = useState<Record<string, boolean>>({});
  const [addingPrivate, setAddingPrivate] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const todayRef = useRef<HTMLDivElement>(null);

  const weekDates = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const dateFrom = fmt(weekDates[0]);
  const dateTo = fmt(weekDates[6]);

  useEffect(() => {
    fetchItems();
  }, [weekStart]);

  useEffect(() => {
    getConfig().then((cfg) => {
      const w = parseInt(cfg.PLANNER_COLUMN_WIDTH?.value || "220", 10);
      if (w >= 160 && w <= 400) setColumnWidth(w);
    }).catch(() => {});
  }, [settingsRev]);

  useEffect(() => {
    if (activeInput && inputRef.current) inputRef.current.focus();
  }, [activeInput]);

  useEffect(() => {
    if (!loading && scrollRef.current && todayRef.current) {
      const container = scrollRef.current;
      const todayEl = todayRef.current;
      const scrollLeft = todayEl.offsetLeft - container.offsetWidth / 2 + todayEl.offsetWidth / 2;
      container.scrollTo({ left: Math.max(0, scrollLeft), behavior: "smooth" });
    }
  }, [loading]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      setItems(await getChecklist(dateFrom, dateTo));
    } catch {
      setItems([]);
    }
    setLoading(false);
  };

  const dayItems = (date: string) =>
    items.filter((i) => i.date === date && !i.private).sort((a, b) => a.sort_order - b.sort_order);

  const dayPrivateItems = (date: string) =>
    items.filter((i) => i.date === date && i.private).sort((a, b) => a.sort_order - b.sort_order);

  // ---- Add items (Enter keeps input open) ----
  const handleAdd = async (date: string) => {
    const text = newText.trim();
    if (!text) return;
    const existing = addingPrivate ? dayPrivateItems(date) : dayItems(date);
    const created = await createChecklistItem(text, date, existing.length, false, addingPrivate);
    setItems((prev) => [...prev, created]);
    setNewText("");
    // keep input open for rapid entry
  };

  const startAdding = (date: string) => {
    setActiveInput(date);
    setNewText("");
  };

  const stopAdding = () => {
    setActiveInput(null);
    setNewText("");
  };

  // ---- Toggle / Edit / Delete ----
  const handleToggle = async (item: ChecklistItem) => {
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, done: !i.done } : i)));
    await updateChecklistItem(item.id, { done: !item.done });
  };

  const handlePriority = async (item: ChecklistItem) => {
    const next = !item.priority;
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, priority: next } : i)));
    await updateChecklistItem(item.id, { priority: next });
  };

  const handleDelete = async (id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
    await deleteChecklistItem(id);
  };

  const handlePrivateToggle = async (item: ChecklistItem) => {
    const next = !item.private;
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, private: next } : i)));
    await updateChecklistItem(item.id, { private: next });
  };

  const handleEditSave = async (item: ChecklistItem) => {
    const text = editText.trim();
    if (!text || text === item.text) {
      setEditingId(null);
      return;
    }
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, text } : i)));
    setEditingId(null);
    await updateChecklistItem(item.id, { text });
  };

  // ---- Drag & Drop ----
  const onDragStart = (e: DragEvent, item: ChecklistItem) => {
    setDragItem(item);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", item.id);
  };

  const onDragOverDay = (e: DragEvent, date: string, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDropTarget({ date, index });
  };

  const onDragOverColumn = (e: DragEvent, date: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const count = dayItems(date).length;
    setDropTarget({ date, index: count });
  };

  const onDrop = async (e: DragEvent, targetDate: string, targetIndex: number) => {
    e.preventDefault();
    if (!dragItem) return;

    const movedToDifferentDay = dragItem.date !== targetDate;

    // Build new items list
    let updated = items.filter((i) => i.id !== dragItem.id);
    const movedItem = { ...dragItem, date: targetDate };

    // Get items for the target day (without the dragged item)
    const targetDayItems = updated
      .filter((i) => i.date === targetDate)
      .sort((a, b) => a.sort_order - b.sort_order);

    // Insert at target index
    targetDayItems.splice(targetIndex, 0, movedItem);

    // Reassign sort orders
    const reorderedIds: string[] = [];
    targetDayItems.forEach((item, idx) => {
      item.sort_order = idx;
      reorderedIds.push(item.id);
    });

    // Rebuild full items list
    const otherItems = updated.filter((i) => i.date !== targetDate);
    setItems([...otherItems, ...targetDayItems]);
    setDragItem(null);
    setDropTarget(null);

    // Persist
    if (movedToDifferentDay) {
      await updateChecklistItem(movedItem.id, { date: targetDate, sort_order: targetIndex });
    }
    await reorderChecklist(reorderedIds);
  };

  const onDragEnd = () => {
    setDragItem(null);
    setDropTarget(null);
  };

  // ---- Navigation ----
  const today = fmt(new Date());
  const prevWeek = () => setWeekStart(addDays(weekStart, -7));
  const nextWeek = () => setWeekStart(addDays(weekStart, 7));
  const goToday = () => setWeekStart(startOfWeek(new Date()));

  const weekLabel = (() => {
    const s = weekDates[0];
    const e = weekDates[6];
    const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
    return `${s.toLocaleDateString(undefined, opts)} \u2013 ${e.toLocaleDateString(undefined, { ...opts, year: "numeric" })}`;
  })();

  return (
    <div className="space-y-5">
      {/* Week navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={prevWeek} className="p-2 rounded-lg hover:bg-slate-100 transition-colors">
            <ChevronLeft size={20} />
          </button>
          <button onClick={nextWeek} className="p-2 rounded-lg hover:bg-slate-100 transition-colors">
            <ChevronRight size={20} />
          </button>
          <button
            onClick={goToday}
            className="text-sm px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 font-medium transition-colors"
          >
            Today
          </button>
        </div>
        <h2 className="text-xl font-bold text-slate-800">{weekLabel}</h2>
      </div>

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : (
        <div className="overflow-x-auto pb-2" ref={scrollRef}>
        <div className="flex gap-3" style={{ minWidth: `${columnWidth * 7 + 6 * 12}px` }}>
          {weekDates.map((d) => {
            const ds = fmt(d);
            const dItems = dayItems(ds);
            const isToday = ds === today;
            const isPast = ds < today;
            const isDropHere = dropTarget?.date === ds;

            return (
              <div
                key={ds}
                ref={isToday ? todayRef : undefined}
                style={{ width: columnWidth, minWidth: columnWidth }}
                className={`rounded-xl border-2 p-4 min-h-[280px] flex flex-col flex-shrink-0 transition-colors ${
                  isDropHere && dragItem
                    ? "border-indigo-400 bg-indigo-50/70"
                    : isToday
                    ? "border-indigo-400 bg-indigo-50/40"
                    : isPast
                    ? "border-slate-200 bg-slate-50/60"
                    : "border-slate-200 bg-white"
                }`}
                onDragOver={(e) => onDragOverColumn(e, ds)}
                onDrop={(e) => onDrop(e, ds, dItems.length)}
              >
                {/* Day header */}
                <div className="mb-3 pb-2 border-b border-slate-100">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    {DAY_LABELS[d.getDay()]}
                  </div>
                  <div
                    className={`text-2xl font-bold ${
                      isToday ? "text-indigo-600" : "text-slate-700"
                    }`}
                  >
                    {d.getDate()}
                  </div>
                  {dItems.length > 0 && (
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {dItems.filter((i) => i.done).length}/{dItems.length} done
                    </div>
                  )}
                </div>

                {/* Items */}
                <div className="flex-1 space-y-2">
                  {dItems.map((item, idx) => {
                    const color = itemColor(item, idx);
                    const isDropBefore =
                      dropTarget?.date === ds && dropTarget?.index === idx && dragItem?.id !== item.id;

                    return (
                      <div key={item.id}>
                        {isDropBefore && (
                          <div className="h-1 bg-indigo-400 rounded-full mb-1 mx-1" />
                        )}
                        <div
                          draggable
                          onDragStart={(e) => onDragStart(e, item)}
                          onDragEnd={onDragEnd}
                          onDragOver={(e) => onDragOverDay(e, ds, idx)}
                          onDrop={(e) => {
                            e.stopPropagation();
                            onDrop(e, ds, idx);
                          }}
                          className={`group rounded-lg border px-2.5 py-2 cursor-grab active:cursor-grabbing transition-all ${
                            item.done
                              ? "bg-slate-50 border-slate-200 opacity-60"
                              : `${color.bg} ${color.border}`
                          } ${
                            dragItem?.id === item.id ? "opacity-30 scale-95" : ""
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <GripVertical
                              size={14}
                              className="mt-0.5 text-slate-300 group-hover:text-slate-500 flex-shrink-0"
                            />
                            <input
                              type="checkbox"
                              checked={item.done}
                              onChange={() => handleToggle(item)}
                              className="mt-1 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer flex-shrink-0"
                            />
                            <div className="flex-1 min-w-0">
                              {editingId === item.id ? (
                                <input
                                  type="text"
                                  value={editText}
                                  onChange={(e) => setEditText(e.target.value)}
                                  onBlur={() => handleEditSave(item)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") handleEditSave(item);
                                    if (e.key === "Escape") setEditingId(null);
                                  }}
                                  autoFocus
                                  className="w-full text-sm font-medium border-b-2 border-indigo-400 outline-none bg-transparent"
                                />
                              ) : (
                                <span
                                  className={`text-sm font-medium leading-snug block ${
                                    item.done
                                      ? "line-through text-slate-400"
                                      : color.text
                                  }`}
                                  onDoubleClick={() => {
                                    setEditingId(item.id);
                                    setEditText(item.text);
                                  }}
                                >
                                  {item.text}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-0.5 flex-shrink-0">
                              <button
                                onClick={() => handlePrivateToggle(item)}
                                className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-300 hover:text-slate-600 transition-all"
                                title="Move to private"
                              >
                                <EyeOff size={14} />
                              </button>
                              <button
                                onClick={() => handlePriority(item)}
                                className={`p-0.5 transition-colors ${
                                  item.priority
                                    ? "text-amber-500"
                                    : "opacity-0 group-hover:opacity-100 text-slate-300 hover:text-amber-500"
                                }`}
                                title="Toggle priority"
                              >
                                <Star size={14} fill={item.priority ? "currentColor" : "none"} />
                              </button>
                              <button
                                onClick={() => handleDelete(item.id)}
                                className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-300 hover:text-red-500 transition-all"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {/* Drop indicator at end */}
                  {dropTarget?.date === ds &&
                    dropTarget.index >= dItems.length &&
                    dragItem &&
                    dragItem.date !== ds && (
                      <div className="h-1 bg-indigo-400 rounded-full mx-1" />
                    )}
                </div>

                {/* Private items accordion */}
                {(() => {
                  const pItems = dayPrivateItems(ds);
                  if (pItems.length === 0 && activeInput !== ds) return null;
                  const isOpen = privateOpen[ds] ?? false;
                  return (
                    <div className="mt-2 pt-2 border-t border-dashed border-slate-200">
                      <button
                        onClick={() => setPrivateOpen((prev) => ({ ...prev, [ds]: !isOpen }))}
                        className="flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-600 font-medium uppercase tracking-wider w-full"
                      >
                        <ChevronDown
                          size={12}
                          className={`transition-transform ${isOpen ? "" : "-rotate-90"}`}
                        />
                        <EyeOff size={11} />
                        Private{pItems.length > 0 && ` (${pItems.length})`}
                      </button>
                      {isOpen && (
                        <div className="mt-2 space-y-2">
                          {pItems.map((item, idx) => {
                            const color = itemColor(item, idx);
                            return (
                              <div
                                key={item.id}
                                draggable
                                onDragStart={(e) => onDragStart(e, item)}
                                onDragEnd={onDragEnd}
                                className={`group rounded-lg border px-2.5 py-2 cursor-grab active:cursor-grabbing transition-all ${
                                  item.done
                                    ? "bg-slate-50 border-slate-200 opacity-60"
                                    : `${color.bg} ${color.border}`
                                } ${
                                  dragItem?.id === item.id ? "opacity-30 scale-95" : ""
                                }`}
                              >
                                <div className="flex items-start gap-2">
                                  <GripVertical
                                    size={14}
                                    className="mt-0.5 text-slate-300 group-hover:text-slate-500 flex-shrink-0"
                                  />
                                  <input
                                    type="checkbox"
                                    checked={item.done}
                                    onChange={() => handleToggle(item)}
                                    className="mt-1 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer flex-shrink-0"
                                  />
                                  <div className="flex-1 min-w-0">
                                    {editingId === item.id ? (
                                      <input
                                        type="text"
                                        value={editText}
                                        onChange={(e) => setEditText(e.target.value)}
                                        onBlur={() => handleEditSave(item)}
                                        onKeyDown={(e) => {
                                          if (e.key === "Enter") handleEditSave(item);
                                          if (e.key === "Escape") setEditingId(null);
                                        }}
                                        autoFocus
                                        className="w-full text-sm font-medium border-b-2 border-indigo-400 outline-none bg-transparent"
                                      />
                                    ) : (
                                      <span
                                        className={`text-sm font-medium leading-snug block ${
                                          item.done
                                            ? "line-through text-slate-400"
                                            : color.text
                                        }`}
                                        onDoubleClick={() => {
                                          setEditingId(item.id);
                                          setEditText(item.text);
                                        }}
                                      >
                                        {item.text}
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-0.5 flex-shrink-0">
                                    <button
                                      onClick={() => handlePrivateToggle(item)}
                                      className="p-0.5 text-slate-400 hover:text-slate-600 transition-colors"
                                      title="Move to visible"
                                    >
                                      <EyeOff size={14} />
                                    </button>
                                    <button
                                      onClick={() => handlePriority(item)}
                                      className={`p-0.5 transition-colors ${
                                        item.priority
                                          ? "text-amber-500"
                                          : "opacity-0 group-hover:opacity-100 text-slate-300 hover:text-amber-500"
                                      }`}
                                      title="Toggle priority"
                                    >
                                      <Star size={14} fill={item.priority ? "currentColor" : "none"} />
                                    </button>
                                    <button
                                      onClick={() => handleDelete(item.id)}
                                      className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-300 hover:text-red-500 transition-all"
                                    >
                                      <Trash2 size={14} />
                                    </button>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Always-visible input area */}
                {activeInput === ds ? (
                  <div className="mt-3 pt-2 border-t border-slate-100">
                    <div className="flex items-center gap-2 mb-2">
                      <button
                        onClick={() => setAddingPrivate(false)}
                        className={`text-[11px] font-medium px-2 py-0.5 rounded ${
                          !addingPrivate ? "bg-indigo-100 text-indigo-700" : "text-slate-400 hover:text-slate-600"
                        }`}
                      >
                        Visible
                      </button>
                      <button
                        onClick={() => setAddingPrivate(true)}
                        className={`text-[11px] font-medium px-2 py-0.5 rounded flex items-center gap-1 ${
                          addingPrivate ? "bg-slate-200 text-slate-700" : "text-slate-400 hover:text-slate-600"
                        }`}
                      >
                        <EyeOff size={10} />
                        Private
                      </button>
                    </div>
                    <input
                      ref={inputRef}
                      type="text"
                      value={newText}
                      onChange={(e) => setNewText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleAdd(ds);
                        }
                        if (e.key === "Escape") stopAdding();
                      }}
                      onBlur={() => {
                        if (!newText.trim()) stopAdding();
                      }}
                      autoFocus
                      placeholder={addingPrivate ? "Private item..." : "Type and press Enter..."}
                      className={`w-full text-sm border rounded-lg px-3 py-2 outline-none focus:ring-1 ${
                        addingPrivate
                          ? "border-slate-400 focus:border-slate-500 focus:ring-slate-200"
                          : "border-slate-300 focus:border-indigo-400 focus:ring-indigo-200"
                      }`}
                    />
                    <p className="text-[11px] text-slate-400 mt-1">
                      Enter to add, Esc to close
                    </p>
                  </div>
                ) : (
                  <button
                    onClick={() => { setAddingPrivate(false); startAdding(ds); }}
                    className="mt-3 w-full py-2 text-sm text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg border border-dashed border-slate-200 hover:border-indigo-300 transition-colors"
                  >
                    + Add item
                  </button>
                )}
              </div>
            );
          })}
        </div>
        </div>
      )}
    </div>
  );
}
