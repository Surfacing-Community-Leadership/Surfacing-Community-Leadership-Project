import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import Landing from "./pages/Landing.jsx";
import MapHome from "./pages/MapHome.jsx";
import EventDetail from "./pages/EventDetail.jsx";
import CreateEvent from "./pages/CreateEvent.jsx";
import EditEvent from "./pages/EditEvent.jsx";
import MyEvents from "./pages/MyEvents.jsx";
import Profile from "./pages/Profile.jsx";
import PublicProfile from "./pages/PublicProfile.jsx";
import Connections from "./pages/Connections.jsx";
import Blocks from "./pages/Blocks.jsx";

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Authenticated routes share the Layout shell */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/map" element={<MapHome />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/events/new" element={<CreateEvent />} />
        <Route path="/my-events" element={<MyEvents />} />
        <Route path="/events/:id" element={<EventDetail />} />
        <Route path="/events/:id/edit" element={<EditEvent />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/profile/:userId" element={<PublicProfile />} />
        <Route path="/connections" element={<Connections />} />
        <Route path="/blocks" element={<Blocks />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
