# Dashboard Static Files

## Purpose

Client-side UI for the sentiment analysis dashboard.

## Files

| File | Purpose |
|------|---------|
| index.html | Main dashboard page |
| styles.css | Styling with sentiment colors |
| app.js | Chart.js visualizations + SSE |
| config.js | API URL configuration |

## For On-Call Engineers

If users report dashboard issues:

1. **Charts not loading** → Check browser console for API errors
2. **Data not updating** → Check `/api/v2/sentiment` endpoint in Network tab
3. **CORS errors** → Verify Function URL CORS configuration

### Browser Console Commands

```javascript
// Check last API response
console.log(window.lastSentimentResponse);

// Force refresh
window.location.reload(true);

// Test API manually
fetch('/api/v2/sentiment?tags=AI', {headers: {'Authorization': 'Bearer YOUR_KEY'}})
  .then(r => r.json())
  .then(console.log);
```

## Charts

1. **Pie chart** - Sentiment distribution (positive/neutral/negative)
2. **Bar chart** - Articles by tag
3. **Metrics cards** - Total, positive, neutral, negative counts
4. **Recent items table** - Last 20 analyzed articles

## Colors

- Positive: `#4CAF50` (green)
- Neutral: `#FFC107` (amber)
- Negative: `#f44336` (red)

## Security

- API key stored in config.js (should be loaded from environment in production)
- No sensitive data cached in localStorage
- All API calls use HTTPS
