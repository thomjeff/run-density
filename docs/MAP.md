# Interactive Density Map

The run-density application now includes an interactive map that visualizes segment density zones in real-time.

## Features

- **Interactive Map**: Built with Leaflet.js and OpenStreetMap
- **Real-time Data**: Fetches density data from your existing `/api/density.summary` endpoint
- **Zone Visualization**: Colors segments by density zones (green → yellow → orange → red → dark-red)
- **Metric Toggle**: Switch between areal and crowd density metrics
- **Hover Information**: See detailed segment information on hover
- **Responsive Design**: Works on desktop and mobile devices

## Accessing the Map

### Production
```
https://your-app-url/map
```

### Local Development
```
http://localhost:8081/map
```

## API Endpoints

### `/map` and `/api/map`
- **Method**: GET
- **Response**: HTML page with interactive map
- **Purpose**: Main map interface

### `/api/segments.geojson`
- **Method**: GET  
- **Response**: GeoJSON FeatureCollection of all segments
- **Purpose**: Provides segment geometries for the map
- **Status**: Currently returns placeholder data

## How It Works

1. **Map Initialization**: Loads with OpenStreetMap tiles
2. **Data Fetching**: Simultaneously fetches segments and density data
3. **Rendering**: Colors segments based on density zones from your API
4. **Interactivity**: Users can toggle metrics and see real-time updates

## Current Status

### ✅ Implemented
- Interactive map interface
- Real-time density data fetching
- Zone-based coloring
- Metric switching (areal/crowd)
- Responsive design
- Error handling with fallbacks

### 🔄 Placeholder Data
- Segment geometries (currently using demo coordinates)
- Will be replaced with real course data when available

### 🚀 Future Enhancements
- Real segment geometries from GPX/course data
- Custom zone threshold controls
- Export functionality
- Historical data visualization

## Technical Details

### Dependencies
- **Frontend**: Leaflet.js 1.9.4, vanilla JavaScript
- **Backend**: FastAPI with Jinja2 templating
- **Styling**: CSS3 with responsive design

### Browser Support
- Modern browsers with ES6+ support
- Mobile-friendly with touch interactions

## Customization

### Adding Real Segment Data
Replace the placeholder data in `/api/segments.geojson` with real coordinates:

```json
{
  "type": "Feature",
  "properties": {
    "seg_id": "A1a",
    "segment_label": "Start to Queen/Regent"
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [longitude1, latitude1],
      [longitude2, latitude2]
    ]
  }
}
```

### Styling
Modify the CSS in `app/templates/map.html` to customize:
- Colors and fonts
- Panel positioning
- Map controls
- Legend appearance

## Testing

### Local Testing
```bash
# Start the application
make run-local

# Open in browser
open http://localhost:8081/map
```

### Production Testing
```bash
# Test the map endpoint
curl -s "https://your-app-url/map" | head -20
```

## Troubleshooting

### Common Issues
1. **Map not loading**: Check browser console for JavaScript errors
2. **No segments visible**: Verify `/api/segments.geojson` returns valid GeoJSON
3. **Density data missing**: Check `/api/density.summary` endpoint
4. **Styling issues**: Ensure CSS is loading properly

### Debug Mode
Open browser developer tools to see:
- Network requests
- JavaScript console logs
- Map rendering status

## Integration with Existing Workflow

The map integrates seamlessly with your existing density analysis:
1. Run density calculations as usual
2. View results in the interactive map
3. Toggle between areal and crowd metrics
4. Export data using existing CSV endpoints

This provides a visual complement to your numerical density analysis, making it easier for race organizers and volunteers to understand congestion patterns.

