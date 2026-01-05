# Authentication Guide

This guide details the authentication flows for the HomePot application, covering both the Client and Engineer (Admin) experiences.

## Overview

HomePot supports two distinct user roles with separate login/signup experiences:

1.  **Engineers (Admins)**: Have full access to system configuration, device management, and detailed analytics.
2.  **Clients (Users)**: Have restricted access focused on monitoring their specific devices and basic home management.

## User Registration (Sign Up)

The Sign Up page provides a tabbed interface to easily switch between creating an Engineer account or a Client account.

### Engineer Sign Up
- **Tab:** Select "ENGINEER"
- **Role Assigned:** `Admin` (and `is_admin=True`)
- **Required Fields:**
    - Full Name
    - Email
    - Password
- **Notes:** Engineers typically require 2FA (Two-Factor Authentication) which is noted on the screen but currently enforced via policy.

### Client Sign Up
- **Tab:** Select "CLIENT"
- **Role Assigned:** `User` (and `is_admin=False`)
- **Required Fields:**
    - Full Name
    - Email
    - Password
    - Role (Dropdown: e.g., Home Owner, Resident)

### Key Features
*   **Smart Role Selection:** The active tab automatically sets the underlying system role (`Admin` vs `User`).
*   **Full Name Support:** Users can now provide their full real name, which is stored in the database for personalized greetings and audit logs.
*   **Username Generation:** If a username is not explicitly provided (via API), the system automatically generates one from the email address to ensure seamless registration.

## User Login (Sign In)

The Login page mirrors the Sign Up experience with a tabbed interface.

1.  **Select Identity:** Choose "ENGINEER" or "CLIENT".
2.  **Enter Credentials:** Email and Password.
3.  **SSO (Coming Soon):** The "Sign in with SSO" button is a placeholder for future Enterprise Single Sign-On integration.

## Default Credentials (Development)

For development and testing purposes, the system is seeded with the following accounts:

| Role | Email | Password | Full Name |
|------|-------|----------|-----------|
| **Engineer (Admin)** | `admin@homepot.com` | `homepot_dev_password` | System Administrator |
| **Client (User)** | `user@homepot.com` | `homepot_dev_password` | Standard Client |

## Technical Implementation

### Database Schema
The `users` table includes:
- `email` (Unique Identifier)
- `username` (Unique, can be auto-generated)
- `full_name` (Display Name)
- `hashed_password` (Bcrypt hash)
- `role` (String: "Admin", "Client", etc.)
- `is_admin` (Boolean flag derived from role)

### Security
- **HTTPOnly Cookies:** Session tokens (JWT) are stored in secure, HTTPOnly cookies to prevent XSS attacks.
- **CSRF Protection:** SameSite cookie policies are enforced.
