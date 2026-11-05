// App auxiliar "Jarvis Localização": pede a permissão de localização do macOS (o processo Python do Jarvis não
// consegue, por não ser um app com Info.plist) e grava {"lat","lon","acc"} ou {"erro"} no arquivo do 1º argumento.
// Compilado sob demanda em cache/JarvisLocal.app por jarvis/mac/location.py.

import AppKit
import CoreLocation
import Foundation

let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "/dev/stdout"
func finish(_ obj: [String: Any]) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: obj)
    FileManager.default.createFile(atPath: out, contents: data)
    exit(0)
}

final class Delegate: NSObject, CLLocationManagerDelegate {
    let manager = CLLocationManager()
    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }
    func start() {
        switch manager.authorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .denied, .restricted: finish(["erro": "negado"])
        default: manager.requestLocation()
        }
    }
    func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        switch m.authorizationStatus {
        case .notDetermined: break
        case .denied, .restricted: finish(["erro": "negado"])
        default: m.requestLocation()
        }
    }
    func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        guard let l = locs.last else { return }
        finish(["lat": l.coordinate.latitude, "lon": l.coordinate.longitude, "acc": l.horizontalAccuracy])
    }
    func locationManager(_ m: CLLocationManager, didFailWithError e: Error) {
        finish(["erro": e.localizedDescription])
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let d = Delegate()
app.activate(ignoringOtherApps: true)
d.start()
DispatchQueue.main.asyncAfter(deadline: .now() + 600) { finish(["erro": "tempo esgotado", "status": d.manager.authorizationStatus.rawValue]) }
app.run()
