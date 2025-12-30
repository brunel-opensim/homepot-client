# Accessing the Dashboard

This guide explains how to start the HOMEPOT application and log in to the dashboard.

## Starting the Application

To run the complete HOMEPOT system (Backend + Frontend), use the provided startup script. This script checks for prerequisites, sets up the environment, and launches both services.

1.  Open your terminal in the project root directory.
2.  Run the following command:

    ```bash
    ./scripts/start-complete-website.sh
    ```

    > **Note**: This script requires **Node.js 22+**. If you have an older version, the script will attempt to use `nvm` to switch to version 22 automatically.

3.  Wait for the services to start. You should see output indicating that the Backend is running on port `8000` and the Frontend on port `5173`.

## Logging In

Once the application is running, open your web browser and navigate to:

**[http://localhost:5173](http://localhost:5173)**

You will be presented with the login screen.

### Default Credentials

For development and testing, the database is seeded with a default administrator account:

*   **Email**: `admin@homepot.com`
*   **Password**: `homepot_dev_password`
*   **Role**: Admin

Enter these credentials and click **Sign In**.

### Creating a New Account

If you prefer to create a new user:

1.  Click the **Sign Up** link on the login page.
2.  Fill in your **Name**, **Email**, **Password**, and select a **Role**.
3.  Click **Sign Up**.

### Manually Adding a User (Database)

If you encounter issues with the registration form or need to create a specific user role directly in the database, you can use the `add-user.sh` script.

1.  Open your terminal in the project root directory.
2.  Run the script with the desired username, email, password, and admin status (true/false):

    ```bash
    ./scripts/add-user.sh <username> <email> <password> [is_admin]
    ```

    **Example:**
    ```bash
    ./scripts/add-user.sh john_doe john@example.com secret123 false
    ```

    This will create a new user in the database that you can immediately use to log in.

## Troubleshooting

### Node.js Version Error
If you see an error regarding the Node.js version (e.g., "Vite requires Node.js version 20.19+"), you need to update your Node.js installation.

If you have `nvm` installed, you can run:
```bash
nvm install 22
nvm use 22
```
Then try running the start script again.

### Port Already in Use
If port `8000` or `5173` is already in use, the start script will ask if you want to kill the existing process. Type `y` and press Enter to proceed.
