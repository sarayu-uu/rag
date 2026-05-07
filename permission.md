# Permission Model and Access Flow

## Roles

- `Admin`
  - Global access to all documents.
  - Can read, query, and edit/delete all documents.
  - Can manage users and document permissions.

- `Manager`
  - Global access for `read` and `query` across all documents.
  - Does not get global `edit` by role default.
  - Can access admin endpoints for operational management.

- `Analyst`
  - No global document access by role.
  - Can access:
    - Documents they uploaded (owner access).
    - Documents granted via `permissions` table (user-level or role-level grants).

- `Viewer`
  - No global document access by role.
  - Can access:
    - Documents they uploaded (owner access).
    - Documents granted via `permissions` table.

- `Guest`
  - No global document access by role.
  - Can access:
    - Documents they uploaded (owner access).
    - Documents granted via `permissions` table.

## Permission Sources

Document access is granted from one or more of these sources:

1. Role-level global access (`Admin`, `Manager` for read/query only).
2. Ownership (`documents.upload_user_id == current_user.id`).
3. Explicit permission rows in `permissions` table:
   - `permissions.user_id == current_user.id` or
   - `permissions.role_id == current_user.role_id`
   - with one of:
     - `can_read`
     - `can_query`
     - `can_edit`

## Route-Level Access Enforcement

- Document listing/details:
  - Uses `document_access_filter(..., permission_field="can_read")`.
  - Only documents readable by the current user are returned.

- Document delete:
  - Uses `document_access_filter(..., permission_field="can_edit")`.
  - Delete is only allowed if user has edit access.

- Retrieval endpoints (`/retrieval/search`, `/chat/query`):
  - Compute `allowed_document_ids = accessible_document_ids(..., permission_field="can_query")`.
  - Retrieval is restricted to those document ids only.

## Retrieval-Level Enforcement (Chunk Scope)

Even after route-level filtering, retrieval service keeps document scoping:

1. `search_chunk_text(...)` receives allowed `document_ids`.
2. Semantic retrieval applies metadata filter in vector store query:
   - `document_id in allowed_document_ids`
   - optional `owner_user_id` when provided
3. Keyword retrieval query applies SQL filter:
   - `DocumentChunk.document_id.in_(allowed_document_ids)`
   - optional `owner_user_id` when provided
4. Hybrid reranking runs only on this already-filtered candidate set.

Result: chunks can only come from documents the user is allowed to query.

## Admin Permission Management

- Endpoint: `PATCH /admin/documents/{document_id}/permissions`
- Supports grants by:
  - `user_id` (user-specific)
  - `role` or `role_id` (role-wide)
- Writable flags:
  - `can_read`
  - `can_query`
  - `can_edit`

These flags are later enforced through `document_access_filter` and `accessible_document_ids`.
