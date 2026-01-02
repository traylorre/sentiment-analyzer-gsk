# Data Model: Fix Manifest.json 404 Error

**Feature**: 1117-fix-manifest-404
**Date**: 2026-01-01

## Manifest Schema

The manifest.json file follows the W3C Web App Manifest specification.

### Manifest Structure

```json
{
  "name": "string (required) - Full application name",
  "short_name": "string (required) - Short name for home screen",
  "description": "string (optional) - Description of the application",
  "start_url": "string (required) - URL to open when app launches",
  "display": "string (required) - One of: standalone, fullscreen, minimal-ui, browser",
  "background_color": "string (required) - CSS color for app background during launch",
  "theme_color": "string (required) - CSS color for browser UI theming",
  "icons": [
    {
      "src": "string (required) - Path to icon file",
      "sizes": "string (required) - Icon dimensions (e.g., '192x192')",
      "type": "string (required) - MIME type (e.g., 'image/png')"
    }
  ]
}
```

### Concrete Values for Sentiment Analyzer

```json
{
  "name": "Sentiment Analyzer",
  "short_name": "Sentiment",
  "description": "Real-time sentiment analysis dashboard for market data",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#3b82f6",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

## Icon Specifications

| File | Dimensions | Format | Purpose |
|------|------------|--------|---------|
| icon-192.png | 192x192 px | PNG | Add to Home Screen, task switcher |
| icon-512.png | 512x512 px | PNG | Splash screen, PWA install prompt |

### Icon Design Requirements

- Solid background color (not transparent) for splash screen compatibility
- Simple, recognizable design visible at small sizes
- Square aspect ratio (1:1)
- PNG format with 8-bit color depth

## File Locations

| File | Path | Served At |
|------|------|-----------|
| manifest.json | `frontend/public/manifest.json` | `/manifest.json` |
| icon-192.png | `frontend/public/icons/icon-192.png` | `/icons/icon-192.png` |
| icon-512.png | `frontend/public/icons/icon-512.png` | `/icons/icon-512.png` |

## Validation Rules

1. **JSON Validity**: manifest.json must be valid JSON
2. **Required Fields**: name, short_name, start_url, display, background_color, theme_color, icons
3. **Icon Existence**: All icon paths must resolve to existing files
4. **Color Format**: Colors must be valid CSS color values (hex format preferred)
5. **Display Mode**: Must be one of the valid display modes
