import React from "react";
import { Check, Clock3, Plus, Search, X } from "lucide-react";
import { apiRequest, ApiUser, ApiVisit, displayUserType, Page } from "./api";

const localInput = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};
const apiTypes = [
  ["Student", "student"],
  ["Faculty", "faculty"],
  ["Non-Teaching", "non-teaching personnel"],
  ["Visitor", "visitor"],
] as const;

export default function Attendance({editable}:{editable:boolean}) {
  const [q, setQ] = React.useState(""),
    [type, setType] = React.useState(""),
    [rows, setRows] = React.useState<ApiVisit[]>([]),
    [total, setTotal] = React.useState(0),
    [version, setVersion] = React.useState(0),
    [manual, setManual] = React.useState(
      () => editable && new URLSearchParams(location.search).get("manual") === "1",
    ),
    [error, setError] = React.useState(""),
    [loading, setLoading] = React.useState(true);
  const closeManual = () => {
    setManual(false);
    if (location.search) history.replaceState({}, "", location.pathname);
  };
  React.useEffect(() => {
    const controller = new AbortController(),
      timer = setTimeout(() => {
        setLoading(true);
        apiRequest<Page<ApiVisit>>(
          "/api/library/attendance?" +
            new URLSearchParams({ q, user_type: type, page_size: "500" }),
          { signal: controller.signal },
        )
          .then((body) => {
            setRows(body.items);
            setTotal(body.total);
            setError("");
          })
          .catch((reason) => {
            if (reason.name !== "AbortError") setError(reason.message);
          })
          .finally(() => setLoading(false));
      }, 180);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [q, type, version]);
  return (
    <div className="module-stack">
      <div className="module-heading">
        <div>
          <span className="eyebrow">Check-in log</span>
          <h2>Library attendance</h2>
          <p>QR and librarian-recorded check-ins share one attendance log.</p>
        </div>
        <div className="module-count">
          <Clock3 size={18} />
          <strong>{total}</strong>
          <span>check-ins</span>
        </div>
      </div>
      <section className="panel">
        <div className="module-filters">
          <label className="module-search">
            <Search size={17} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search user"
            />
          </label>
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">All user types</option>
            {apiTypes.map(([label, value]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
          {editable && <button className="manual-button" onClick={() => setManual(true)}>
            <Plus size={17} />
            Manual Check-In
          </button>}
        </div>
        {error && <p className="module-error">{error}</p>}
        <div className="table-wrap attendance-table">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>User</th>
                <th>Type</th>
                <th>Program / Department</th>
                <th>Check-in time</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((v) => (
                <tr key={v.id}>
                  <td>{new Date(v.check_in_time).toLocaleDateString()}</td>
                  <td>
                    <strong>{v.name}</strong>
                    <small>{v.user_number}</small>
                    {(v.note || v.purpose) && (
                      <small>{v.note || v.purpose}</small>
                    )}
                  </td>
                  <td>{displayUserType(v.user_type)}</td>
                  <td>
                    {v.program ||
                      v.department ||
                      v.organization ||
                      "External visitor"}
                  </td>
                  <td>
                    {new Date(v.check_in_time).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td>
                    <span
                      className={
                        v.source === "manual" ? "badge manual" : "badge inside"
                      }
                    >
                      {v.source === "manual"
                        ? "Manual"
                        : v.source === "guest"
                          ? "Guest QR"
                          : "QR check-in"}
                    </span>
                    {v.recorded_by && <small>By {v.recorded_by}</small>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {loading && <p className="module-state">Loading attendance...</p>}
          {!loading && !rows.length && !error && (
            <p className="module-state">
              No attendance records match these filters.
            </p>
          )}
        </div>
      </section>
      {editable && manual && (
        <ManualModal
          close={closeManual}
          saved={() => {
            setVersion((v) => v + 1);
            closeManual();
          }}
        />
      )}
    </div>
  );
}

function ManualModal({
  close,
  saved,
}: {
  close: () => void;
  saved: () => void;
}) {
  const [userType, setUserType] = React.useState("student"),
    [users, setUsers] = React.useState<ApiUser[]>([]),
    [number, setNumber] = React.useState(""),
    [visitor, setVisitor] = React.useState({
      name: "",
      organization: "",
      purpose: "",
    }),
    [timeMode, setTimeMode] = React.useState<"now" | "manual">("now"),
    [time, setTime] = React.useState(localInput),
    [note, setNote] = React.useState(""),
    [userSearch, setUserSearch] = React.useState(""),
    [error, setError] = React.useState(""),
    [saving, setSaving] = React.useState(false);
  React.useEffect(() => {
    if (userType === "visitor") {
      setUsers([]);
      setNumber("");
      return;
    }
    const controller = new AbortController(),
      timer = setTimeout(
        () =>
          apiRequest<Page<ApiUser>>(
            "/api/library/users?" +
              new URLSearchParams({
                q: userSearch,
                user_type: userType,
                page_size: "200",
              }),
            { signal: controller.signal },
          )
            .then((body) => {
              setUsers(body.items);
              setNumber((current) =>
                body.items.some((user) => user.number === current)
                  ? current
                  : body.items[0]?.number || "",
              );
            })
            .catch((reason) => {
              if (reason.name !== "AbortError") setError(reason.message);
            }),
        180,
      );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [userType, userSearch]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/api/library/attendance/manual", {
        method: "POST",
        body: JSON.stringify(
          userType === "visitor"
            ? {
                visitor_name: visitor.name,
                organization: visitor.organization,
                purpose: visitor.purpose,
                checked_in_at:
                  timeMode === "manual" ? new Date(time).toISOString() : null,
                note,
              }
            : {
                user_number: number,
                checked_in_at:
                  timeMode === "manual" ? new Date(time).toISOString() : null,
                note,
              },
        ),
      });
      saved();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to record check-in.",
      );
    } finally {
      setSaving(false);
    }
  }
  const selected = users.find((user) => user.number === number);
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <form className="manual-modal" onSubmit={submit}>
        <header>
          <div>
            <span className="eyebrow">Librarian entry</span>
            <h3>Manual Check-In</h3>
            <p>Record attendance when a QR scan is unavailable.</p>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={close}
            title="Close"
          >
            <X size={19} />
          </button>
        </header>
        <div className="manual-form">
          <label>
            User type
            <select
              value={userType}
              onChange={(e) => {
                setUserType(e.target.value);
                setUserSearch("");
                setError("");
              }}
            >
              {apiTypes.map(([label, value]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {userType === "visitor" ? (
            <>
              <label>
                Visitor name
                <input
                  value={visitor.name}
                  onChange={(e) =>
                    setVisitor((v) => ({ ...v, name: e.target.value }))
                  }
                  required
                />
              </label>
              <label>
                Organization
                <input
                  value={visitor.organization}
                  onChange={(e) =>
                    setVisitor((v) => ({ ...v, organization: e.target.value }))
                  }
                />
              </label>
              <label>
                Purpose of visit
                <input
                  value={visitor.purpose}
                  onChange={(e) =>
                    setVisitor((v) => ({ ...v, purpose: e.target.value }))
                  }
                  required
                />
              </label>
            </>
          ) : (
            <>
              <label className="wide">
                Search user
                <span className="manual-user-search">
                  <Search size={17} />
                  <input
                    type="search"
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                    placeholder="Name, ID number, program, section, or department"
                    autoComplete="off"
                  />
                </span>
              </label>
              <label className="wide">
                User
                <select
                  value={number}
                  onChange={(e) => setNumber(e.target.value)}
                  disabled={!users.length}
                >
                  {users.length ? (
                    users.map((user) => (
                      <option value={user.number} key={user.number}>
                        {user.name} · {user.number}
                      </option>
                    ))
                  ) : (
                    <option value="">No matching users</option>
                  )}
                </select>
                {selected ? (
                  <small>
                    {selected.user_type === "student"
                      ? [
                          selected.program,
                          selected.year_level,
                          selected.section,
                        ]
                          .filter(Boolean)
                          .join(" · ")
                      : selected.department}
                  </small>
                ) : (
                  <small>No users match your search.</small>
                )}
              </label>
            </>
          )}
          <div className="time-choice wide">
            <span>Check-in date and time</span>
            <div className="time-segments">
              <button
                type="button"
                className={timeMode === "now" ? "active" : ""}
                onClick={() => setTimeMode("now")}
              >
                Automatic / now
              </button>
              <button
                type="button"
                className={timeMode === "manual" ? "active" : ""}
                onClick={() => {
                  setTimeMode("manual");
                  setTime(localInput());
                }}
              >
                Set manually
              </button>
            </div>
            {timeMode === "now" ? (
              <small>
                The current date and time will be recorded when you submit.
              </small>
            ) : (
              <input
                type="datetime-local"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                max={localInput()}
                required
              />
            )}
          </div>
          <label className="wide">
            Note (optional)
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Reason for manual entry"
            />
          </label>
          {error && <p className="module-error wide">{error}</p>}
        </div>
        <footer>
          <button type="button" className="secondary-button" onClick={close}>
            Cancel
          </button>
          <button
            className="save-button"
            disabled={saving || (userType !== "visitor" && !number)}
          >
            <Check size={16} />
            {saving ? "Recording..." : "Record check-in"}
          </button>
        </footer>
      </form>
    </div>
  );
}
