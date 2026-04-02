import Foundation
import CoreMotion
import Combine

final class AltimeterManager: ObservableObject {
    private let altimeter = CMAltimeter()
    private let log = Logger.shared

    @Published var relativeAltitude: Double = 0.0
    @Published var pressure: Double = 0.0
    @Published var isAvailable: Bool = false
    @Published var lastError: String?
    @Published var updateCount: Int = 0

    init() {
        isAvailable = CMAltimeter.isRelativeAltitudeAvailable()
        if isAvailable {
            log.log(.info, "Barometric altimeter available")
        } else {
            log.log(.warn, "Barometric altimeter NOT available on this device")
        }
    }

    func start() {
        guard isAvailable else {
            lastError = "Altimetro barometrico non disponibile"
            log.log(.error, "Cannot start altimeter: not available")
            return
        }

        lastError = nil
        updateCount = 0
        log.log(.info, "Altimeter started")

        altimeter.startRelativeAltitudeUpdates(to: .main) { [weak self] data, error in
            guard let self else { return }

            if let error {
                self.lastError = "Errore barometro: \(error.localizedDescription)"
                self.log.log(.error, "Altimeter error: \(error.localizedDescription)")
                return
            }

            guard let data else {
                self.log.log(.warn, "Altimeter update with nil data")
                return
            }

            self.relativeAltitude = data.relativeAltitude.doubleValue
            self.pressure = data.pressure.doubleValue
            self.updateCount += 1
            self.lastError = nil
        }
    }

    func stop() {
        altimeter.stopRelativeAltitudeUpdates()
        log.log(.info, "Altimeter stopped (total updates: \(updateCount))")
    }

    func reset() {
        relativeAltitude = 0.0
        pressure = 0.0
        updateCount = 0
        lastError = nil
    }
}
