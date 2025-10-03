import '@carbon/styles/css/styles.css'
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import ProtectedRoute from "./components/ProtectedRoute"
import Home from "./pages/Home"
import Login from "./pages/Login"
import NotFound from "./pages/NotFound"
import RecommendationChat from "./pages/RecommendationChat"
import Register from "./pages/Register"


function Logout(){
  localStorage.clear()
  return <Navigate to ="/login" /> 
}

//makes sure there are no conflicts with access tokens as someone is registering
function RegisterAndLogout() {
  localStorage.clear()
  return <Register />
}


function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }
        />
        <Route
          path="/trips/:tripId/chat"
          element={
            <ProtectedRoute>
              <RecommendationChat />
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<Login />} />
        <Route path="/logout" element={<Logout />} />
        <Route path="/register" element={<RegisterAndLogout />} />
        <Route path="*" element={<NotFound />}></Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App