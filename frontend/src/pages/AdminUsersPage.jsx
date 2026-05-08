/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import { deleteUser, getUserUsageDetails, getUsers, updateUserRole } from "../lib/api";
import { ROLE_KEYS } from "../lib/roles";
import { useAuth } from "../context/AuthContext";

const ROLE_OPTIONS = Object.values(ROLE_KEYS);
/** Renders the admin users management page. */
export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [roleDrafts, setRoleDrafts] = useState({});
  const [managerDrafts, setManagerDrafts] = useState({});
  const [busyUserId, setBusyUserId] = useState(null);
  const [usageBusyUserId, setUsageBusyUserId] = useState(null);
  const [usageOpenUserId, setUsageOpenUserId] = useState(null);
  const [usagePanel, setUsagePanel] = useState({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  /** Loads users. */
  async function loadUsers() {
    try {
      const response = await getUsers();
      setUsers(response.users || []);
    } catch (usersError) {
      setError(usersError.message || "Failed to load users.");
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);
  useEffect(() => {
    setRoleDrafts((prev) => {
      const next = { ...prev };
      for (const item of users) {
        if (!next[item.id]) {
          next[item.id] = item.role;
        }
      }
      return next;
    });
    setManagerDrafts((prev) => {
      const next = { ...prev };
      for (const item of users) {
        if (next[item.id] === undefined) {
          next[item.id] = item.manager_user_id ?? "";
        }
      }
      return next;
    });
  }, [users]);
  /** Updates a user role from the admin page. */
  async function handleRoleChange(userId) {
    setBusyUserId(userId);
    setError("");
    setSuccess("");
    try {
      const role = roleDrafts[userId];
      const managerUserIdRaw = managerDrafts[userId];
      const managerUserId = role === ROLE_KEYS.ANALYST && managerUserIdRaw !== "" ? Number(managerUserIdRaw) : null;
      await updateUserRole(userId, role, managerUserId);
      setSuccess("User role updated successfully.");
      await loadUsers();
    } catch (roleError) {
      setError(roleError.message || "Role update failed.");
    } finally {
      setBusyUserId(null);
    }
  }
  /** Deletes a user from the admin page. */
  async function handleDeleteUser(user) {
    const confirmed = window.confirm(`Delete user ${user.username}? This cannot be undone.`);
    if (!confirmed) {
      return;
    }

    setBusyUserId(user.id);
    setError("");
    setSuccess("");
    try {
      await deleteUser(user.id);
      setSuccess("User deleted successfully.");
      await loadUsers();
    } catch (deleteError) {
      setError(deleteError.message || "Delete user failed.");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleToggleUsage(userId) {
    if (usageOpenUserId === userId) {
      setUsageOpenUserId(null);
      return;
    }

    setError("");
    if (!usagePanel[userId]) {
      setUsageBusyUserId(userId);
      try {
        const response = await getUserUsageDetails(userId);
        setUsagePanel((prev) => ({ ...prev, [userId]: response }));
      } catch (usageError) {
        setError(usageError.message || "Failed to load user usage.");
        return;
      } finally {
        setUsageBusyUserId(null);
      }
    }
    setUsageOpenUserId(userId);
  }

  const canDeleteUsers = currentUser?.role === ROLE_KEYS.ADMIN;
  const isAdmin = currentUser?.role === ROLE_KEYS.ADMIN;
  const isUsageAdmin = currentUser?.role === ROLE_KEYS.ADMIN;
  const managerUsers = users.filter((item) => item.role === ROLE_KEYS.MANAGER);

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Management"
        title="Admin users"
        description="Review users and patch role assignments directly against the FastAPI admin API."
      />

      {error ? <div className="error-banner">{error}</div> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      <section className="feature-card table-card">
        <div className="table-shell">
          <div className="table-row table-head admin-users-row">
            <span>User</span>
            <span>Email</span>
            <span>Role</span>
            <span>Usage</span>
            <span>Controls</span>
          </div>
          {users.map((user) => (
            <div key={user.id} className="table-row admin-users-row">
              <div className="admin-user-cell">
                <strong>{user.username}</strong>
              </div>
              <span>{user.email}</span>
              <span>
                <span className="role-chip admin-role-chip">{user.role}</span>
              </span>
              <span>
                {isUsageAdmin ? (
                  <button
                    type="button"
                    className="ghost-button admin-save-button"
                    onClick={() => handleToggleUsage(user.id)}
                    disabled={usageBusyUserId === user.id}
                  >
                    {usageBusyUserId === user.id ? "Loading..." : usageOpenUserId === user.id ? "Hide Usage" : "Usage"}
                  </button>
                ) : (
                  <span className="admin-user-meta">Unavailable</span>
                )}
              </span>
              <div className="admin-user-actions">
                <select
                  value={roleDrafts[user.id] || user.role}
                  className="admin-role-select"
                  onChange={(event) => setRoleDrafts((value) => ({ ...value, [user.id]: event.target.value }))}
                  disabled={busyUserId === user.id}
                >
                  {ROLE_OPTIONS.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
                {isAdmin && (roleDrafts[user.id] || user.role) === ROLE_KEYS.ANALYST ? (
                  <select
                    value={managerDrafts[user.id] ?? ""}
                    className="admin-role-select admin-manager-select"
                    onChange={(event) => setManagerDrafts((value) => ({ ...value, [user.id]: event.target.value }))}
                    disabled={busyUserId === user.id}
                  >
                    <option value="">Select manager</option>
                    {managerUsers.map((manager) => (
                      <option key={manager.id} value={manager.id}>
                        {manager.username} ({manager.email})
                      </option>
                    ))}
                  </select>
                ) : null}
                <button
                  type="button"
                  className="ghost-button admin-save-button"
                  onClick={() => handleRoleChange(user.id)}
                  disabled={
                    busyUserId === user.id ||
                    (isAdmin && (roleDrafts[user.id] || user.role) === ROLE_KEYS.ANALYST && !managerDrafts[user.id])
                  }
                >
                  {busyUserId === user.id ? "Saving..." : "Save"}
                </button>
                {canDeleteUsers && user.role !== ROLE_KEYS.ADMIN ? (
                  <button
                    type="button"
                    className="ghost-button danger-button admin-delete-button"
                    onClick={() => handleDeleteUser(user)}
                    disabled={busyUserId === user.id}
                  >
                    {busyUserId === user.id ? "Deleting..." : "Delete"}
                  </button>
                ) : (
                  <span className="admin-user-meta">{user.role === ROLE_KEYS.ADMIN ? "Protected" : "Unavailable"}</span>
                )}
              </div>
              {isUsageAdmin && usageOpenUserId === user.id && usagePanel[user.id] ? (
                <div className="admin-usage-panel">
                  <div className="admin-usage-block">
                    <strong>1) Total tokens spent by the user</strong>
                    <p>
                      {usagePanel[user.id].total_tokens_spent ?? 0} tokens
                      {" | "}
                      ${Number(usagePanel[user.id].total_estimated_cost_usd ?? 0).toFixed(6)}
                    </p>
                  </div>
                  <div className="admin-usage-block">
                    <strong>2) See his/her documents</strong>
                    {usagePanel[user.id].documents?.length ? (
                      <ul>
                        {usagePanel[user.id].documents.map((doc) => (
                          <li key={doc.id}>
                            {doc.title} ({doc.file_type})
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p>No documents found.</p>
                    )}
                  </div>
                  <div className="admin-usage-block">
                    <strong>3) See his/her chats</strong>
                    {usagePanel[user.id].chats?.length ? (
                      <ul>
                        {usagePanel[user.id].chats.map((chat) => (
                          <li key={chat.session_id}>
                            {chat.title || `Session ${chat.session_id}`} - {chat.messages?.length || 0} messages
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p>No chats found.</p>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
