# Frontend Integration Documentation

> **Framework**: React 19.1 + Vite 7.1 | **UI Library**: IBM Carbon Design | **Status**: ✅ Core features complete

## Overview

This document covers the React frontend architecture, component structure, state management, and API integration with the Django backend.

## Table of Contents
- [Frontend Architecture](#frontend-architecture)
- [Main Components](#main-components)
- [API Integration](#api-integration)
- [Routing and Navigation](#routing-and-navigation)
- [State Management Strategy](#state-management-strategy)
- [Styling Approach](#styling-approach)

---

## Frontend Architecture

```
frontend/
├── public/                        # Static assets
├── src/
│   ├── pages/                    # Page components
│   │   ├── Home.jsx              # Trip dashboard (✅ Complete)
│   │   ├── RecommendationChat.jsx    # AI chat interface (✅ Complete, 595 LOC) ⭐
│   │   ├── Login.jsx             # Auth form (✅ Complete)
│   │   ├── Register.jsx          # Registration (✅ Complete)
│   │   └── NotFound.jsx          # 404 page
│   │
│   ├── components/               # Reusable components
│   │   ├── Form.jsx              # Auth form wrapper
│   │   ├── ProtectedRoute.jsx   # Auth guard (✅ Critical)
│   │   └── LoadingIndicator.jsx # Loading states
│   │
│   ├── styles/                   # SCSS modules
│   │   ├── Home.scss
│   │   ├── Login.scss
│   │   └── RecommendationChat.scss
│   │
│   ├── App.jsx                   # Root component + routing (50 LOC)
│   ├── main.jsx                  # React entry point
│   ├── api.js                    # Axios instance (24 LOC) ⭐
│   └── constants.js              # App constants
│
├── package.json                  # Dependencies (11 packages)
├── vite.config.js               # Vite configuration
├── nginx.conf                   # Production server config
├── Dockerfile                   # Multi-stage build (Node + Nginx)
└── .env                         # Environment variables
```

---

## Main Components

### App.jsx - Root Router

File: `frontend/src/App.jsx`

```jsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";

function Logout() {
  localStorage.clear();              // Clear JWT tokens
  return <Navigate to="/login" />;
}

function RegisterAndLogout() {
  localStorage.clear();              // Prevent token conflicts
  return <Register />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={
          <ProtectedRoute><Home /></ProtectedRoute>
        } />
        <Route path="/trips/:tripId/chat" element={
          <ProtectedRoute><RecommendationChat /></ProtectedRoute>
        } />
        <Route path="/login" element={<Login />} />
        <Route path="/logout" element={<Logout />} />
        <Route path="/register" element={<RegisterAndLogout />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**Key Patterns:**

1. **Logout as Component**
   - Clears `localStorage` (removes JWT tokens)
   - Redirects to `/login`
   - Simple, declarative

2. **RegisterAndLogout**
   - Prevents token conflicts (old user logged in, tries to register new account)
   - Clears storage before showing register form

3. **Protected Routes**
   - Wraps routes requiring authentication
   - Checks for JWT token, redirects to `/login` if missing

---

### ProtectedRoute.jsx - Authentication Guard

File: `frontend/src/components/ProtectedRoute.jsx` (not shown in reads, but standard pattern)

```jsx
import { Navigate } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import { ACCESS_TOKEN } from "../constants";

function ProtectedRoute({ children }) {
  const token = localStorage.getItem(ACCESS_TOKEN);

  if (!token) {
    return <Navigate to="/login" />;
  }

  try {
    const decoded = jwtDecode(token);
    const now = Date.now() / 1000;

    if (decoded.exp < now) {
      // Token expired
      localStorage.removeItem(ACCESS_TOKEN);
      return <Navigate to="/login" />;
    }

    return children;  // Token valid, render protected content
  } catch (error) {
    // Invalid token
    return <Navigate to="/login" />;
  }
}
```

**Why Client-Side Token Validation?**
- Avoid unnecessary API calls (check token before hitting backend)
- Immediate redirect to login (better UX)
- Backend still validates (client-side check is UX, not security)

---

### Home.jsx - Trip Dashboard

File: `frontend/src/pages/Home.jsx` (not shown in reads, typical React CRUD)

**Key Features:**
- List all user's trips (paginated)
- Create new trip modal
- Click trip → Navigate to `/trips/{id}/chat`
- Filter by status
- Delete trip

**State Management:**
```jsx
const [trips, setTrips] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  const fetchTrips = async () => {
    try {
      const response = await api.get("/api/trips/");
      setTrips(response.data.results);  // Paginated response
    } catch (err) {
      setError(err.response?.data?.error || "Failed to load trips");
    } finally {
      setLoading(false);
    }
  };

  fetchTrips();
}, []);
```

**IBM Carbon Components Used:**
- `<DataTable>` for trip list
- `<Modal>` for create trip form
- `<Button>` for actions
- `<Tag>` for trip status badges

---

### RecommendationChat.jsx - AI Chat Interface ⭐

File: `frontend/src/pages/RecommendationChat.jsx` (595 lines)

This is the **most complex frontend component** - handles the entire AI conversation flow.

#### Component Structure

```jsx
const RecommendationChat = () => {
  const { tripId } = useParams();                    // Get tripId from URL
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  // State
  const [messages, setMessages] = useState([]);      // Chat history
  const [inputValue, setInputValue] = useState("");  // Text input
  const [isLoading, setIsLoading] = useState(false); // API call in progress
  const [currentStage, setCurrentStage] = useState("initial");  // Workflow stage
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [destinations, setDestinations] = useState(null);  // Final recommendations
  const [error, setError] = useState(null);
  const [tripTitle, setTripTitle] = useState("Your Trip");

  // Load conversation history on mount
  useEffect(() => {
    loadConversation();
  }, [tripId]);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
```

---

#### Send Message Function

```jsx
const sendMessage = async () => {
  if (!inputValue.trim() || isLoading) return;

  const userMessage = inputValue.trim();
  setInputValue("");
  setIsLoading(true);
  setError(null);

  // Optimistic UI: Add user message immediately
  const tempUserMessage = {
    id: `temp-${Date.now()}`,
    is_user: true,
    content: userMessage,
    timestamp: new Date().toISOString(),
  };
  setMessages((prev) => [...prev, tempUserMessage]);

  try {
    const response = await api.post("/destination_search/chat/", {
      trip_id: parseInt(tripId),
      message: userMessage,
    });

    // Replace temp message with real ones from backend
    const userMsg = { ...response.data.user_message, is_user: true };
    const aiMsg = { ...response.data.ai_message, is_user: false };

    setMessages((prev) => [
      ...prev.filter((msg) => msg.id !== tempUserMessage.id),  // Remove temp
      userMsg,
      aiMsg,
    ]);

    // Update stage and progress
    setCurrentStage(response.data.stage);
    setProgress({
      current: response.data.metadata?.question_number || 0,
      total: response.data.metadata?.total_questions || 0,
    });

    // Update destinations if provided
    if (response.data.destinations) {
      setDestinations(response.data.destinations);
    }
  } catch (err) {
    // Remove temp message on error
    setMessages((prev) => prev.filter((msg) => msg.id !== tempUserMessage.id));
    setError(err.response?.data?.error || "Failed to send message");
  } finally {
    setIsLoading(false);
  }
};
```

**Key UX Patterns:**

1. **Optimistic UI Update**
   - Add user message immediately (before API response)
   - Replace with real message when backend responds
   - Remove if API fails

2. **Error Handling**
   - Show error toast (IBM Carbon `<ToastNotification>`)
   - Don't lose user's input (except on success)

3. **Stage Tracking**
   - Backend sends `stage` in response
   - Frontend shows different UI based on stage:
     - `initial`: Welcome message
     - `asking_clarifications`: Progress indicator
     - `destinations_complete`: Destination cards

---

#### UI Structure

```jsx
return (
  <FlexGrid fullWidth>
    {/* Header with progress indicator */}
    <Layer>
      <ProgressIndicator currentIndex={...}>
        <ProgressStep label="Share Preferences" />
        <ProgressStep label="Answer Questions" />
        <ProgressStep label="Review Destinations" />
        <ProgressStep label="Select Destination" />
      </ProgressIndicator>
    </Layer>

    {/* Messages Area */}
    <div style={{ overflowY: "auto", maxHeight: "calc(100vh - 300px)" }}>
      {messages.map((message) => (
        <div key={message.id} style={{
          display: "flex",
          justifyContent: message.is_user ? "flex-end" : "flex-start",
        }}>
          <div style={{
            backgroundColor: message.is_user ? "#0f62fe" : "#f4f4f4",
            color: message.is_user ? "white" : "black",
            padding: "0.75rem 1rem",
            borderRadius: message.is_user ? "16px 16px 0 16px" : "16px 16px 16px 0",
          }}>
            {message.content}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />  {/* Auto-scroll anchor */}
    </div>

    {/* Destination Cards (if stage === "destinations_complete") */}
    {destinations && currentStage === "destinations_complete" && (
      <Grid>
        {destinations.map((dest, index) => (
          <Column key={index} sm={4} md={4} lg={4}>
            <ClickableTile onClick={() => selectDestination(dest)}>
              <h4>{dest.name}</h4>
              <Tag type="blue">{dest.country}</Tag>
              <p>{dest.description}</p>
              <Button renderIcon={Checkmark}>Choose This</Button>
            </ClickableTile>
          </Column>
        ))}
      </Grid>
    )}

    {/* Input Area */}
    <Layer>
      <TextArea
        placeholder={
          currentStage === "initial" ? "Describe your ideal vacation..." :
          currentStage === "asking_clarifications" ? "Type your answer..." :
          "Ask about the destinations or make your choice..."
        }
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyPress={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
          }
        }}
        disabled={isLoading || currentStage === "commitment_detected"}
      />
      <Button
        renderIcon={Send}
        onClick={sendMessage}
        disabled={!inputValue.trim() || isLoading}
      />
    </Layer>
  </FlexGrid>
);
```

**UI Highlights:**

1. **Chat Bubbles**
   - User messages: Blue, right-aligned, rounded corners
   - AI messages: Gray, left-aligned, opposite corners

2. **Progress Indicator**
   - Shows 4 steps: Share Preferences → Answer Questions → Review Destinations → Select Destination
   - Current step highlighted
   - Updates as conversation progresses

3. **Destination Cards**
   - Only shown when `stage === "destinations_complete"`
   - Clickable tiles with IBM Carbon's `<ClickableTile>`
   - Auto-populate input with "Let's go with {destination}!" on click

4. **Dynamic Placeholder**
   - Changes based on stage (better UX than static placeholder)

---

#### Destination Selection

```jsx
const selectDestination = (destination) => {
  setInputValue(`Let's go with ${destination.name}!`);
  // Auto-send after a moment for smooth UX
  setTimeout(() => sendMessage(), 100);
};
```

**Why `setTimeout`?**
- Allows user to see input populate before sending
- Better UX than instant send (feels more natural)

---

### Login.jsx & Register.jsx

File: `frontend/src/pages/Login.jsx` (similar pattern for Register)

```jsx
const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await api.post("/api/token", { username, password });
      localStorage.setItem(ACCESS_TOKEN, response.data.access);
      localStorage.setItem(REFRESH_TOKEN, response.data.refresh);
      navigate("/");  // Redirect to home
    } catch (error) {
      alert(error.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form onSubmit={handleSubmit}>
      <TextInput
        labelText="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />
      <PasswordInput
        labelText="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" disabled={loading}>
        {loading ? <InlineLoading /> : "Log In"}
      </Button>
    </Form>
  );
};
```

**Pattern**: Store JWT tokens in `localStorage`, navigate to home on success.

---

## API Integration

### Axios Instance Configuration

File: `frontend/src/api.js` (24 lines)

```javascript
import axios from "axios";
import { ACCESS_TOKEN } from "./constants";

const apiUrl = "https://my-travel-agent.onrender.com";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : apiUrl,
});

// Request interceptor: Inject JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;
```

**Why This Pattern:**

1. **Centralized Base URL**
   - Environment variable (`VITE_API_URL`) for local dev
   - Falls back to production URL
   - Example: `VITE_API_URL=http://localhost:8000`

2. **Automatic Token Injection**
   - Every request gets `Authorization: Bearer {JWT}` header
   - No need to manually add header in every API call

3. **DRY Principle**
   - Import `api` instead of `axios` everywhere
   - Configuration in one place

**Usage:**
```javascript
import api from "../api";

// GET request
const response = await api.get("/api/trips/");

// POST request
const response = await api.post("/api/trips/", { title: "New Trip" });
```

---

### Missing: Automatic Token Refresh

**Current Limitation**: If access token expires (30 min), user must manually log out and log back in.

**What Should Happen:**
```javascript
// Response interceptor (NOT IMPLEMENTED)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Try to refresh token
      const refreshToken = localStorage.getItem(REFRESH_TOKEN);
      if (refreshToken) {
        try {
          const response = await axios.post("/api/token/refresh", {
            refresh: refreshToken,
          });
          localStorage.setItem(ACCESS_TOKEN, response.data.access);
          // Retry original request with new token
          error.config.headers.Authorization = `Bearer ${response.data.access}`;
          return axios(error.config);
        } catch (refreshError) {
          // Refresh failed, redirect to login
          localStorage.clear();
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);
```

---

## Routing and Navigation

### Route Structure

| Route | Component | Protected | Description |
|-------|-----------|-----------|-------------|
| `/` | `Home` | ✅ Yes | Trip dashboard |
| `/trips/:tripId/chat` | `RecommendationChat` | ✅ Yes | AI chat interface |
| `/login` | `Login` | ❌ No | Login form |
| `/register` | `Register` | ❌ No | Registration form |
| `/logout` | `Logout` | ❌ No | Clear tokens, redirect |
| `*` | `NotFound` | ❌ No | 404 page |

---

### Programmatic Navigation

```jsx
import { useNavigate } from "react-router-dom";

const Component = () => {
  const navigate = useNavigate();

  const goToChat = (tripId) => {
    navigate(`/trips/${tripId}/chat`);
  };

  const goBack = () => {
    navigate(-1);  // Go back one page
  };

  return <Button onClick={() => goToChat(10)}>Start Chat</Button>;
};
```

---

### URL Parameters

```jsx
import { useParams } from "react-router-dom";

const RecommendationChat = () => {
  const { tripId } = useParams();  // Extract :tripId from URL

  useEffect(() => {
    // Fetch trip details using tripId
    api.get(`/destination_search/conversations/${tripId}/`);
  }, [tripId]);
};
```

---

## State Management Strategy

### No Redux or Context API

**Decision**: Use **React hooks only** (useState, useEffect, useRef).

**Why?**
- Simple application (no complex shared state)
- Each page is independent (no data shared between Home and Chat)
- JWT token in `localStorage` (persistent across pages)

**What State is Managed:**
- **Local state**: Component-specific (messages, loading, error)
- **URL parameters**: Trip ID (via React Router)
- **LocalStorage**: JWT tokens (access, refresh)

**When We'd Need Redux:**
- If user preferences needed across multiple pages
- If trip list needed to update from chat page
- If complex state transitions (multi-step forms)

---

### Data Fetching Pattern

```jsx
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  const fetchData = async () => {
    try {
      setLoading(true);
      const response = await api.get("/api/trips/");
      setData(response.data);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  fetchData();
}, []);

if (loading) return <SkeletonText />;
if (error) return <InlineNotification kind="error" title={error} />;
return <DataDisplay data={data} />;
```

**Pattern**: Loading → Success → Error (three states).

---

## Styling Approach

### IBM Carbon Design System

**Why Carbon?**
- Enterprise-grade components (accessibility built-in)
- Consistent design language
- Less custom CSS needed
- Better than Material-UI for business applications

**Components Used:**
- Layout: `<FlexGrid>`, `<Row>`, `<Column>`, `<Layer>`
- Forms: `<TextInput>`, `<TextArea>`, `<Button>`, `<PasswordInput>`
- Data: `<DataTable>`, `<Tag>`, `<Tile>`, `<ClickableTile>`
- Feedback: `<InlineNotification>`, `<ToastNotification>`, `<InlineLoading>`
- Navigation: `<ProgressIndicator>`, `<ProgressStep>`

---

### SCSS Modules

File: `frontend/src/styles/RecommendationChat.scss` (not shown, but standard pattern)

```scss
.chat-container {
  height: 100vh;
  display: flex;
  flex-direction: column;

  .messages-area {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;

    .message-bubble {
      max-width: 70%;
      margin-bottom: 0.75rem;

      &.user {
        background-color: #0f62fe;  // IBM Carbon blue
        color: white;
        margin-left: auto;
      }

      &.ai {
        background-color: #f4f4f4;
        color: black;
      }
    }
  }
}
```

**Pattern**: Component-specific SCSS files, scoped styles.

---

## Key Takeaways

**Frontend Strengths:**
1. **Optimistic UI**: Immediate feedback (user message appears before API response)
2. **Protected Routes**: Automatic redirect to login if not authenticated
3. **Auto Token Injection**: Axios interceptor adds JWT to every request
4. **Progressive UI**: Different UI based on conversation stage
5. **IBM Carbon**: Consistent, accessible design system

**Missing Features:**
- [ ] Automatic token refresh (manual logout required after 30 min)
- [ ] Global state management (Redux/Context) - not needed yet
- [ ] WebSocket real-time updates - using HTTP polling currently
- [ ] Offline support - all features require internet
- [ ] Mobile-responsive improvements - desktop-first currently

**Interview Talking Points:**
- "We use optimistic UI updates in the chat - user messages appear immediately, then we replace with the server response. This makes the UI feel instant even with 2-3 second LLM response times."
- "Protected routes check JWT expiry client-side before rendering, preventing unnecessary API calls and providing immediate redirects to login."
- "We chose not to use Redux because each page is self-contained - the chat doesn't need to know about the trip list, and vice versa. Adding Redux would be over-engineering at this stage."

---

**Related Documentation:**
- [API_DESIGN.md](./API_DESIGN.md) - Backend endpoints this frontend calls
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System overview
- [LANGGRAPH_WORKFLOW.md](./LANGGRAPH_WORKFLOW.md) - What happens on the backend when user sends a message
