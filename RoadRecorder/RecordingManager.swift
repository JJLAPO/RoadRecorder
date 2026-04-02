import Foundation
import CoreLocation
import Combine

final class RecordingManager: ObservableObject {
    let locationManager = LocationManager()
    let altimeterManager = AltimeterManager()
    private let log = Logger.shared

    @Published var points: [RecordingPoint] = []
    @Published var isRecording = false
    @Published var isWarmingUp = false
    @Published var totalDistance: Double = 0.0
    @Published var gpsGapCount: Int = 0
    @Published var droppedPoints: Int = 0
    @Published var exportError: String?

    private var lastLocation: CLLocation?
    private var secondLastLocation: CLLocation?
    private var lastPointTime: Date?
    private var interpolationTimer: Timer?

    static let warmupAccuracy: Double = 5.0

    init() {
        locationManager.onLocationUpdate = { [weak self] locations in
            for location in locations {
                self?.handleLocation(location)
            }
        }
    }

    func requestPermission() {
        locationManager.requestPermission()
    }

    func startRecording() {
        points.removeAll()
        totalDistance = 0.0
        gpsGapCount = 0
        droppedPoints = 0
        lastLocation = nil
        secondLastLocation = nil
        lastPointTime = nil
        exportError = nil
        isWarmingUp = true
        isRecording = true

        altimeterManager.reset()
        altimeterManager.start()
        locationManager.startUpdating()
        log.log(.info, "Recording STARTED (warming up, waiting for accuracy < \(Self.warmupAccuracy)m)")
    }

    func stopRecording() {
        isRecording = false
        isWarmingUp = false
        stopInterpolationTimer()
        locationManager.stopUpdating()
        altimeterManager.stop()
        let interpCount = points.filter { $0.interpolated }.count
        log.log(.info, "Recording STOPPED — \(points.count) points (\(interpCount) interpolated), \(String(format: "%.0f", totalDistance))m, \(gpsGapCount) gaps, \(droppedPoints) dropped")
    }

    func exportCSV() -> URL? {
        guard !points.isEmpty else {
            exportError = "Nessun punto da esportare"
            return nil
        }

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd_HH-mm-ss"
        let filename = "road_\(formatter.string(from: Date())).csv"

        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let fileURL = docs.appendingPathComponent(filename)

        var csv = RecordingPoint.csvHeader + "\n"
        for point in points {
            csv += point.csvLine + "\n"
        }

        do {
            try csv.write(to: fileURL, atomically: true, encoding: .utf8)
            let sizeMB = Double(csv.utf8.count) / 1_048_576.0
            log.log(.info, "CSV exported: \(filename) (\(points.count) points, \(String(format: "%.2f", sizeMB)) MB)")
            exportError = nil
            return fileURL
        } catch {
            exportError = "Export fallito: \(error.localizedDescription)"
            log.log(.error, "CSV export failed: \(error.localizedDescription)")
            return nil
        }
    }

    func exportLog() -> URL {
        return Logger.shared.logFileURL
    }

    // MARK: - Interpolation timer

    private func startInterpolationTimer() {
        stopInterpolationTimer()
        interpolationTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            self?.generateInterpolatedPoint()
        }
    }

    private func stopInterpolationTimer() {
        interpolationTimer?.invalidate()
        interpolationTimer = nil
    }

    private func generateInterpolatedPoint() {
        guard isRecording, !isWarmingUp else { return }
        guard let loc1 = secondLastLocation, let loc2 = lastLocation else { return }

        let dt = loc2.timestamp.timeIntervalSince(loc1.timestamp)
        guard dt > 0.3 && dt < 3.0 else { return }

        let now = Date()
        let timeSinceLast = now.timeIntervalSince(loc2.timestamp)

        // Only interpolate between 0.3s and 0.9s after last GPS fix
        guard timeSinceLast > 0.3 && timeSinceLast < 0.9 else { return }

        // Linear interpolation of position based on last two GPS fixes
        let fraction = timeSinceLast / dt
        let lat = loc2.coordinate.latitude + (loc2.coordinate.latitude - loc1.coordinate.latitude) * fraction
        let lon = loc2.coordinate.longitude + (loc2.coordinate.longitude - loc1.coordinate.longitude) * fraction
        let altGPS = loc2.altitude + (loc2.altitude - loc1.altitude) * fraction
        let speed = max(loc2.speed, 0)
        let course = loc2.course

        let point = RecordingPoint(
            timestamp: now.timeIntervalSince1970,
            latitude: lat,
            longitude: lon,
            altitudeGPS: altGPS,
            altitudeBaroRelative: altimeterManager.relativeAltitude,
            pressure: altimeterManager.pressure,
            speed: speed,
            course: course,
            horizontalAccuracy: max(loc2.horizontalAccuracy, loc1.horizontalAccuracy),
            verticalAccuracy: max(loc2.verticalAccuracy, loc1.verticalAccuracy),
            interpolated: true
        )

        points.append(point)
    }

    // MARK: - Handle GPS updates

    private func handleLocation(_ location: CLLocation) {
        guard isRecording else { return }

        // Drop points with very bad accuracy (> 20m)
        if location.horizontalAccuracy < 0 || location.horizontalAccuracy > 20 {
            droppedPoints += 1
            log.log(.warn, "Dropped point: h_accuracy=\(String(format: "%.1f", location.horizontalAccuracy))m")
            return
        }

        // Warmup: wait for good accuracy before recording
        if isWarmingUp {
            if location.horizontalAccuracy <= Self.warmupAccuracy {
                isWarmingUp = false
                startInterpolationTimer()
                log.log(.info, "Warmup complete: h_accuracy=\(String(format: "%.1f", location.horizontalAccuracy))m — recording started")
            } else {
                log.log(.info, "Warming up: h_accuracy=\(String(format: "%.1f", location.horizontalAccuracy))m (need < \(Self.warmupAccuracy)m)")
                return
            }
        }

        // Detect GPS gaps (> 3 seconds since last point)
        if let lastTime = lastPointTime {
            let gap = location.timestamp.timeIntervalSince(lastTime)
            if gap > 3.0 {
                gpsGapCount += 1
                log.log(.warn, "GPS gap detected: \(String(format: "%.1f", gap))s between points")
            }
        }

        // Detect position jumps (> 50m/s = likely GPS spike)
        if let last = lastLocation {
            let dist = location.distance(from: last)
            let dt = location.timestamp.timeIntervalSince(last.timestamp)
            if dt > 0 && dt < 3 && dist / dt > 50 {
                droppedPoints += 1
                log.log(.warn, "Dropped spike: \(String(format: "%.0f", dist))m in \(String(format: "%.1f", dt))s (\(String(format: "%.0f", dist/dt)) m/s)")
                return
            }
            totalDistance += dist
        }

        secondLastLocation = lastLocation
        lastLocation = location
        lastPointTime = location.timestamp

        let point = RecordingPoint(
            timestamp: location.timestamp.timeIntervalSince1970,
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            altitudeGPS: location.altitude,
            altitudeBaroRelative: altimeterManager.relativeAltitude,
            pressure: altimeterManager.pressure,
            speed: max(location.speed, 0),
            course: location.course,
            horizontalAccuracy: location.horizontalAccuracy,
            verticalAccuracy: location.verticalAccuracy,
            interpolated: false
        )

        points.append(point)
    }
}
