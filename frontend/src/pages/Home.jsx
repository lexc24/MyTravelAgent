// pages/Home.jsx

import { Add, ArrowRight, ChevronDown } from "@carbon/icons-react";
import {
  Button,
  Column,
  ComboButton,
  Grid,
  InlineLoading,
  MenuItem,
  Stack,
  Tile,
  ToastNotification,
} from "@carbon/react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "../constants";

const Home = () => {
  const navigate = useNavigate();
  const [trips, setTrips] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);
  const [username, setUsername] = useState("Username");

  useEffect(() => {
    fetchTrips();
    fetchUserInfo();
  }, []);

  const fetchUserInfo = async () => {
    try {
      const token = localStorage.getItem(ACCESS_TOKEN);
      if (token) {
        try {
          // Decode JWT token
          const base64Url = token.split(".")[1];
          const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
          const jsonPayload = decodeURIComponent(
            atob(base64)
              .split("")
              .map(function (c) {
                return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
              })
              .join("")
          );
          const decoded = JSON.parse(jsonPayload);

          console.log("Decoded JWT token:", decoded); // Debug log to see token structure

          // Try different possible fields where username might be stored
          const possibleUsername =
            decoded.username ||
            decoded.user_name ||
            decoded.name ||
            decoded.sub ||
            decoded.email;

          if (possibleUsername) {
            // Capitalize first letter of username
            const capitalizedUsername =
              possibleUsername.charAt(0).toUpperCase() +
              possibleUsername.slice(1);
            setUsername(capitalizedUsername);
          } else {
            console.log("Username not found in token");
            // If we can't get it from token, try fetching from an API endpoint
            // You might need to create this endpoint
            try {
              const response = await api.get("/api/user/me/");
              if (response.data.username) {
                const capitalizedUsername =
                  response.data.username.charAt(0).toUpperCase() +
                  response.data.username.slice(1);
                setUsername(capitalizedUsername);
              }
            } catch (apiError) {
              console.log("No user endpoint available");
            }
          }
        } catch (e) {
          console.error("Error decoding token:", e);
        }
      }
    } catch (err) {
      console.error("Error fetching user info:", err);
    }
  };

  const fetchTrips = async () => {
    try {
      setIsLoading(true);
      const response = await api.get("/api/trips/");
      setTrips(response.data);
    } catch (err) {
      console.error("Error fetching trips:", err);
      setError("Failed to load trips");
    } finally {
      setIsLoading(false);
    }
  };

  const createNewTrip = async () => {
    try {
      setIsCreating(true);
      setError(null);

      const response = await api.post("/api/trips/", {
        title: `Trip ${new Date().toLocaleDateString()}`,
        description: "Planning a new adventure",
      });

      navigate(`/trips/${response.data.id}/chat`);
    } catch (err) {
      console.error("Error creating trip:", err);
      setError("Failed to create new trip. Please try again.");
      setIsCreating(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(ACCESS_TOKEN);
    localStorage.removeItem(REFRESH_TOKEN);
    navigate("/login");
  };

  const goToTripChat = (tripId) => {
    navigate(`/trips/${tripId}/chat`);
  };

  if (isLoading) {
    return (
      <div style={{ padding: "2rem" }}>
        <InlineLoading description="Loading your trips..." />
      </div>
    );
  }

  return (
    <div style={{ padding: "2rem" }}>
      <Stack gap={6}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <h1>Your Trips</h1>

          <ComboButton
            label={username}
            kind="primary"
            onClick={() => {}} // No action for main button click
            renderIcon={ChevronDown}
            size="md"
          >
            <MenuItem
              label="Create New Trip"
              onClick={createNewTrip}
              disabled={isCreating}
            />
            <MenuItem label="Logout" onClick={handleLogout} />
          </ComboButton>
        </div>

        {trips.length === 0 ? (
          <Tile style={{ textAlign: "center", padding: "3rem" }}>
            <h3>No trips yet</h3>
            <p style={{ marginTop: "1rem", marginBottom: "2rem" }}>
              Start planning your next adventure!
            </p>
            <Button
              renderIcon={Add}
              onClick={createNewTrip}
              disabled={isCreating}
            >
              {isCreating ? "Creating..." : "Create Your First Trip"}
            </Button>
          </Tile>
        ) : (
          <Grid>
            {trips.map((trip) => (
              <Column key={trip.id} sm={4} md={4} lg={4}>
                <Tile
                  style={{
                    padding: "1.5rem",
                    cursor: "pointer",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                  onClick={() => goToTripChat(trip.id)}
                >
                  <div>
                    <h3>{trip.title}</h3>
                    {trip.destination && (
                      <p style={{ marginTop: "0.5rem", color: "#0f62fe" }}>
                        📍 {trip.destination.name}
                      </p>
                    )}
                    <p style={{ marginTop: "0.5rem", fontSize: "0.875rem" }}>
                      Status: {trip.status.replace("_", " ")}
                    </p>
                    <p
                      style={{
                        marginTop: "0.5rem",
                        fontSize: "0.75rem",
                        opacity: 0.7,
                      }}
                    >
                      Created: {new Date(trip.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    kind="ghost"
                    size="sm"
                    renderIcon={ArrowRight}
                    style={{ marginTop: "1rem" }}
                  >
                    Continue Planning
                  </Button>
                </Tile>
              </Column>
            ))}
          </Grid>
        )}
      </Stack>

      {error && (
        <ToastNotification
          kind="error"
          title="Error"
          subtitle={error}
          timeout={5000}
          onClose={() => setError(null)}
          style={{ position: "fixed", bottom: 20, right: 20, minWidth: 300 }}
        />
      )}
    </div>
  );
};

export default Home;
