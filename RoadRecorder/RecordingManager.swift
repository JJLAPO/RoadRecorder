import Foundation
import CoreLocation
import Combine

final class RecordingManager: ObservableObject {
    let locationManager = LocationManager()
    let altimeterManager = AltimeterManager()

    @Published var points: [RecordingPoint] = []
    @Published var isRecording = false
    @Published var totalDistance: Double = 0.0

    private var lastLocation: CLLocation?

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
        lastLocation = nil
        isRecording = true

        altimeterManager.reset()
        altimeterManager.start()
        locationManager.startUpdating()
    }

    func stopRecording() {
        isRecording = false
        locationManager.stopUpdating()
        altimeterManager.stop()
    }

    func exportCSV() -> URL? {
        guard !points.isEmpty else { return nil }

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd_HH-mm-ss"
        let filename = "road_\(formatter.string(from: Date())).csv"

        let tempDir = FileManager.default.temporaryDirectory
        let fileURL = tempDir.appendingPathComponent(filename)

        var csv = RecordingPoint.csvHeader + "\n"
        for point in points {
            csv += point.csvLine + "\n"
        }

        do {
            try csv.write(to: fileURL, atomically: true, encoding: .utf8)
            return fileURL
        } catch {
            print("CSV export error: \(error)")
            return nil
        }
    }

    private func handleLocation(_ location: CLLocation) {
        guard isRecording else { return }

        if let last = lastLocation {
            totalDistance += location.distance(from: last)
        }
        lastLocation = location

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
