import Foundation

public func downloadFile(url: URL) async throws -> Data {
    // Swift async function with braces
    let (data, _) = try await URLSession.shared.data(from: url)
    return data
}

struct UserProfile {
    let username: String
    let id: UUID
    
    func display() {
        print("User: \(username) (\(id))")
    }
}

class NetworkMonitor {
    var isRunning = false
    
    func startMonitoring() {
        isRunning = true
    }
}
