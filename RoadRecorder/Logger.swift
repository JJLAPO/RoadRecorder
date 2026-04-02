import Foundation

final class Logger {
    static let shared = Logger()

    private let fileURL: URL
    private let queue = DispatchQueue(label: "com.roadrecorder.logger")
    private let formatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss.SSS"
        return f
    }()

    private init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        fileURL = docs.appendingPathComponent("roadrecorder.log")
    }

    func log(_ level: Level, _ message: String) {
        let line = "[\(formatter.string(from: Date()))] [\(level.rawValue)] \(message)\n"
        #if DEBUG
        print(line, terminator: "")
        #endif
        queue.async { [fileURL] in
            if let data = line.data(using: .utf8) {
                if FileManager.default.fileExists(atPath: fileURL.path) {
                    if let handle = try? FileHandle(forWritingTo: fileURL) {
                        handle.seekToEndOfFile()
                        handle.write(data)
                        handle.closeFile()
                    }
                } else {
                    try? data.write(to: fileURL)
                }
            }
        }
    }

    func clearLog() {
        queue.async { [fileURL] in
            try? FileManager.default.removeItem(at: fileURL)
        }
    }

    var logFileURL: URL { fileURL }

    enum Level: String {
        case info = "INFO"
        case warn = "WARN"
        case error = "ERROR"
    }
}
