# Frontend

This folder contains the Angular application for DataPulse.

## Prerequisites

- Node.js installed
- The backend server running on `http://localhost:3001`

## Install

From this folder, install dependencies:

```powershell
npm install
```

## Run

Start the frontend development server:

```powershell
npm start
```

If the default port is busy, Angular will prompt for another port.

Open the app in your browser using the local URL shown in the terminal.

## Build

Create a production build:

```powershell
npm run build
```

## Notes

- The chat screen sends requests to the backend API at `http://localhost:3001/api/diagnose`.
- Start the backend before testing the chat flow.
