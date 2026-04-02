import Foundation
import CoreLocation

struct RecordingPoint: Identifiable {
    let id = UUID()
    let timestamp: TimeInterval
    let latitude: Double
    let longitude: Double
    let altitudeGPS: Double
    let altitudeBaroRelative: Double
    let pressure: Double
    let speed: Double
    let course: Double
    let horizontalAccuracy: Double
    let verticalAccuracy: Double
    let interpolated: Bool

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    static let csvHeader = "timestamp,lat,lon,alt_gps,alt_baro_rel,pressure,speed,course,h_accuracy,v_accuracy,interpolated"

    var csvLine: String {
        String(format: "%.3f,%.8f,%.8f,%.2f,%.3f,%.4f,%.2f,%.1f,%.1f,%.1f,%d",
               timestamp, latitude, longitude, altitudeGPS,
               altitudeBaroRelative, pressure, speed, course,
               horizontalAccuracy, verticalAccuracy,
               interpolated ? 1 : 0)
    }
}
