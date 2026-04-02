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

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    static let csvHeader = "timestamp,lat,lon,alt_gps,alt_baro_rel,pressure,speed,course,h_accuracy,v_accuracy"

    var csvLine: String {
        String(format: "%.3f,%.8f,%.8f,%.2f,%.3f,%.4f,%.2f,%.1f,%.1f,%.1f",
               timestamp, latitude, longitude, altitudeGPS,
               altitudeBaroRelative, pressure, speed, course,
               horizontalAccuracy, verticalAccuracy)
    }
}
