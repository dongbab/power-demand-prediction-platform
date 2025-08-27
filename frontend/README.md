# Svelte Frontend for Charging Station Peak Predictor

This is the refactored Svelte frontend for the charging station peak prediction system.

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Development mode:**
   ```bash
   npm run dev
   ```
   This will start the development server at `http://localhost:5173`

3. **Build for production:**
   ```bash
   npm run build
   ```
   This will build the app to the `../static` directory

4. **Preview production build:**
   ```bash
   npm run preview
   ```

## Backend Integration

- The backend should be running at `http://localhost:8000`
- In development, the Vite proxy forwards API calls to the backend
- In production, the built app is served by FastAPI from the `/static` directory

## Components

- **StationSelector**: Main page showing all charging stations
- **Dashboard**: Station-specific dashboard with metrics and charts
- **MetricCard**: Animated metric display components
- **Charts**: Interactive Chart.js components for hourly patterns, distribution, etc.

## Features

- Reactive state management with Svelte stores
- Chart.js integration for data visualization
- Real-time data updates
- Keyboard shortcuts (Ctrl+R to refresh, etc.)
- Responsive design
- Loading states and error handling
- Notification system

## API Integration

The frontend consumes the following backend endpoints:
- `GET /api/stations` - List all stations
- `GET /predict/{station_id}` - Get predictions
- `GET /api/station-analysis/{station_id}` - Get detailed analysis
- `GET /api/monthly-contract/{station_id}` - Get contract recommendations

## Development Notes

- The frontend is a SPA (Single Page Application)
- Routes are handled client-side using SvelteKit routing
- All API calls go through the centralized API service
- State is managed using Svelte stores for reactivity