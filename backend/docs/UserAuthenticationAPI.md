# User Authentication API Documentation

## Base URL
```
http://localhost:8000
```

## API Version
```
/api/v1/auth
```

---

## Endpoints

### 1. User Signup (Registration)

**Description:** Register a new user account in the HomePot system.

#### Endpoint
```
POST /api/v1/auth/signup
```

#### Request Headers
```
Content-Type: application/json
```

#### Request Body
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "username": "user"
}
```

**Fields:**
- `email` (required, EmailStr): User's email address
- `password` (required, string): User's password (will be hashed)
- `username` (optional, string): User's username

#### Success Response (201 Created)
```json
{
  "success": true,
  "message": "User registered successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### Error Responses

**Email Already Registered (400)**
```json
{
  "status_code": 400,
  "detail": "Email already registered"
}
```

**Username Already Taken (400)**
```json
{
  "status_code": 400,
  "detail": "Username already taken"
}
```

**Internal Server Error (500)**
```json
{
  "detail": "Internal Server Error"
}
```

#### cURL Example
```bash
curl -X POST http://localhost:8001/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123",
    "username": "john_doe"
  }'
```

---

### 2. User Login

**Description:** Authenticate an existing user and receive an access token.

#### Endpoint
```
POST /api/v1/auth/login
```

#### Request Headers
```
Content-Type: application/json
```

#### Request Body
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Fields:**
- `email` (required, EmailStr): User's email address
- `password` (required, string): User's password

#### Success Response (200 OK)
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "username": "john_doe",
    "is_admin": false
  }
}
```

**Response Fields:**
- `success` (boolean): Operation success status
- `message` (string): Status message
- `data.access_token` (string): JWT access token for authenticated requests
- `data.username` (string): User's username
- `data.is_admin` (boolean): Whether user has admin privileges

#### Error Responses

**Invalid Email (401 Unauthorized)**
```json
{
  "detail": "Invalid email"
}
```

**Invalid Credentials (401 Unauthorized)**
```json
{
  "detail": "Invalid credentials"
}
```

**Internal Server Error (500)**
```json
{
  "detail": "Internal Server Error"
}
```

#### cURL Example
```bash
curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123"
  }'
```

---

### 3. Assign User Role (Admin Only)

**Description:** Assign a role to a user. **Currently disabled** - the role/permission system is not implemented in the current schema.

#### Endpoint
```
PUT /api/v1/auth/users/{user_id}/role
```

#### Request Headers
```
Content-Type: application/json
Authorization: Bearer <admin_access_token>
```

#### Path Parameters
- `user_id` (integer): The ID of the user to update

#### Query Parameters
- `new_role` (string): The new role to assign

#### Status: Not Implemented (501)

**Response:**
```json
{
  "detail": "Role assignment not implemented in current schema. Use is_admin field instead."
}
```

**Note:** This endpoint is currently disabled. To manage user permissions, use the `is_admin` field in the User model instead of role-based permissions.

#### cURL Example
```bash
curl -X PUT "http://localhost:8001/api/v1/auth/users/123/role?new_role=Admin" \
  -H "Authorization: Bearer <admin_access_token>" \
  -H "Content-Type: application/json"
```

---

### 4. Delete User

**Description:** Delete a user account by email address.

#### Endpoint
```
DELETE /api/v1/auth/users/{email}
```

#### Request Headers
```
Content-Type: application/json
```

#### Path Parameters
- `email` (string): The email address of the user to delete

#### Success Response (200 OK)
```json
{
  "success": true,
  "message": "User deleted successfully.",
  "data": {
    "email": "user@example.com"
  }
}
```

#### Error Responses

**User Not Found (401 Unauthorized)**
```json
{
  "detail": "Invalid email"
}
```

**Internal Server Error (500)**
```json
{
  "detail": "Internal Server Error"
}
```

#### cURL Example
```bash
curl -X DELETE http://localhost:8001/api/v1/auth/users/user@example.com \
  -H "Content-Type: application/json"
```

---

## Authentication

### JWT Token Usage

After successful login or signup, you'll receive an `access_token` in the response. Use this token in subsequent requests to protected endpoints:

#### Header Format
```
Authorization: Bearer <access_token>
```

#### Example
```bash
curl -X GET http://localhost:8001/api/v1/protected-endpoint \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Data Models

### UserCreate (Signup Request)
```typescript
{
  email: string (EmailStr, required)
  password: string (required)
  username?: string (optional)
}
```

### UserLogin (Login Request)
```typescript
{
  email: string (EmailStr, required)
  password: string (required)
}
```

### Standard Response Format
```typescript
{
  success: boolean
  message: string
  data: object
}
```

---

## Security Notes

1. **Password Hashing**: All passwords are hashed using bcrypt before storage
2. **JWT Tokens**: Access tokens expire after 30 minutes (configurable)
3. **HTTPS**: In production, always use HTTPS to protect credentials
4. **Token Storage**: Store access tokens securely (e.g., httpOnly cookies or secure storage)

---


---

## Testing with Postman

1. **Create a new request**
2. **Set the method** (POST, DELETE, etc.)
3. **Enter the URL**: `http://localhost:8001/api/v1/auth/signup`
4. **Add Headers**:
   - `Content-Type`: `application/json`
5. **Add Body** (raw JSON):
   ```json
   {
     "email": "test@example.com",
     "password": "testPassword123",
     "username": "testuser"
   }
   ```
6. **Send the request**

---

## Full API Workflow Example

### 1. Register a New User
```bash
curl -X POST http://localhost:8001/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "myPassword123",
    "username": "newuser"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "User registered successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 2. Login with Existing User
```bash
curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "myPassword123"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "username": "newuser",
    "is_admin": false
  }
}
```

### 3. Use Token for Protected Requests
```bash
curl -X GET http://localhost:8001/api/v1/protected-resource \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Environment Configuration

The API uses configuration from `homepot.config`:

```python
# Default Database
database_url = "postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db"

# JWT Settings
secret_key = "homepot-dev-secret-change-in-production"
algorithm = "HS256"
access_token_expire_minutes = 30
```

**Important**: Change the `secret_key` in production!

---

## Troubleshooting

### Issue: Connection Refused
**Solution**: Ensure the backend server is running on port 8001
```bash
python -m uvicorn homepot.app.main:app --host 0.0.0.0 --port 8001
```

### Issue: 401 Unauthorized
**Solution**: Check that:
- Email and password are correct
- Access token is valid and not expired
- Token is properly formatted in Authorization header

### Issue: 500 Internal Server Error
**Solution**: Check server logs for detailed error information
```bash
tail -f logs/homepot.log
```

---

## Additional Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **JWT Tokens**: https://jwt.io/
- **Password Hashing**: https://passlib.readthedocs.io/

---


