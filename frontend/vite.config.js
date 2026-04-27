import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
/**
 * File purpose:
 * - Configures Vite for React + TypeScript development and builds.
 */
export default defineConfig({
    plugins: [react()],
});
