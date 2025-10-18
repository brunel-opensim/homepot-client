# Homepot

Homepot is a modern React application built with **Vite** and **Tailwind CSS**, featuring charts, routing, and reusable UI components.

## Table of Contents

- [Installation](#installation)
- [Available Scripts](#available-scripts)
- [Dependencies](#dependencies)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client/frontend
npm install
```

**Environment Setup:**

Copy the environment example file and configure your backend API URL:

```bash
cp .env.example .env.local
```

Edit `.env.local` to set your backend API URL (default: `http://localhost:8000`)

## Available Scripts

In the project directory, you can run:

- **`npm run dev`**
  Runs the app in development mode using Vite. Open [http://localhost:5173](http://localhost:5173) to view it in the browser.
  
  > **Note:** Vite's default port is 5173. To change to port 8080, update `vite.config.js` with:
  > ```javascript
  > server: { port: 8080 }
  > ```

- **`npm run build`**
  Builds the app for production into the `dist` folder.

- **`npm run preview`**
  Serves the production build locally for preview.

- **`npm run lint`**
  Runs ESLint to check code for linting errors.

## Dependencies

- **React** & **React DOM** – Core library for building UI.
- **React Router DOM** – Declarative routing for React.
- **Chart.js** & **react-chartjs-2** – Charting library for data visualization.
- **Tailwind CSS** – Utility-first CSS framework.
- **Tailwind Variants** & **Tailwind Merge** – Tailwind helpers for managing class names.
- **Lucide React** – Icon library.
- **Class Variance Authority** & **clsx** – Utilities for conditional class names.
- **Radix UI Slot** – Component composition helper.
- **tailwindcss-animate** – Animation utilities for Tailwind.

## Development

1. Ensure you have the backend running (see `../backend/README.md`)

2. Run the frontend development server:

```bash
npm run dev
```

3. Open [http://localhost:5173](http://localhost:5173) in your browser.
4. Start editing the source code in the `src/` folder. Changes will hot-reload automatically.

**Current Status:**
- ✅ All UI pages implemented and working
- ⚠️ **Backend API integration pending** - Currently using mock/static data
- See `FRONTEND_REVIEW.md` in the root directory for detailed status

## Pages

The application includes the following pages:

- **Home** (`/`) - Landing page
- **Login** (`/login`) - Authentication (UI only, backend integration pending)
- **Dashboard** (`/dashboard`) - Main monitoring interface with charts
- **Device** (`/device`) - Device management and monitoring
- **Site** (`/site`) - Site listing and search
- **SiteDevice** (`/site/:deviceId`) - Individual site device details

## Contributing

1. Fork the repository.
2. Create a new branch: `git checkout -b feature/YourFeature`
3. Commit your changes: `git commit -m "Add YourFeature"`
4. Push to the branch: `git push origin feature/YourFeature`
5. Open a Pull Request.
