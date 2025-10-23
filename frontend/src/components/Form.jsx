import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Form,
  FormGroup,
  TextInput,
  Grid,
  Column,
  Content,
  Header,
  HeaderContainer,
  HeaderName,
  SkipToContent,
  InlineNotification,
  Loading,
  Tile,
} from "@carbon/react";
import { Login as LoginIcon, UserFollow } from "@carbon/icons-react";
import api from "../api";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "../constants";

function FormComponent({ route, method }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const navigate = useNavigate();

  const isLogin = method === "login";
  const title = isLogin ? "Sign In" : "Create Account";
  const buttonText = isLogin ? "Sign In" : "Register";
  const Icon = isLogin ? LoginIcon : UserFollow;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setNotification(null);

    try {
      const res = await api.post(route, { username, password });

      if (isLogin) {
        localStorage.setItem(ACCESS_TOKEN, res.data.access);
        localStorage.setItem(REFRESH_TOKEN, res.data.refresh);
        setNotification({
          kind: "success",
          title: "Welcome back!",
          subtitle: "Redirecting to your dashboard...",
        });

        setTimeout(() => {
          navigate("/");
        }, 1500);
      } else {
        setNotification({
          kind: "success",
          title: "Account created!",
          subtitle: "Please sign in with your new account.",
        });

        setTimeout(() => {
          navigate("/login");
        }, 2000);
      }
    } catch (error) {
      console.error("Authentication error:", error);
      let errorMessage = "An error occurred. Please try again.";

      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.data?.username) {
        errorMessage = error.response.data.username[0];
      } else if (error.response?.data?.password) {
        errorMessage = error.response.data.password[0];
      } else if (error.response?.status === 401) {
        errorMessage = "Invalid username or password.";
      }

      setNotification({
        kind: "error",
        title: isLogin ? "Sign in failed" : "Registration failed",
        subtitle: errorMessage,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <HeaderContainer
        render={() => (
          <Header aria-label="Travel Planner">
            <SkipToContent />
            <HeaderName href="#" prefix="">
              Travel Planner
            </HeaderName>
          </Header>
        )}
      />

      <Content>
        <Grid
          condensed
          fullWidth
          style={{
            justifyContent: "center",
            alignItems: "center",
            minHeight: "100vh",
          }}
        >
          <Column lg={6} md={6} sm={4}>
            <div
              style={{
                marginTop: "2rem",
                marginBottom: "2rem",
                textAlign: "center",
              }}
            >
              <div
                style={{
                  width: "80px",
                  height: "80px",
                  background: "var(--cds-interactive)",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 2rem auto",
                }}
              >
                <Icon size={32} style={{ color: "white" }} />
              </div>

              <h1
                style={{
                  fontSize: "2.5rem",
                  fontWeight: "300",
                  marginBottom: "0.5rem",
                  color: "var(--cds-text-primary)",
                }}
              >
                {title}
              </h1>
              <p
                style={{
                  color: "var(--cds-text-secondary)",
                  fontSize: "1.125rem",
                  marginBottom: "2rem",
                }}
              >
                {isLogin
                  ? "Welcome back to your travel planning dashboard"
                  : "Join us and start planning your next adventure"}
              </p>
            </div>

            {notification && (
              <InlineNotification
                kind={notification.kind}
                title={notification.title}
                subtitle={notification.subtitle}
                style={{ marginBottom: "2rem" }}
                onCloseButtonClick={() => setNotification(null)}
              />
            )}

            <Tile style={{ padding: "2.5rem" }}>
              <Form onSubmit={handleSubmit}>
                <FormGroup legendText="">
                  <TextInput
                    id="username"
                    labelText="Username"
                    placeholder="Enter your username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    style={{ marginBottom: "1.5rem" }}
                  />

                  <TextInput
                    id="password"
                    type="password"
                    labelText="Password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    style={{ marginBottom: "2rem" }}
                  />

                  <Button
                    type="submit"
                    disabled={loading}
                    renderIcon={loading ? null : Icon}
                    style={{ width: "100%", marginBottom: "1.5rem" }}
                  >
                    {loading ? (
                      <>
                        <Loading small style={{ marginRight: "0.5rem" }} />
                        {isLogin ? "Signing In..." : "Creating Account..."}
                      </>
                    ) : (
                      buttonText
                    )}
                  </Button>

                  <div
                    style={{
                      textAlign: "center",
                      paddingTop: "1rem",
                      borderTop: "1px solid var(--cds-border-subtle)",
                    }}
                  >
                    {isLogin ? (
                      <p style={{ color: "var(--cds-text-secondary)" }}>
                        Don't have an account?{" "}
                        <Button
                          kind="ghost"
                          size="sm"
                          onClick={() => navigate("/register")}
                          style={{ padding: "0", minHeight: "auto" }}
                        >
                          Create one here
                        </Button>
                      </p>
                    ) : (
                      <p style={{ color: "var(--cds-text-secondary)" }}>
                        Already have an account?{" "}
                        <Button
                          kind="ghost"
                          size="sm"
                          onClick={() => navigate("/login")}
                          style={{ padding: "0", minHeight: "auto" }}
                        >
                          Sign in here
                        </Button>
                      </p>
                    )}
                  </div>
                </FormGroup>
              </Form>
            </Tile>
          </Column>
        </Grid>
      </Content>
    </div>
  );
}

export default FormComponent;
