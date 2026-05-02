/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import { deleteUser, getUsers, updateUserRole } from "../lib/api";
import { ROLE_KEYS } from "../lib/roles";
import { useAuth } from "../context/AuthContext";

const ROLE_OPTIONS = Object.values(ROLE_KEYS);

/**
 * Detailed function explanation:
 * - Purpose: `AdminUsersPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [busyUserId, setBusyUserId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  /**
   * Detailed function explanation:
   * - Purpose: `loadUsers` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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

  /**
   * Detailed function explanation:
   * - Purpose: `handleRoleChange` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
  async function handleRoleChange(userId, role) {
    setBusyUserId(userId);
    setError("");
    setSuccess("");
    try {
      await updateUserRole(userId, role);
      setSuccess("User role updated successfully.");
      await loadUsers();
    } catch (roleError) {
      setError(roleError.message || "Role update failed.");
    } finally {
      setBusyUserId(null);
    }
  }

  /**
   * Detailed function explanation:
   * - Purpose: `handleDeleteUser` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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

  const canDeleteUsers = currentUser?.role === ROLE_KEYS.ADMIN;

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
            <span>Status</span>
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
                <span className={`status-chip admin-status-chip ${user.is_active ? "is-active" : "is-pending"}`}>
                  <span className={`status-dot admin-status-dot ${user.is_active ? "is-active" : "is-pending"}`} />
                  {user.is_active ? "Active" : "Pending"}
                </span>
              </span>
              <div className="admin-user-actions">
                <select
                  defaultValue={user.role}
                  className="admin-role-select"
                  onChange={(event) => handleRoleChange(user.id, event.target.value)}
                  disabled={busyUserId === user.id}
                >
                  {ROLE_OPTIONS.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
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
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
