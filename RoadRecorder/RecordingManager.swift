import Foundation
import CoreLocation
import Combine

final class RecordingManager: ObservableObject {
    let locationManager = LocationManager()
    let altimeterManager = AltimeterManager()
    private let log = Logger.shared

    @Published var points: [RecordingPoint] = []
    @Published var isRecording = false
    @Published var totalDistance: Double = 0.0
    @Published var gpsGapCount: Int = 0
    @Published var droppedPoints: Int = 0
    @Published var exportError: String?

    private var lastLocation: CLLocation?
    private var lastPointTime: Date?

    init() {
        locationManager.onLocationUpdate = { [weak self] location in
            self?.handleLocation(location)
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
        lastPointTime = nil
        exportError = nil
        isRecording = true

        altimeterManager.reset()
        altimeterManager.start()
        locationManager.startUpdating()
        log.log(.info, "Recording STARTED")
    }

    func stopRecording() {
        isRecording = false
        locationManager.stopUpdating()
        altimeterManager.stop()
        log.log(.info, "Recording STOPPED — \(points.count) points, \(String(format: "%.0f", totalDistance))m, \(gpsGapCount) gaps, \(droppedPoints) dropped")
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

    private func handleLocation(_ location: CLLocation) {
        guard isRecording else { return }

        // Drop points with very bad accuracy (> 20m)
        if location.horizontalAccuracy < 0 || location.horizontalAccuracy > 20 {
            droppedPoints += 1
            log.log(.warn, "Dropped point: h_accuracy=\(String(format: "%.1f", location.horizontalAccuracy))m")
            return
        }

        // Detect GPS gaps (> 3 seconds since last point)
        if let lastTime = lastPointTime {
            let gap = location.timestamp.timeIntervalSince(lastTime)
            if gap > 3.0 {
                gpsGapCount += 1
                log.log(.warn, "GPS gap detected: \(String(format: "%.1f", gap))s between points")
            }
        }

        // Detect position jumps (> 50m in 1-2 seconds = likely GPS spike)
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
            verticalAccuracy: location.verticalAccuracy
        )

        points.append(point)
    }
}
