import { useEffect, useState } from "react";
import { FileText, Trash2, Eye } from "lucide-react";
import type { Report } from "../types";
import { deleteReport, getReports } from "../services/api";
import ReportViewModal from "./ReportViewModal";

export default function ReportsPanel() {
  const [reports, setReports] = useState<Report[]>([]);
  const [viewing, setViewing] = useState<Report | null>(null);

  const load = () => getReports().then(setReports).catch(() => {});

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (report: Report) => {
    if (!confirm("Delete this report?")) return;
    await deleteReport(report.id);
    load();
  };

  return (
    <>
      <div className="bg-white rounded-2xl shadow-sm p-6">
        <h2 className="text-lg font-bold mb-4">Reports</h2>

        {reports.length === 0 ? (
          <p className="text-slate-500 text-sm py-4 text-center">
            No reports yet. Reports are generated when scheduled jobs run.
          </p>
        ) : (
          <div className="space-y-2">
            {reports.map((report) => (
              <div
                key={report.id}
                className="flex items-center gap-3 border border-slate-200 rounded-lg p-3"
              >
                <FileText size={18} className="text-indigo-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{report.job_name}</div>
                  <div className="text-xs text-slate-500">
                    {new Date(report.created_at).toLocaleString()}
                    {report.results.email && " \u00b7 Emails"}
                    {report.results.calendar && " \u00b7 Calendar"}
                  </div>
                </div>
                <button
                  onClick={() => setViewing(report)}
                  className="p-1.5 text-slate-500 hover:text-indigo-600"
                  title="View report"
                >
                  <Eye size={16} />
                </button>
                <button
                  onClick={() => handleDelete(report)}
                  className="p-1.5 text-slate-400 hover:text-red-500"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {viewing && <ReportViewModal report={viewing} onClose={() => setViewing(null)} />}
    </>
  );
}
