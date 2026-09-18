import React from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  Bell,
  ChevronRight,
  Clock3,
  LayoutDashboard,
  LogOut,
  Maximize2,
  Menu,
  Minimize2,
  Moon,
  QrCode,
  Search,
  Settings,
  Sun,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import Reports from "./Reports";
import Students, { StudentDetail } from "./Students";
import Attendance from "./Attendance";
import SettingsPage from "./SettingsPage";
import LoginPage, { LibrarianSession } from "./LoginPage";
import ScanPage from "./ScanPage";
import { apiRequest, ApiVisit } from "./api";
import { defaultSettings, getDisplaySettings } from "./settings";
import "./index.css";

const BASE = import.meta.env.BASE_URL;
const API = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const currentPath = () => {
  const path = location.pathname;
  const base = BASE.endsWith("/") ? BASE.slice(0, -1) : BASE;
  return base && path.startsWith(base) ? path.slice(base.length) || "/" : path;
};
const href = (path: string) =>
  BASE + (path === "/" ? "" : path.replace(/^\//, ""));

type DailyQr = { date: string; url: string; expiresAt: number };
type DailyQrResponse = {
  scan_url: string;
  session_date: string;
  expires_at: string;
  status: string;
};
function useDailyQr(enabled = true) {
  const [qr, setQr] = React.useState<DailyQr>({
    date: "",
    url: "",
    expiresAt: 0,
  });
  const [error, setError] = React.useState("");
  const load = React.useCallback(async () => {
    if (!enabled) return;
    try {
      const response = await fetch(API + "/api/library/sessions/current", {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Unable to load the daily QR code");
      const body = (await response.json()) as DailyQrResponse;
      setQr({
        date: body.session_date,
        url: body.scan_url,
        expiresAt: new Date(body.expires_at).getTime(),
      });
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to load the daily QR code",
      );
    }
  }, [enabled]);
  React.useEffect(() => {
    if (!enabled) return;
    load();
    const timer = window.setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [enabled, load]);
  return { ...qr, error, regenerate: load };
}
const navigation = [
  {
    label: "Library",
    items: [
      { label: "Dashboard", path: "/", icon: LayoutDashboard },
      { label: "Attendance", path: "/attendance", icon: Clock3 },
      { label: "Library Users", path: "/students", icon: Users },
      { label: "Reports", path: "/reports", icon: BarChart3 },
    ],
  },
  {
    label: "Administration",
    items: [{ label: "Settings", path: "/settings", icon: Settings }],
  },
];
function App() {
  const [path, setPath] = React.useState(currentPath());
  const [librarian, setLibrarian] = React.useState<LibrarianSession | null>(null);
  const [authLoading, setAuthLoading] = React.useState(true);
  const [drawer, setDrawer] = React.useState(false);
  const [dark, setDark] = React.useState(
    () => localStorage.getItem("dark-mode") === "true",
  );
  React.useEffect(() => {
    const fn = () => setPath(currentPath());
    addEventListener("popstate", fn);
    return () => removeEventListener("popstate", fn);
  }, []);
  React.useEffect(
    () => localStorage.setItem("dark-mode", String(dark)),
    [dark],
  );
  React.useEffect(() => {
    apiRequest<LibrarianSession>("/api/admin/me")
      .then(setLibrarian)
      .catch(() => setLibrarian(null))
      .finally(() => setAuthLoading(false));
  }, []);
  async function logout() {
    try { await apiRequest("/api/admin/logout", {method: "POST"}); }
    catch { /* Clear the local view even if the server is temporarily unavailable. */ }
    finally { setLibrarian(null); navigate("/"); }
  }
  function navigate(next: string) {
    history.pushState({}, "", href(next));
    setPath(next);
    setDrawer(false);
  }
  if (path.startsWith("/scan/")) return <ScanPage />;
  if (authLoading) return <main className="librarian-login"><p role="status">Checking librarian session...</p></main>;
  if (!librarian) return <LoginPage onLogin={setLibrarian} />;
  if (path === "/qr-display")
    return librarian.role === "auditor" ? <main className="librarian-login"><p>QR display requires librarian access.</p><button onClick={() => navigate("/")}>Dashboard</button></main> : <QrDisplay close={() => navigate("/")} />;
  const title =
    path === "/reports"
      ? "Reports"
      : path === "/attendance"
        ? "Attendance"
        : path.startsWith("/students")
          ? "Students"
          : path === "/settings"
            ? "Settings"
            : "Dashboard";
  return (
    <div className={`lifeos-shell ${dark ? "dark" : ""}`}>
      <Sidebar path={path} navigate={navigate} librarian={librarian} logout={logout} />
      <div className="lifeos-workspace">
        <Topbar
          title={title}
          dark={dark}
          setDark={setDark}
          open={() => setDrawer(true)}
        />
        <main className="lifeos-content">
          {path === "/reports" ? (
            <Reports />
          ) : path.startsWith("/students/") ? (
            <StudentDetail
              number={decodeURIComponent(path.slice("/students/".length))}
            />
          ) : path === "/students" ? (
            <Students canManage={librarian.role === "admin"} />
          ) : path === "/attendance" ? (
            <Attendance editable={librarian.role !== "auditor"} />
          ) : path === "/settings" ? (
            librarian.role === "admin" ? <SettingsPage /> : <p role="alert">Administrator permission required.</p>
          ) : path === "/" ? (
            <Dashboard editable={librarian.role !== "auditor"} />
          ) : (
            <Placeholder title={title} />
          )}
        </main>
      </div>
      {drawer && (
        <div className="lifeos-drawer">
          <div className="drawer-head">
            <Brand />
            <button className="icon-button" onClick={() => setDrawer(false)}>
              <X size={20} />
            </button>
          </div>
          <Sidebar path={path} navigate={navigate} compact librarian={librarian} logout={logout} />
        </div>
      )}
    </div>
  );
}
function Brand() {
  return (
    <div className="brand-lockup">
      <span className="brand-mark">
        <img src={BASE + "lifeos-platform-crest.svg"} alt="LifeOS" />
      </span>
      <span>
        <strong>Life College</strong>
        <small>Library Attendance</small>
      </span>
    </div>
  );
}
function Sidebar({
  path,
  navigate,
  compact = false,
  librarian,
  logout,
}: {
  path: string;
  navigate: (p: string) => void;
  compact?: boolean;
  librarian: LibrarianSession;
  logout: () => void;
}) {
  const [accountOpen, setAccountOpen] = React.useState(false);
  const accountRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    if (!accountOpen) return;
    const closeOnOutside = (event: PointerEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAccountOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [accountOpen]);
  return (
    <aside className={`lifeos-sidebar ${compact ? "compact" : ""}`}>
      {!compact && (
        <div className="sidebar-head">
          <Brand />
        </div>
      )}
      <nav>
        {navigation.filter(section => section.items.some(item => item.path !== "/settings" || librarian.role === "admin")).map((section) => (
          <div className="nav-section" key={section.label}>
            <p>{section.label}</p>
            {section.items.filter(item => item.path !== "/settings" || librarian.role === "admin").map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className={
                    path === item.path ||
                    (item.path !== "/" && path.startsWith(item.path + "/"))
                      ? "active"
                      : ""
                  }
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                  <ChevronRight size={15} />
                </button>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="sidebar-foot" ref={accountRef}>
        {accountOpen && <div className="sidebar-account-menu" role="menu">
          <div className="sidebar-account-details">
            <strong>{librarian.name}</strong>
            <span>{librarian.email}</span>
            <small>{librarian.role}</small>
          </div>
          <button role="menuitem" onClick={logout}><LogOut size={17} />Sign out</button>
        </div>}
        <button className="sidebar-account-trigger" aria-expanded={accountOpen} aria-haspopup="menu" onClick={() => setAccountOpen(open => !open)}>
          <span className="sidebar-account-avatar">{librarian.name.split(" ").map(part => part[0]).slice(0, 2).join("")}</span>
          <span className="sidebar-account-label"><strong>{librarian.name}</strong><small>{librarian.role}</small></span>
          <ChevronRight size={16} className={accountOpen ? "account-chevron open" : "account-chevron"} />
        </button>
      </div>
    </aside>
  );
}
function Topbar({
  title,
  dark,
  setDark,
  open,
}: {
  title: string;
  dark: boolean;
  setDark: (v: boolean) => void;
  open: () => void;
}) {
  return (
    <header className="lifeos-topbar">
      <button className="icon-button mobile" onClick={open}>
        <Menu size={20} />
      </button>
      <div>
        <h1>{title}</h1>
      </div>
      <div className="top-actions">
        <label className="search">
          <Search size={17} />
          <input placeholder="Search" />
        </label>
        <button className="icon-button" title="Notifications">
          <Bell size={19} />
        </button>
        <button
          className="icon-button"
          title="Theme"
          onClick={() => setDark(!dark)}
        >
          {dark ? <Sun size={19} /> : <Moon size={19} />}
        </button>
      </div>
    </header>
  );
}
type DashboardData = {
  check_in_count: number;
  unique_visitors: number;
  peak_hour: number | null;
  visits: ApiVisit[];
};
function Dashboard({editable}:{editable:boolean}) {
  const { url, error: qrError, regenerate } = useDailyQr(editable),
    [data, setData] = React.useState<DashboardData>({
      check_in_count: 0,
      unique_visitors: 0,
      peak_hour: null,
      visits: [],
    }),
    [error, setError] = React.useState("");
  const load = React.useCallback(
    () =>
      apiRequest<DashboardData>("/api/library/dashboard")
        .then((body) => {
          setData(body);
          setError("");
        })
        .catch((reason) => setError(reason.message)),
    [],
  );
  React.useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);
  const peak =
    data.peak_hour === null
      ? "-"
      : new Date(2000, 0, 1, data.peak_hour).toLocaleTimeString([], {
          hour: "numeric",
        });
  return (
    <div className={`dashboard-grid${editable ? "" : " dashboard-grid-readonly"}`}>
      <section className="overview-hero">
        <div>
          <span className="eyebrow">Library operations</span>
          <h2>Library overview</h2>
          <p>
            Monitor daily foot traffic and manage the student attendance code.
          </p>
        </div>
        <div className="date-block">
          <span>Today</span>
          <strong>
            {new Date().toLocaleDateString(undefined, {
              month: "long",
              day: "numeric",
            })}
          </strong>
          <small>
            {new Date().toLocaleDateString(undefined, {
              weekday: "long",
              year: "numeric",
            })}
          </small>
        </div>
      </section>
      <div className="dashboard-metrics">
        <Metric
          label="Check-ins today"
          value={String(data.check_in_count)}
          detail="Across all user types"
        />
        <Metric
          label="Unique visitors"
          value={String(data.unique_visitors)}
          detail="Recorded today"
        />
        <Metric
          label="Peak check-in hour"
          value={peak}
          detail="Highest arrival volume"
        />
      </div>
      {editable && <section className="panel qr-panel">
        <div className="panel-title">
          <div>
            <QrCode size={18} />
            <h3>Daily QR code</h3>
          </div>
          <button
            className="icon-button qr-display-button"
            title="Open student display"
            onClick={() => location.assign(href("/qr-display"))}
          >
            <QrCode size={18} />
          </button>
        </div>
        <div className="qr-code">
          {url ? (
            <QRCodeSVG value={url} size={230} />
          ) : (
            <div className="display-empty">
              <QrCode size={36} />
              <strong>{qrError || "Loading daily QR code..."}</strong>
            </div>
          )}
        </div>
        <div className="qr-actions">
          <button className="primary-button" onClick={regenerate}>
            Refresh daily QR
          </button>
          <button
            className="secondary-button manual-qr-button"
            onClick={() => location.assign(href("/attendance?manual=1"))}
          >
            <UserPlus size={17} />
            Manual Check-In
          </button>
        </div>
        <small>
          Generated automatically each day and replaced at midnight.
        </small>
      </section>}
      <section className="panel activity-panel">
        <div className="panel-title">
          <div>
            <Clock3 size={18} />
            <h3>Today's activity</h3>
          </div>
          <button
            className="secondary-button"
            onClick={() => location.assign(href("/attendance"))}
          >
            View attendance
          </button>
        </div>
        {error && <p className="module-error">{error}</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Check-in time</th>
                <th>Attendance</th>
              </tr>
            </thead>
            <tbody>
              {data.visits.map((v) => (
                <tr key={v.id}>
                  <td>
                    <strong>{v.name}</strong>
                    <small>{v.user_number}</small>
                  </td>
                  <td>
                    {new Date(v.check_in_time).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td>
                    <span className="badge inside">Checked in</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.visits.length && !error && (
            <p className="module-state">No check-ins recorded today.</p>
          )}
        </div>
      </section>
    </div>
  );
}
function QrDisplay({ close }: { close: () => void }) {
  const [settings, setSettings] = React.useState(defaultSettings);
  const { url } = useDailyQr();
  React.useEffect(() => {
    let active = true;
    getDisplaySettings()
      .then((value) => {
        if (active) setSettings((current) => ({ ...current, ...value }));
      })
      .catch(() => {});
    return () => { active = false; };
  }, []);
  const [isFullscreen, setIsFullscreen] = React.useState(
    Boolean(document.fullscreenElement),
  );
  React.useEffect(() => {
    const sync = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);
  async function toggleFullscreen() {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen?.();
  }
  return (
    <main className="student-display">
      <header>
        <Brand />
        <div>
          <button
            className="display-action"
            onClick={toggleFullscreen}
            aria-pressed={isFullscreen}
            title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            <span>{isFullscreen ? "Exit fullscreen" : "Fullscreen"}</span>
          </button>
          <button className="display-action" onClick={close}>
            Back to dashboard
          </button>
        </div>
      </header>
      <section className="display-card">
        <div className="display-copy">
          <span className="eyebrow">{settings.libraryName}</span>
          <h1>{settings.qrHeading}</h1>
          <p>{settings.qrInstructions}</p>
          <div className="display-date">
            {new Date().toLocaleDateString(undefined, {
              weekday: "long",
              month: "long",
              day: "numeric",
              year: "numeric",
            })}
          </div>
        </div>
        <div className="display-qr">
          {url ? (
            <QRCodeSVG value={url} size={560} level="M" />
          ) : (
            <div className="display-empty">
              <QrCode size={52} />
              <strong>No active QR code</strong>
              <span>Generate today's code from the librarian dashboard.</span>
            </div>
          )}
        </div>
      </section>
      <footer>
        Library Attendance <span /> Powered by LifeOS
      </footer>
    </main>
  );
}
function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <section className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </section>
  );
}
function Placeholder({ title }: { title: string }) {
  return (
    <section className="placeholder">
      <span className="eyebrow">Module</span>
      <h2>{title}</h2>
      <p>
        This LifeOS tenant module is ready for its library-specific workflow.
      </p>
    </section>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
