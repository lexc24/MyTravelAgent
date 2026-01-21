# Authentication Guide

> Complete guide to authenticating with the MyTravelAgent API using JWT tokens

## Quick Start

### 1. Register a New Account

**Endpoint:** `POST /api/user/register`

```json
{
  "username": "traveler123",
  "password": "SecurePass123!",
  "email": "traveler@example.com",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response:** User details with auto-created preferences object

**Rate Limit:** 5 registrations per hour per IP address

---

### 2. Login to Get Tokens

**Endpoint:** `POST /api/token`

```json
{
  "username": "traveler123",
  "password": "SecurePass123!"
}
```

**Response:**

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

You receive two tokens:

- **Access Token**: Used for API requests (expires in 30 minutes)
- **Refresh Token**: Used to get new access tokens (expires in 1 day)

---

### 3. Make Authenticated Requests

Include the access token in the `Authorization` header:

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

**Example Request:**

```bash
curl https://my-travel-agent.onrender.com/api/trips \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### 4. Refresh Your Access Token

When your access token expires (after 30 minutes), use the refresh token to get a new one.

**Endpoint:** `POST /api/token/refresh`

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response:**

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..." // New access token
}
```

---

## Token Lifecycle

| Token Type    | Lifespan   | Purpose                   | When to Use               |
| ------------- | ---------- | ------------------------- | ------------------------- |
| Access Token  | 30 minutes | Authenticate API requests | Every API call            |
| Refresh Token | 1 day      | Get new access tokens     | When access token expires |

---

## Authentication Flow Diagram

```
1. User Registers
   ↓
2. User Logs In → Receives Access + Refresh Tokens
   ↓
3. Make API Requests with Access Token
   ↓
4. Access Token Expires (after 30 min)
   ↓
5. Use Refresh Token → Get New Access Token
   ↓
6. Continue Making Requests
   ↓
7. Refresh Token Expires (after 1 day)
   ↓
8. User Must Log In Again
```

---

## Common Error Responses

### 401 Unauthorized - Invalid Token

```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid",
  "messages": [
    {
      "token_class": "AccessToken",
      "token_type": "access",
      "message": "Token is invalid or expired"
    }
  ]
}
```

**Solution:** Use your refresh token to get a new access token, or log in again.

---

### 401 Unauthorized - No Token Provided

```json
{
  "detail": "Authentication credentials were not provided."
}
```

**Solution:** Include `Authorization: Bearer <token>` header in your request.

---

### 401 Unauthorized - Invalid Credentials (Login)

```json
{
  "detail": "No active account found with the given credentials"
}
```

**Solution:** Check your username and password. Account might not exist or might be inactive.

---

## Testing in Swagger UI

1. Click the **"Authorize"** button (🔒 icon) at the top of the page
2. Get your access token by calling `POST /api/token`
3. Copy the `access` token from the response
4. Paste it into the "Value" field in the authorization popup
5. Click "Authorize"
6. All authenticated endpoints are now accessible!

**Note:** Don't include the word "Bearer" - Swagger adds it automatically.

---

## Security Best Practices

### ✅ DO:

- Store tokens securely (use httpOnly cookies or secure storage)
- Refresh tokens before they expire
- Implement token refresh logic in your client
- Use HTTPS in production (tokens sent over HTTP can be intercepted)
- Log out users by deleting stored tokens

### ❌ DON'T:

- Store tokens in localStorage (vulnerable to XSS)
- Share tokens between users
- Commit tokens to version control
- Use the same token across multiple applications
- Send tokens in URL parameters

---

## Integration Examples

### JavaScript/React

```javascript
// Login and store tokens
async function login(username, password) {
  const response = await fetch(
    "https://my-travel-agent.onrender.com/api/token",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }
  );

  const { access, refresh } = await response.json();

  // Security Note: In production, use httpOnly cookies or secure storage.
  // localStorage shown here for simplicity in demos/testing.
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

// Make authenticated requests
async function getTrips() {
  const token = localStorage.getItem("access_token");

  const response = await fetch(
    "https://my-travel-agent.onrender.com/api/trips",
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  return response.json();
}

// Refresh token
async function refreshToken() {
  const refresh = localStorage.getItem("refresh_token");

  const response = await fetch(
    "https://my-travel-agent.onrender.com/api/token/refresh",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    }
  );

  const { access } = await response.json();
  localStorage.setItem("access_token", access);
}
```

---

### Python

```python
import requests

# Login
response = requests.post(
    'https://my-travel-agent.onrender.com/api/token',
    json={
        'username': 'traveler123',
        'password': 'SecurePass123!'
    }
)
tokens = response.json()
access_token = tokens['access']
refresh_token = tokens['refresh']

# Make authenticated request
headers = {'Authorization': f'Bearer {access_token}'}
trips = requests.get(
    'https://my-travel-agent.onrender.com/api/trips',
    headers=headers
).json()

# Refresh token
refresh_response = requests.post(
    'https://my-travel-agent.onrender.com/api/token/refresh',
    json={'refresh': refresh_token}
)
new_access_token = refresh_response.json()['access']
```

---

### cURL

```bash
# Login
curl -X POST https://my-travel-agent.onrender.com/api/token \
  -H "Content-Type: application/json" \
  -d '{"username":"traveler123","password":"SecurePass123!"}'

# Make authenticated request (replace YOUR_TOKEN)
curl https://my-travel-agent.onrender.com/api/trips \
  -H "Authorization: Bearer YOUR_TOKEN"

# Refresh token
curl -X POST https://my-travel-agent.onrender.com/api/token/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh":"YOUR_REFRESH_TOKEN"}'
```

---

## FAQ

**Q: What happens if both my access and refresh tokens expire?**
A: You'll need to log in again with your username and password.

**Q: Can I have multiple access tokens at once?**
A: Yes, each login creates a new set of tokens. Old tokens remain valid until they expire.

**Q: How do I log out?**
A: Simply delete the stored tokens from your client. The tokens will still be valid until expiration, but the user won't have access to them.

**Q: What if my refresh token is stolen?**
A: Change your password immediately. This will invalidate all existing tokens.

**Q: Do tokens work across different devices?**
A: Yes, but you need to log in on each device separately to get device-specific tokens.

---

## Rate Limiting

Some endpoints have rate limits to prevent abuse:

| Endpoint          | Rate Limit    | Scope          |
| ----------------- | ------------- | -------------- |
| User Registration | 5 per hour    | Per IP address |
| Trip Creation     | 20 per hour   | Per user       |
| Trip Listing      | 100 per hour  | Per user       |
| Chat Messages     | 10 per minute | Per user       |

When you hit a rate limit, you'll receive a `429 Too Many Requests` response.

---

## Need Help?

- **GitHub Issues**: [Report authentication problems](https://github.com/yourusername/MyTravelAgent/issues)
- **API Status**: Check if the API is online at `/health`
- **Swagger UI**: Interactive testing at `/api/docs`
