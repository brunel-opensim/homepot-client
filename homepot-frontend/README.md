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
cd homepot-client
git checkout frontend-develop
npm install
```

## Available Scripts

In the project directory, you can run:

- **`npm run dev`**
  Runs the app in development mode using Vite. Open [http://localhost:8080](http://localhost:8080) to view it in the browser.

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

1. Run the development server:

```bash
npm run dev
```

2. Open [http://localhost:8080](http://localhost:8080) in your browser.
3. Start editing the source code in the `src/` folder. Changes will hot-reload automatically.

## Contributing

1. Fork the repository.
2. Create a new branch: `git checkout -b feature/YourFeature`
3. Commit your changes: `git commit -m "Add YourFeature"`
4. Push to the branch: `git push origin feature/YourFeature`
5. Open a Pull Request.
