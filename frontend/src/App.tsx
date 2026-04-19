/**
 * File purpose:
 * - Root React component for the frontend.
 * - Mounts the upload UI component.
 */

import Upload from "./components/Upload";

export default function App() {
  return (
    <main className="app-shell">
      <h1>RAG Ingestion</h1>
      <Upload />
    </main>
  );
}