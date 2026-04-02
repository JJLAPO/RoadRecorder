# RoadRecorder

iPhone app for recording GPS tracks and barometric altitude on mountain roads, designed to capture precise road geometry data for 3D reconstruction in Blender (driving simulator).

## What it records (1 Hz)

| Field | Sensor | Precision |
|-------|--------|-----------|
| Latitude / Longitude | GPS dual-freq L5 | 1-3 m (open sky) |
| GPS Altitude | GPS | 4-10 m |
| Barometric Altitude (relative) | Barometer | ±0.1-0.3 m |
| Pressure | Barometer | high |
| Speed, Course | GPS | good |
| Horizontal / Vertical Accuracy | GPS | for filtering |

## Features

- Real-time map with recorded track
- Live stats: points, distance, altitude, GPS accuracy, speed
- Combined GPS + barometric altimeter for precise elevation profile
- Background recording (screen off)
- CSV export via Share Sheet (AirDrop, Files, etc.)
- Minimal UI: Start / Stop / Save

## Requirements

- iPhone 12+ (dual-frequency GPS L5 recommended)
- iOS 17+
- Xcode 15+

## Setup

1. Open `RoadRecorder.xcodeproj` in Xcode
2. Set your Development Team in Signing & Capabilities
3. Connect your iPhone and hit Run
4. Accept location permissions when prompted

## Output format

CSV file with one row per second:

```
timestamp,lat,lon,alt_gps,alt_baro_rel,pressure,speed,course,h_accuracy,v_accuracy
```

## Pipeline

```
iPhone (this app) → CSV → Python cleanup → Satellite comparison → Blender import → Driving simulator
```

## License

MIT
test
