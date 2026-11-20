import type { Report, SummaryResult } from "../types";

function ResultSection({ title, result }: { title: string; result: SummaryResult }) {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-slate-900">
        {title}
        {result.count !== undefined && (
          <span className="text-slate-400 font-normal text-sm"> &middot; {result.count} items</span>
        )}
      </h3>

      <p className="text-slate-800 leading-relaxed text-sm">{result.summary}</p>

      {result.highlights && result.highlights.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-slate-600 mb-2">Highlights</h4>
          <ul className="space-y-2">
            {result.highlights.map((h, i) => (
              <li key={i} className="border-l-2 border-indigo-400 pl-3 py-1">
                <div className="font-medium text-sm">{h.title}</div>
                {h.subject && <div className="text-xs text-slate-500">{h.subject}</div>}
                {h.from && <div className="text-xs text-slate-500">From: {h.from}</div>}
                {h.when && <div className="text-xs text-slate-500">{h.when}</div>}
                {h.why && <div className="text-xs text-slate-600 mt-1">{h.why}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.themes && result.themes.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-slate-600 mb-2">Themes</h4>
          <div className="flex flex-wrap gap-2">
            {result.themes.map((t, i) => (
              <span key={i} className="bg-slate-100 text-slate-700 text-xs px-2 py-1 rounded">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {result.action_items && result.action_items.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-slate-600 mb-2">Action Items</h4>
          <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
            {result.action_items.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ReportViewModal({ report, onClose }: { report: Report; onClose: () => void }) {
  const { results } = report;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50 overflow-auto">
      <div className="bg-white rounded-2xl shadow-xl p-6 max-w-2xl w-full space-y-5 my-6 max-h-[90vh] overflow-y-auto">
        <div>
          <h2 className="text-xl font-bold">{report.job_name}</h2>
          <p className="text-xs text-slate-500 mt-1">
            Generated {new Date(report.created_at).toLocaleString()}
          </p>
        </div>

        {results.email && (
          <>
            <hr className="border-slate-200" />
            <ResultSection
              title={`Email Summary (${results.email.period ?? ""})`}
              result={results.email}
            />
          </>
        )}

        {results.calendar && (
          <>
            <hr className="border-slate-200" />
            <ResultSection
              title={`Calendar Summary — ${results.calendar.direction === "future" ? "upcoming" : "previous"} ${results.calendar.period ?? ""}`}
              result={results.calendar}
            />
          </>
        )}

        <div className="flex justify-end pt-2">
          <button
            onClick={onClose}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
