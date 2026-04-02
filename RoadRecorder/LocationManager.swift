import Foundation
import CoreLocation
import Combine

final class LocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let log = Logger.shared

    @Published var currentLocation: CLLocation?
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined
    @Published var lastError: String?
    @Published var signalLost = false

    private var signalTimer: Timer?

    var onLocationUpdate: (([CLLocation]) -> Void)?

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.distanceFilter = kCLDistanceFilterNone
        manager.activityType = .automotiveNavigation
        manager.allowsBackgroundLocationUpdates = true
        manager.pausesLocationUpdatesAutomatically = false
        manager.showsBackgroundLocationIndicator = true
        log.log(.info, "LocationManager initialized")
    }

    func requestPermission() {
        log.log(.info, "Requesting location permission")
        manager.requestAlwaysAuthorization()
    }

    func startUpdating() {
        guard authorizationStatus == .authorizedAlways || authorizationStatus == .authorizedWhenInUse else {
            log.log(.error, "Cannot start: location permission not granted (status: \(authorizationStatus.rawValue))")
            lastError = "Permesso posizione non concesso"
            return
        }
        lastError = nil
        signalLost = false
        manager.startUpdatingLocation()
        startSignalTimer()
        log.log(.info, "GPS started")
    }

    func stopUpdating() {
        manager.stopUpdatingLocation()
        stopSignalTimer()
        signalLost = false
        log.log(.info, "GPS stopped")
    }

    // MARK: - Signal loss detection

    private func startSignalTimer() {
        stopSignalTimer()
        signalTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            if let last = self.currentLocation,
               Date().timeIntervalSince(last.timestamp) > 5.0 {
                self.signalLost = true
                self.log.log(.warn, "GPS signal lost (no update for 5s)")
            }
        }
    }

    private func stopSignalTimer() {
        signalTimer?.invalidate()
        signalTimer = nil
    }

    // MARK: - CLLocationManagerDelegate

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard !locations.isEmpty else { return }

        if signalLost {
            log.log(.info, "GPS signal recovered")
        }
        if locations.count > 1 {
            log.log(.info, "GPS batch: \(locations.count) locations in one update")
        }
        signalLost = false
        lastError = nil
        currentLocation = locations.last
        onLocationUpdate?(locations)
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let old = authorizationStatus
        authorizationStatus = manager.authorizationStatus
        log.log(.info, "Location auth changed: \(old.rawValue) -> \(authorizationStatus.rawValue)")

        if authorizationStatus == .denied || authorizationStatus == .restricted {
            lastError = "Posizione negata. Attiva in Impostazioni > Privacy > Posizione"
            log.log(.error, "Location permission denied/restricted")
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let clError = error as? CLError
        let code = clError?.code ?? .locationUnknown

        switch code {
        case .denied:
            lastError = "Posizione negata. Attiva in Impostazioni"
            log.log(.error, "Location denied by user")
        case .network:
            lastError = "Errore rete GPS"
            log.log(.warn, "GPS network error: \(error.localizedDescription)")
        default:
            lastError = "Errore GPS: \(error.localizedDescription)"
            log.log(.error, "GPS error [\(code.rawValue)]: \(error.localizedDescription)")
        }
    }
}
