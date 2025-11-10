import Foundation
import EventKit

// Minimal output structure
struct SimpleEvent: Codable {
    let title: String
    let location: String?
    let from: String
    let to: String
    let organizer: String?
}

@inline(__always)
func iso8601String(_ date: Date, _ fmt: ISO8601DateFormatter) -> String {
    fmt.string(from: date)
}

@inline(__always)
func getDayRange(_ cal: Calendar, for date: Date) -> (Date, Date) {
    let start = cal.startOfDay(for: date)
    return (start, cal.date(byAdding: .day, value: 1, to: start)!)
}

@inline(__always)
func parseArgDate(_ arg: String, tz: TimeZone) -> Date? {
    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd"
    df.timeZone = tz
    return df.date(from: arg)
}

@inline(__always)
func mapEvent(_ e: EKEvent, _ fmt: ISO8601DateFormatter) -> SimpleEvent {
    SimpleEvent(
        title: e.title ?? "(No Title)",
        location: e.location,
        from: iso8601String(e.startDate, fmt),
        to: iso8601String(e.endDate, fmt),
        organizer: e.organizer?.name
    )
}

func printJSON<T: Encodable>(_ v: T) {
    let enc = JSONEncoder()
    enc.outputFormatting = [.withoutEscapingSlashes]   // smaller output
    do {
        let data = try enc.encode(v)
        FileHandle.standardOutput.write(data)
    } catch {
        FileHandle.standardOutput.write(Data("{\"error\":\"JSON encoding failed\"}".utf8))
    }
}

// === MAIN ===
let tz = TimeZone.current
var cal = Calendar.current
cal.timeZone = tz

let args = CommandLine.arguments
let targetDate: Date
if args.count > 1, let parsed = parseArgDate(args[1], tz: tz) {
    targetDate = parsed
} else {
    targetDate = Date()
}
let (start, end) = getDayRange(cal, for: targetDate)

let fmt = ISO8601DateFormatter()
fmt.formatOptions = [.withInternetDateTime]
fmt.timeZone = tz

let store = EKEventStore()
let sem = DispatchSemaphore(value: 0)
var granted = false

if #available(macOS 14.0, *) {
    store.requestFullAccessToEvents { ok, err in
        granted = ok && err == nil
        sem.signal()
    }
} else {
    store.requestAccess(to: .event) { ok, err in
        granted = ok && err == nil
        sem.signal()
    }
}

_ = sem.wait(timeout: .now() + 10)
guard granted else {
    print("{\"error\":\"Calendar access not granted\"}")
    exit(1)
}

// Fetch + filter + sort
let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
let events = store.events(matching: predicate)
    .lazy                                     // avoids allocating intermediate arrays
    .filter { !$0.isAllDay }
    .filter {
        let t = $0.title.lowercased()
        return !t.contains("holiday") && !t.contains("birthday")
    }
    .sorted { $0.startDate < $1.startDate }

let result = events.map { mapEvent($0, fmt) }
printJSON(result)
