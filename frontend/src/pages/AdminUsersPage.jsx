import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import { getUsers, updateUserRole } from "../lib/api";
import { ROLE_KEYS } from "../lib/roles";

const ROLE_OPTIONS = Object.values(ROLE_KEYS);

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [busyUserId, setBusyUserId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

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
          <div className="table-row table-head">
            <span>User</span>
            <span>Email</span>
            <span>Role</span>
            <span>Status</span>
            <span>Update</span>
          </div>
          {users.map((user) => (
            <div key={user.id} className="table-row">
              <span>{user.username}</span>
              <span>{user.email}</span>
              <span>{user.role}</span>
              <span>{user.is_active ? "Active" : "Pending"}</span>
              <span>
                <select
                  defaultValue={user.role}
                  onChange={(event) => handleRoleChange(user.id, event.target.value)}
                  disabled={busyUserId === user.id}
                >
                  {ROLE_OPTIONS.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
