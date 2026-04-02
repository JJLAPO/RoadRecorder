import Foundation
import CoreMotion
import Combine

final class AltimeterManager: ObservableObject {
    private let altimeter = CMAltimeter()

    @Published var relativeAltitude: Double = 0.0
    @Published var pressure: Double = 0.0
    @Published var isAvailable: Bool = false

    init() {
        isAvailable = CMAltimeter.isRelativeAltitudeAvailable()
    }

    func start() {
        guard isAvailable else { return }
        altimeter.startRelativeAltitudeUpdates(to: .main) { [weak self] data, error in
            guard let self, let data, error == nil else { return }
            self.relativeAltitude = data.relativeAltitude.doubleValue
            self.pressure = data.pressure.doubleValue // kPa
        }
    }

    func stop() {
        altimeter.stopRelativeAltitudeUpdates()
    }

    func reset() {
        relativeAltitude = 0.0
        pressure = 0.0
    }
}
