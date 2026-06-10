"use client";

import { useEffect, useRef, useState } from "react";

type Message = {
  role: "squanch" | "user";
  text: string;
};

type Agent = {
  name: string;
  status: string;
};

type LogItem = {
  text: string;
  created_at: string;
};

type ActivityItem = {
  id: number;
  agent: string;
  action: string;
  summary: string;
  detail: string;
  ref_type: string;
  ref_id: number | null;
  created_at: string;
};

type Task = {
  id: number;
  text: string;
  created_at: string;
};

type JobItem = {
  id: number;
  agent: string;
  status: string;
  prompt: string;
  result: string;
  created_at: string;
  updated_at: string;
};

type EventItem = {
  id: number;
  title: string;
  date_text: string;
  time_text: string;
  person: string;
  created_at: string;
  event_datetime?: string | null;
};

type SystemStatus = {
  backend: string;
  telegram: string;
  memory: string;
  codex: {
    status: string;
    version: string;
  };
  agents: Agent[];
  tasks_count: number;
  events_count: number;
  tasks: Task[];
  events: EventItem[];
  jobs: JobItem[];
  logs: LogItem[];
  activities: ActivityItem[];
  updated_at: string;
};

function formatDateTime(value?: string | null) {
  if (!value) return "";

  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;

  return d.toLocaleString("es-MX", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "squanch", text: "SQUANCH online. Awaiting command." },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [showMemory, setShowMemory] = useState(false);
  const [showJobs, setShowJobs] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);
  const [completedTasks, setCompletedTasks] = useState<Task[]>([]);
  const [completedEvents, setCompletedEvents] = useState<EventItem[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobItem | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  async function fetchCompleted() {
    try {
      const res = await fetch("http://127.0.0.1:8000/completed");
      const data = await res.json();
      setCompletedTasks(data.tasks ?? []);
      setCompletedEvents(data.events ?? []);
    } catch {
      setCompletedTasks([]);
      setCompletedEvents([]);
    }
  }

  async function fetchStatus() {
    try {
      const res = await fetch("http://127.0.0.1:8000/status");
      const data = await res.json();
      setStatus(data);
      fetchCompleted();
    } catch {
      setStatus(null);
    }
  }

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const userMessage = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        { role: "squanch", text: data.response },
      ]);

      fetchStatus();
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "squanch",
          text: "Connection error. FastAPI backend is offline.",
        },
      ]);
    }

    setLoading(false);
  }

  async function markDone(taskId: number) {
    await fetch(`http://127.0.0.1:8000/tasks/${taskId}/done`, {
      method: "PATCH",
    });
    fetchStatus();
  }

  async function deleteTask(taskId: number) {
    await fetch(`http://127.0.0.1:8000/tasks/${taskId}`, {
      method: "DELETE",
    });
    fetchStatus();
  }

  async function markEventDone(eventId: number) {
    await fetch(`http://127.0.0.1:8000/events/${eventId}/done`, {
      method: "PATCH",
    });
    fetchStatus();
  }

  async function deleteEvent(eventId: number) {
    await fetch(`http://127.0.0.1:8000/events/${eventId}`, {
      method: "DELETE",
    });
    fetchStatus();
  }

  const backendStatus = status?.backend ?? "offline";
  const memoryStatus = status?.memory ?? "offline";
  const codexStatus = status?.codex?.status ?? "offline";
  const agents = status?.agents ?? [];
  const activities = status?.activities ?? [];
  const tasks = status?.tasks ?? [];
  const events = status?.events ?? [];
  const jobs = status?.jobs ?? [];

  return (
    <main className="h-screen w-screen bg-[#02060d] text-cyan-100 overflow-hidden">
      <style jsx global>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes spinBack { to { transform: rotate(-360deg); } }
        @keyframes pulseCore {
          0%,100% { transform: scale(1); opacity:.75; box-shadow:0 0 35px rgba(0,195,255,.25); }
          50% { transform: scale(1.05); opacity:1; box-shadow:0 0 90px rgba(0,195,255,.7); }
        }
        @keyframes float { 50% { transform: translateY(-6px); } }

        .card {
          background: rgba(2, 10, 22, .86);
          border: 1px solid rgba(0,195,255,.28);
          box-shadow: inset 0 0 24px rgba(0,195,255,.05), 0 0 28px rgba(0,195,255,.10);
        }
        .glow {
          text-shadow: 0 0 10px rgba(0,195,255,.95), 0 0 28px rgba(0,195,255,.45);
        }
        .grid-bg {
          background-image:
            linear-gradient(rgba(0,195,255,.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,195,255,.04) 1px, transparent 1px);
          background-size: 42px 42px;
        }
      `}</style>

      <div className="fixed inset-0 grid-bg opacity-50" />

      <div className="relative h-full w-full p-4 grid grid-cols-[250px_1fr_390px] gap-4">
        <aside className="card rounded-3xl p-5 flex flex-col">
          <div>
            <h1 className="text-2xl font-black glow tracking-wide">SQUANCH</h1>
            <p className="text-[10px] text-cyan-500 tracking-[0.3em]">
              COMMAND CENTER
            </p>
          </div>

          <nav className="mt-8 space-y-2 text-sm">
            {[
              "Dashboard",
              "Conversation",
              "Agents",
              "Sports Intel",
              "Portfolio",
              "Memory",
              "Completed",
              "Processes",
              "Logs",
              "Settings",
            ].map((item, i) => (
              <button
                key={item}
                onClick={() => {
                  if (item === "Memory") setShowMemory(true);
                  if (item === "Completed") setShowCompleted(true);
                  if (item === "Processes") setShowJobs(true);
                }}
                className={`w-full text-left rounded-xl p-3 border ${
                  i === 0
                    ? "bg-cyan-400/15 border-cyan-300/50"
                    : "bg-black/30 border-cyan-900/60 hover:bg-cyan-400/10"
                }`}
              >
                <div className="flex justify-between">
                  <span>{item === "Memory" ? "PENDING" : item}</span>
                  {item === "Completed" && (
                    <span className="text-cyan-300">
                      {completedTasks.length + completedEvents.length}
                    </span>
                  )}
                  {item === "Processes" && (
                    <span className="text-cyan-300">{jobs.length}</span>
                  )}
                  {item === "Memory" && (
                    <span className="text-cyan-300">
                      {tasks.length + events.length}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </nav>

          <div className="mt-auto card rounded-2xl p-4">
            <p className="text-xs text-cyan-500 tracking-widest">STATUS</p>
            <p
              className={`text-3xl font-black glow ${
                backendStatus === "online" ? "text-cyan-200" : "text-red-400"
              }`}
            >
              {backendStatus.toUpperCase()}
            </p>
            <p className="text-xs text-cyan-700">
              Telegram: {status?.telegram ?? "offline"} · Codex: {codexStatus}
            </p>
          </div>
        </aside>

        <section className="grid grid-rows-[64px_95px_520px_1fr] gap-4 min-h-0">
          <div className="card rounded-3xl p-4 flex items-center justify-between">
            <div>
              <p className="font-black tracking-[0.18em]">
                NEURAL INTERFACE ACTIVE
              </p>
              <p className="text-xs text-cyan-600">
                Last update: {status?.updated_at ?? "waiting for backend"}
              </p>
            </div>
            <div className="text-xs border border-cyan-400/50 rounded-full px-4 py-2">
              {status ? "LIVE" : "OFFLINE"}
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4">
            {[
              ["Backend", backendStatus],
              ["Memory", memoryStatus],
              ["Tasks", `${status?.tasks_count ?? 0}`],
              ["Events", `${status?.events_count ?? 0}`],
            ].map(([a, b]) => (
              <div key={a} className="card rounded-3xl p-4">
                <p className="text-xs text-cyan-500 tracking-[0.25em] uppercase">
                  {a}
                </p>
                <p className="text-3xl font-black glow">{b}</p>
              </div>
            ))}
          </div>

          <div className="card rounded-3xl relative overflow-hidden flex items-center justify-center">
            <div className="absolute inset-0 bg-[radial-gradient(circle,rgba(0,195,255,.25),transparent_58%)]" />

            <div
              className="absolute w-[380px] h-[380px] rounded-full border border-cyan-900/80"
              style={{ animation: "pulseCore 3s ease-in-out infinite" }}
            />
            <div
              className="absolute w-[320px] h-[320px] rounded-full border border-cyan-400/60"
              style={{ animation: "spin 14s linear infinite" }}
            >
              <div className="absolute -top-1 left-1/2 w-3 h-3 bg-cyan-200 rounded-full shadow-[0_0_24px_rgba(0,195,255,1)]" />
              <div className="absolute bottom-8 right-5 w-2.5 h-2.5 bg-blue-300 rounded-full shadow-[0_0_20px_rgba(96,165,250,1)]" />
            </div>
            <div
              className="absolute w-[250px] h-[250px] rounded-full border border-dashed border-cyan-300/50"
              style={{ animation: "spinBack 20s linear infinite" }}
            />
            <div
              className="absolute w-[175px] h-[175px] rounded-full border border-cyan-300/70"
              style={{ animation: "pulseCore 3s ease-in-out infinite" }}
            />

            <div
              className="relative z-10 text-center"
              style={{ animation: "float 4s ease-in-out infinite" }}
            >
              <p className="text-7xl font-black tracking-[0.18em] glow">
                SQUANCH
              </p>
              <p className="text-xs text-cyan-400 tracking-[0.25em] mt-3">
                {loading ? "PROCESSING COMMAND" : "LISTENING FOR COMMAND"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-[1.15fr_.85fr] gap-4 min-h-0">
            <div className="card rounded-3xl p-5 min-h-0 overflow-hidden">
              <h2 className="font-black tracking-[0.14em] mb-3">
                RECENT ACTIVITY
              </h2>
              <div className="text-xs text-cyan-300 space-y-2 overflow-auto h-[calc(100%-32px)]">
                {activities.length > 0 ? (
                  activities.map((activity) => (
                    <button
                      key={activity.id}
                      className="block w-full text-left rounded-lg px-2 py-1 hover:bg-cyan-400/10"
                      onClick={() => {
                        if (activity.ref_type === "job" && activity.ref_id) {
                          const job = jobs.find((j) => j.id === activity.ref_id);
                          if (job) setSelectedJob(job);
                        }
                        if (activity.ref_type === "event") {
                          setShowMemory(true);
                        }
                        if (activity.ref_type === "task") {
                          setShowMemory(true);
                        }
                      }}
                    >
                      <div className="flex justify-between gap-3">
                        <span className="truncate">
                          <span className="text-cyan-200">
                            {activity.agent} {activity.action}
                          </span>
                          <span className="text-cyan-500">
                            {" "}
                            — {activity.summary}
                          </span>
                        </span>
                        <span className="shrink-0 text-cyan-700">
                          {activity.created_at?.slice(11, 16)}
                        </span>
                      </div>
                    </button>
                  ))
                ) : (
                  <p>• Waiting for system activity...</p>
                )}
              </div>
            </div>

            <div className="grid grid-rows-[1fr_1fr] gap-4 min-h-0">
              <div className="card rounded-3xl p-5 overflow-hidden">
                <h2 className="font-black tracking-[0.14em] mb-3">
                  QUICK ACTIONS
                </h2>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {["task test", "citas", "codex status", "analiza picks"].map(
                    (x) => (
                      <button
                        key={x}
                        onClick={() => setInput(x)}
                        className="rounded-xl p-3 border border-cyan-700/70 bg-cyan-400/10 hover:bg-cyan-400/20"
                      >
                        {x}
                      </button>
                    )
                  )}
                </div>
              </div>

              <div className="card rounded-3xl p-5 overflow-hidden">
                <h2 className="font-black tracking-[0.14em] mb-3">
                  ACTIVE AGENTS
                </h2>
                <div className="space-y-2 text-sm">
                  {agents.length > 0 ? (
                    agents.map((agent) => (
                      <div
                        key={agent.name}
                        className="flex justify-between border-b border-cyan-900/50 pb-2"
                      >
                        <span>{agent.name}</span>
                        <span
                          className={
                            agent.status === "ready"
                              ? "text-cyan-300"
                              : "text-yellow-400"
                          }
                        >
                          {agent.status.toUpperCase()}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-cyan-700 text-xs">
                      Waiting for agent status...
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <aside className="card rounded-3xl p-5 flex flex-col min-h-0">
          <h2 className="font-black tracking-[0.14em] mb-4">CONVERSATION</h2>

          <div className="flex-1 bg-black/40 rounded-2xl p-4 text-sm space-y-3 overflow-y-auto overflow-x-hidden border border-cyan-900/70">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`rounded-xl p-3 whitespace-pre-wrap break-words overflow-hidden ${
                  m.role === "user"
                    ? "ml-8 bg-cyan-400/15 border border-cyan-500/50"
                    : "mr-8 bg-black/60 border border-cyan-800/70"
                }`}
              >
                {m.text}
              </div>
            ))}

            {loading && (
              <div className="mr-8 bg-black/60 border border-cyan-800/70 rounded-xl p-3 animate-pulse">
                SQUANCH is thinking...
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          <div className="flex gap-2 mt-4">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              className="flex-1 rounded-xl bg-black/50 border border-cyan-800 p-3 outline-none text-sm"
              placeholder="Type a command..."
            />
            <button
              onClick={sendMessage}
              className="rounded-xl bg-cyan-400 text-black font-black px-5"
            >
              ➤
            </button>
          </div>
        </aside>
      </div>

      {showMemory && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-8">
          <div className="card rounded-3xl w-full max-w-5xl max-h-[84vh] p-6 flex flex-col">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-2xl font-black glow tracking-[0.12em]">
                  PENDING
                </h2>
                <p className="text-xs text-cyan-600 mt-1">
                  {tasks.length} tasks · {events.length} events
                </p>
              </div>

              <button
                onClick={() => setShowMemory(false)}
                className="rounded-xl border border-cyan-700/70 bg-black/40 px-4 py-2 hover:bg-cyan-400/10"
              >
                Close
              </button>
            </div>

                        <div className="grid grid-cols-2 gap-5 overflow-hidden min-h-0">
              <div className="overflow-auto pr-2">
                <h3 className="font-black tracking-[0.16em] text-cyan-300 mb-3">
                  TASKS
                </h3>

                <div className="space-y-3">
                  {tasks.length > 0 ? (
                    tasks.map((task) => (
                      <div
                        key={task.id}
                        className="rounded-2xl border border-cyan-900/70 bg-black/45 p-4"
                      >
                        <p className="text-cyan-100 text-sm mb-2">
                          {task.text}
                        </p>
                        <p className="text-[10px] text-cyan-700 mb-3">
                          Created: {task.created_at}
                        </p>

                        <div className="flex gap-2">
                          <button
                            onClick={() => markDone(task.id)}
                            className="px-4 py-2 rounded-xl bg-cyan-400/15 border border-cyan-600/70 hover:bg-cyan-400/25"
                          >
                            ✓ Done
                          </button>

                          <button
                            onClick={() => deleteTask(task.id)}
                            className="px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/50 hover:bg-red-500/20 text-red-300"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-cyan-700 text-sm">
                      No open tasks.
                    </p>
                  )}
                </div>
              </div>

              <div className="overflow-auto pr-2">
                <h3 className="font-black tracking-[0.16em] text-cyan-300 mb-3">
                  EVENTS
                </h3>

                <div className="space-y-3">
                  {events.length > 0 ? (
                    events.map((event) => (
                      <div
                        key={event.id}
                        className="rounded-2xl border border-cyan-900/70 bg-black/45 p-4"
                      >
                        <p className="text-cyan-100 text-sm font-bold mb-1">
                          📅 {event.title}
                        </p>

                        <p className="text-xs text-cyan-400 mb-1">
                          {event.event_datetime
                            ? formatDateTime(event.event_datetime)
                            : `${event.date_text ?? ""} ${event.time_text ?? ""}`}
                        </p>

                        {event.person && (
                          <p className="text-[11px] text-cyan-600 mb-2">
                            Persona/lugar: {event.person}
                          </p>
                        )}

                        <p className="text-[10px] text-cyan-800 mb-3">
                          Created: {event.created_at}
                        </p>

                        <div className="flex gap-2">
                          <button
                            onClick={() => markEventDone(event.id)}
                            className="px-4 py-2 rounded-xl bg-cyan-400/15 border border-cyan-600/70 hover:bg-cyan-400/25"
                          >
                            ✓ Done
                          </button>

                          <button
                            onClick={() => deleteEvent(event.id)}
                            className="px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/50 hover:bg-red-500/20 text-red-300"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-cyan-700 text-sm">
                      No open events. Tell SQUANCH: “Tengo cita con Mario mañana a las 2”.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {showCompleted && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-8">
          <div className="card rounded-3xl w-full max-w-5xl max-h-[84vh] p-6 flex flex-col">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-2xl font-black glow tracking-[0.12em]">
                  COMPLETED
                </h2>
                <p className="text-xs text-cyan-600 mt-1">
                  {completedTasks.length} tasks · {completedEvents.length} events completed
                </p>
              </div>

              <button
                onClick={() => setShowCompleted(false)}
                className="rounded-xl border border-cyan-700/70 bg-black/40 px-4 py-2 hover:bg-cyan-400/10"
              >
                Close
              </button>
            </div>

            <div className="grid grid-cols-2 gap-5 overflow-hidden min-h-0">
              <div className="overflow-auto pr-2">
                <h3 className="font-black tracking-[0.16em] text-cyan-300 mb-3">
                  COMPLETED TASKS
                </h3>

                <div className="space-y-3">
                  {completedTasks.length > 0 ? (
                    completedTasks.map((task) => (
                      <div
                        key={task.id}
                        className="rounded-2xl border border-cyan-900/70 bg-black/35 p-4 opacity-80"
                      >
                        <p className="text-cyan-100 text-sm mb-2 line-through">
                          {task.text}
                        </p>
                        <p className="text-[10px] text-cyan-700">
                          Created: {task.created_at}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-cyan-700 text-sm">No completed tasks yet.</p>
                  )}
                </div>
              </div>

              <div className="overflow-auto pr-2">
                <h3 className="font-black tracking-[0.16em] text-cyan-300 mb-3">
                  COMPLETED EVENTS
                </h3>

                <div className="space-y-3">
                  {completedEvents.length > 0 ? (
                    completedEvents.map((event) => (
                      <div
                        key={event.id}
                        className="rounded-2xl border border-cyan-900/70 bg-black/35 p-4 opacity-80"
                      >
                        <p className="text-cyan-100 text-sm font-bold mb-1 line-through">
                          📅 {event.title}
                        </p>
                        <p className="text-xs text-cyan-500">
                          {event.event_datetime
                            ? formatDateTime(event.event_datetime)
                            : `${event.date_text ?? ""} ${event.time_text ?? ""}`}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-cyan-700 text-sm">No completed events yet.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {showJobs && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-8">
          <div className="card rounded-3xl w-full max-w-5xl max-h-[84vh] p-6 flex flex-col">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-2xl font-black glow tracking-[0.12em]">
                  PROCESSES
                </h2>
                <p className="text-xs text-cyan-600 mt-1">
                  {jobs.length} recent processes
                </p>
              </div>

              <button
                onClick={() => setShowJobs(false)}
                className="rounded-xl border border-cyan-700/70 bg-black/40 px-4 py-2 hover:bg-cyan-400/10"
              >
                Close
              </button>
            </div>

            <div className="overflow-auto space-y-3 pr-2">
              {jobs.length > 0 ? (
                jobs.map((job) => (
                  <button
                    key={job.id}
                    onClick={() => setSelectedJob(job)}
                    className="block w-full text-left rounded-2xl border border-cyan-900/70 bg-black/45 p-4 hover:bg-cyan-400/10"
                  >
                    <div className="flex justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-cyan-100 font-bold">
                          #{job.id} · {job.agent}
                        </p>
                        <p className="text-xs text-cyan-500 truncate mt-1">
                          {job.prompt || "No prompt"}
                        </p>
                      </div>

                      <div className="text-right shrink-0">
                        <p
                          className={
                            job.status === "completed"
                              ? "text-cyan-300 text-xs font-bold"
                              : job.status === "failed"
                              ? "text-red-300 text-xs font-bold"
                              : "text-yellow-300 text-xs font-bold"
                          }
                        >
                          {job.status.toUpperCase()}
                        </p>
                        <p className="text-[10px] text-cyan-700 mt-1">
                          {job.updated_at}
                        </p>
                      </div>
                    </div>
                  </button>
                ))
              ) : (
                <p className="text-cyan-700 text-sm">No processes yet.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {selectedJob && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-8">
          <div className="card rounded-3xl w-full max-w-5xl max-h-[86vh] p-6 flex flex-col">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-2xl font-black glow tracking-[0.12em]">
                  JOB #{selectedJob.id}
                </h2>
                <p className="text-xs text-cyan-600 mt-1">
                  {selectedJob.agent} · {selectedJob.status.toUpperCase()} · {selectedJob.created_at}
                </p>
              </div>

              <button
                onClick={() => setSelectedJob(null)}
                className="rounded-xl border border-cyan-700/70 bg-black/40 px-4 py-2 hover:bg-cyan-400/10"
              >
                Close
              </button>
            </div>

            <div className="rounded-2xl border border-cyan-900/70 bg-black/45 p-4 mb-4">
              <p className="text-xs text-cyan-500 tracking-[0.18em] mb-2">
                PROMPT
              </p>
              <p className="text-sm text-cyan-100 whitespace-pre-wrap break-words">
                {selectedJob.prompt || "No prompt saved."}
              </p>
            </div>

            <div className="flex-1 overflow-auto rounded-2xl border border-cyan-900/70 bg-black/55 p-4">
              <p className="text-xs text-cyan-500 tracking-[0.18em] mb-3">
                RESULT
              </p>
              <pre className="text-sm text-cyan-100 whitespace-pre-wrap break-words font-sans leading-relaxed">
                {selectedJob.result || "Este job todavía no tiene resultado."}
              </pre>
            </div>
          </div>
        </div>
      )}

    </main>
  );
}
