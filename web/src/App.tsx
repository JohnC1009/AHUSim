import { Navigate, Route, Routes } from "react-router-dom";
import { ConditionsPage } from "./pages/Conditions.tsx";
import { ExportPage } from "./pages/Export.tsx";
import { ProjectPage } from "./pages/Project.tsx";
import { ProjectsPage } from "./pages/Projects.tsx";
import { ResultsPage } from "./pages/Results.tsx";
import { SequencePage } from "./pages/Sequence.tsx";
import { SettingsPage } from "./pages/Settings.tsx";
import { UnitLayout } from "./pages/UnitLayout.tsx";
import { Workspace } from "./pages/Workspace.tsx";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/projects/:id" element={<ProjectPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/units/:id" element={<UnitLayout />}>
        <Route index element={<Workspace />} />
        <Route path="sequence" element={<SequencePage />} />
        <Route path="conditions" element={<ConditionsPage />} />
        <Route path="results" element={<ResultsPage />} />
        <Route path="export" element={<ExportPage />} />
      </Route>
    </Routes>
  );
}
