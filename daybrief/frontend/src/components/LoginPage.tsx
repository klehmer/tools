import { Calendar, Mail } from "lucide-react";
import { getAuthUrl } from "../services/api";

export default function LoginPage({ error }: { error?: string | null }) {
  const handleLogin = async () => {
    const { url } = await getAuthUrl();
    window.location.href = url;
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 space-y-6">
        <div className="flex items-center justify-center gap-3 text-indigo-600">
          <Mail size={32} />
          <Calendar size={32} />
        </div>
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">DayBrief</h1>
          <p className="text-slate-600 text-sm">
            AI-powered summaries of your inbox and calendar over any time period.
          </p>
        </div>
        <ul className="text-sm text-slate-700 space-y-2">
          <li>• Summarize emails from the past day, week, or month</li>
          <li>• Highlight what matters most</li>
          <li>• Look ahead at upcoming meetings</li>
          <li>• Spot themes and action items</li>
        </ul>
        <button
          onClick={handleLogin}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-3 rounded-lg transition"
        >
          Sign in with Google
        </button>
        {error && <p className="text-red-600 text-sm text-center">{error}</p>}
      </div>
    </div>
  );
}
