import AppKit

guard CommandLine.arguments.count == 3, let pid = Int32(CommandLine.arguments[2]) else { exit(2) }
switch CommandLine.arguments[1] {
case "visible":
    let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
        as? [[String: Any]] ?? []
    let visible = windows.contains { window in
        guard window[kCGWindowOwnerPID as String] as? Int32 == pid,
              window[kCGWindowLayer as String] as? Int == 0,
              let bounds = window[kCGWindowBounds as String] as? [String: CGFloat],
              let width = bounds["Width"], let height = bounds["Height"]
        else { return false }
        return width > 100 && height > 100
    }
    exit(visible ? 0 : 1)
case "quit":
    exit(NSRunningApplication(processIdentifier: pid)?.terminate() == true ? 0 : 1)
default:
    exit(2)
}
