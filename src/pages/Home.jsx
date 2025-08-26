import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  ContainedList,
  ContainedListItem,
  Grid,
  Column,
  Content,
  Header,
  HeaderContainer,
  HeaderName,
  SkipToContent,
  Loading,
  InlineNotification,
  Modal,
  MenuButton,
  MenuItem,
  Checkbox,
} from "@carbon/react";
import { Add, UserAvatar } from "@carbon/icons-react";
import api from "../api";
import { ACCESS_TOKEN } from "../constants";

function Home() {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [selectedTrips, setSelectedTrips] = useState(new Set());
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchUserInfo();
    fetchTrips();
  }, []);

  const fetchUserInfo = async () => {
    try {
      const response = await api.get("/api/user/profile/");
      setUser(response.data);
    } catch (error) {
      console.error("Error fetching user info:", error);
      setUser({ username: "User" });
    }
  };

  const fetchTrips = async () => {
    try {
      const response = await api.get("/api/trips/");
      // Filter for upcoming trips only
      const now = new Date();
      const upcomingTrips = response.data.filter(trip => 
        new Date(trip.start_date) >= now
      );
      setTrips(upcomingTrips);
    } catch (error) {
      console.error("Error fetching trips:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleTripSelect = (tripId) => {
    const newSelected = new Set(selectedTrips);
    if (newSelected.has(tripId)) {
      newSelected.delete(tripId);
    } else {
      newSelected.add(tripId);
    }
    setSelectedTrips(newSelected);
  };

  const handleDeleteSelected = async () => {
    try {
      await Promise.all(
        Array.from(selectedTrips).map(tripId =>
          api.delete(`/api/trips/${tripId}/`)
        )
      );
      
      setTrips(trips.filter(trip => !selectedTrips.has(trip.id)));
      setSelectedTrips(new Set());
      setShowDeleteModal(false);
    } catch (error) {
      console.error("Error deleting trips:", error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(ACCESS_TOKEN);
    localStorage.removeItem("refresh_token");
    navigate("/login");
  };

  const handleTripClick = (tripId) => {
    navigate(`/trip/${tripId}`);
  };

  if (loading) {
    return <Loading description="Loading trips..." withOverlay={true} />;
  }

  return (
    <div>
      <HeaderContainer
        render={() => (
          <Header aria-label="MyTravelAgent">
            <SkipToContent />
            <HeaderName href="/" prefix="">
              MyTravelAgent
            </HeaderName>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
              <MenuButton
                label={user?.username || "User"}
                kind="ghost"
                renderIcon={UserAvatar}
              >
                <MenuItem 
                  label="Logout" 
                  onClick={handleLogout}
                />
              </MenuButton>
            </div>
          </Header>
        )}
      />

      <Content>
        <Grid>
          <Column lg={16}>
            <div style={{ marginBottom: '2rem' }}>
              <h1 style={{ 
                fontSize: '2.5rem', 
                fontWeight: '400',
                marginBottom: '2rem',
                color: 'var(--cds-text-primary)'
              }}>
                My Trips
              </h1>
            </div>

            {/* Delete Selected Button */}
            {selectedTrips.size > 0 && (
              <div style={{ marginBottom: '1rem' }}>
                <Button
                  kind="danger"
                  size="sm"
                  onClick={() => setShowDeleteModal(true)}
                >
                  Delete Selected ({selectedTrips.size})
                </Button>
              </div>
            )}

            {trips.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '4rem 2rem',
                background: 'var(--cds-layer)',
                borderRadius: '8px',
                border: '1px solid var(--cds-border-subtle)'
              }}>
                <h3 style={{ 
                  marginBottom: '1rem', 
                  color: 'var(--cds-text-primary)',
                  fontWeight: '400'
                }}>
                  No upcoming trips yet!
                </h3>
                <p style={{ 
                  marginBottom: '2rem', 
                  color: 'var(--cds-text-secondary)' 
                }}>
                  Create your first trip to get started planning your vacation.
                </p>
                <Button
                  renderIcon={Add}
                  onClick={() => navigate("/create-trip")}
                >
                  Create Your First Trip
                </Button>
              </div>
            ) : (
              <ContainedList 
                label="Upcoming Trips"
                action={
                  <Button
                    renderIcon={Add}
                    size="sm"
                    onClick={() => navigate("/create-trip")}
                  >
                    Add Trip
                  </Button>
                }
              >
                {trips.map(trip => (
                  <ContainedListItem
                    key={trip.id}
                    action={
                      <Checkbox
                        id={`trip-${trip.id}`}
                        labelText=""
                        checked={selectedTrips.has(trip.id)}
                        onChange={() => handleTripSelect(trip.id)}
                      />
                    }
                    onClick={() => handleTripClick(trip.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      width: '100%'
                    }}>
                      <span style={{ 
                        color: 'var(--cds-text-primary)',
                        fontWeight: '400'
                      }}>
                        {trip.destination}
                      </span>
                      <span style={{ 
                        color: 'var(--cds-text-secondary)',
                        fontSize: '0.9rem'
                      }}>
                        {new Date(trip.start_date).toLocaleDateString('en-US', { 
                          month: 'short', 
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </span>
                    </div>
                  </ContainedListItem>
                ))}
              </ContainedList>
            )}
          </Column>
        </Grid>
      </Content>

      {/* Delete Confirmation Modal */}
      <Modal
        open={showDeleteModal}
        danger
        modalHeading="Delete trips"
        modalLabel="Confirm deletion"
        primaryButtonText="Delete"
        secondaryButtonText="Cancel"
        onRequestClose={() => setShowDeleteModal(false)}
        onRequestSubmit={handleDeleteSelected}
      >
        <p>
          Are you sure you want to delete {selectedTrips.size} trip(s)? 
          This action cannot be undone.
        </p>
      </Modal>
    </div>
  );
}

export default Home;