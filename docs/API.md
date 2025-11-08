# 🔌 WanderGenie API - Quick Reference

**Base URL:** `http://localhost:8000`

---

## 1. Create Trip

```
POST /api/trip
```

**Request:**
```json
{
  "prompt": "5 days in NYC from Buffalo, love pizza and views"
}
```

**Response:**
```json
{
  "trip_id": "trip_12345",
  "status": "processing"
}
```

---

## 2. Get Trip

```
GET /api/trip/{trip_id}
```

**Response:** See [`sample_trip_response.json`](./sample_trip_response.json)

**Key fields:**
- `days[]` - Array of days
- `days[].activities[]` - Activities with `time`, `name`, `lat`, `lon`, `booking_url`
- `booking_links.flights` - Google Flights link
- `booking_links.hotels` - Booking.com link

---

## 3. Edit Trip (Optional)

```
PATCH /api/trip/{trip_id}
```

**Request:**
```json
{
  "instruction": "Swap Day 2 afternoon for MoMA"
}
```

---

## Frontend Integration

### Render Timeline
```javascript
trip.days.forEach(day => {
  day.activities.forEach(activity => {
    console.log(`${activity.time}: ${activity.name}`);
  });
});
```

### Render Map
```javascript
trip.days.forEach(day => {
  day.activities.forEach(activity => {
    addMarker(activity.lat, activity.lon, activity.name);
  });
});
```

### Show Booking Badge
```javascript
if (activity.booking_required) {
  // Show 🎟️ badge and link to activity.booking_url
}
```

---

**Full Sample Response:** [`sample_trip_response.json`](./sample_trip_response.json)
