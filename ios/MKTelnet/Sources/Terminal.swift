import SwiftUI
import UIKit
import Network

@MainActor
final class TelnetSession: ObservableObject {
    enum Status { case disconnected, connecting, connected }
    @Published var status: Status = .disconnected
    @Published var output = ""
    private var socket: NWConnection?
    private var telnetState = 0
    private var generation = 0
    func connect(host: String, portNumber: UInt16) {
        disconnect()
        let host = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !host.isEmpty, portNumber > 0, let port = NWEndpoint.Port(rawValue: portNumber) else { output = "Niepoprawny adres lub port"; return }
        output = "Łączenie z \(host):\(portNumber)…\n"
        status = .connecting
        generation += 1
        let run = generation
        let c = NWConnection(host: NWEndpoint.Host(host), port: port, using: .tcp)
        socket = c
        c.stateUpdateHandler = { [weak self] state in
            Task { @MainActor [weak self] in
                guard let self = self, self.generation == run else { return }
                switch state {
                case .ready: self.status = .connected; self.output += "Połączono.\n"; self.receive(run)
                case .failed(let err): self.output += "\nBłąd: \(err.localizedDescription)\n"; self.disconnect()
                case .waiting(let err): self.output += "\nOczekiwanie: \(err.localizedDescription)\n"
                default: break
                }
            }
        }
        c.start(queue: .global(qos: .userInitiated))
    }
    func disconnect() {
        generation += 1
        socket?.cancel()
        socket = nil
        status = .disconnected
    }
    func sendLine(_ line: String) {
        let data = Data((line + "\r\n").utf8)
        socket?.send(content: data, completion: .contentProcessed { _ in })
    }
    func sendInterrupt() { socket?.send(content: Data([255,244]), completion: .contentProcessed { _ in }) }
    private func receive(_ run: Int) {
        guard let c = socket else { return }
        c.receive(minimumIncompleteLength: 1, maximumLength: 4096) { [weak self] data, _, complete, error in
            Task { @MainActor [weak self] in
                guard let self = self, self.generation == run else { return }
                if let data = data { self.handle(data) }
                if complete || error != nil { self.output += "\nRozłączono.\n"; self.disconnect() }
                else { self.receive(run) }
            }
        }
    }
    private func handle(_ data: Data) {
        let bytes = Array(data)
        var clean = [UInt8]()
        var i = 0
        while i < bytes.count {
            let b = bytes[i]
            if b == 255 {
                if i + 1 < bytes.count {
                    let cmd = bytes[i+1]
                    if cmd == 255 { clean.append(255); i += 2; continue }
                    if [251,252,253,254].contains(cmd), i + 2 < bytes.count {
                        let option = bytes[i+2]
                        let reply: UInt8 = (cmd == 253 || cmd == 254) ? 252 : 254
                        socket?.send(content: Data([255,reply,option]), completion: .contentProcessed { _ in })
                        i += 3
                        continue
                    }
                    if cmd == 250 {
                        i += 2
                        while i + 1 < bytes.count && !(bytes[i] == 255 && bytes[i+1] == 240) { i += 1 }
                        i = min(i + 2, bytes.count); continue
                    }
                    i += 2; continue
                } else { break }
            }
            if b != 0 && b != 8 { clean.append(b) }
            i += 1
        }
        output += String(decoding: clean, as: UTF8.self)
        if output.count > 60000 { output = String(output.suffix(40000)) }
    }
}

@main
struct MKTelnetApp: App {
    @StateObject private var session = TelnetSession()
    var body: some Scene {
        WindowGroup {
            TerminalView().environmentObject(session)
        }
    }
}

struct TerminalView: View {
    @EnvironmentObject private var session: TelnetSession
    @AppStorage("host") private var host = "192.168.178.100"
    @AppStorage("port") private var port = "23"
    @State private var line = ""
    @State private var secret = false
    private var connected: Bool { session.status == .connected }
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "terminal.fill")
                Text("MK Telnet").font(.title2.bold())
                Spacer()
                Circle().fill(connected ? .green : .gray).frame(width: 10,height:10)
            }
            HStack {
                TextField("IP dekodera", text:$host).textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                TextField("Port", text:$port).keyboardType(.numberPad).frame(width:55).textFieldStyle(.roundedBorder)
                Button(session.status == .disconnected ? "Połącz" : "Rozłącz") {
                    if session.status == .disconnected { session.connect(host: host, portNumber: UInt16(port) ?? 23) }
                    else { session.disconnect() }
                }.buttonStyle(.borderedProminent)
            }
            ScrollViewReader { proxy in
                ScrollView {
                    Text(session.output.isEmpty ? "Wpisz adres IP i połącz z dekoderem." : session.output)
                        .font(.system(size:13, design:.monospaced))
                        .foregroundColor(.green)
                        .frame(maxWidth:.infinity, alignment:.topLeading)
                        .textSelection(.enabled)
                    Color.clear.frame(height: 1).id("end")
                }
                .padding(12)
                .frame(maxWidth:.infinity, maxHeight:.infinity)
                .background(Color.black)
                .clipShape(RoundedRectangle(cornerRadius:12))
                .onChange(of:session.output) { _ in proxy.scrollTo("end",anchor:.bottom) }
            }
            HStack {
                Group {
                    if secret { SecureField("Hasło", text:$line) }
                    else { TextField("Komenda, login lub hasło",text:$line).textInputAutocapitalization(.never).autocorrectionDisabled() }
                }
                .font(.system(.body,design:.monospaced))
                .textFieldStyle(.roundedBorder)
                .onSubmit(send)
                Button { secret.toggle() } label: { Image(systemName: secret ? "eye.slash" : "eye") }
                Button("Wyślij",action:send).buttonStyle(.borderedProminent)
            }.disabled(!connected)
            HStack {
                Button("Wklej") { line = UIPasteboard.general.string ?? "" }
                Button("Ctrl+C") { session.sendInterrupt() }.disabled(!connected)
                Spacer()
                Text("Telnet 23 · bez szyfrowania").font(.caption2).foregroundColor(.secondary)
            }.buttonStyle(.bordered)
        }
        .padding()
        .preferredColorScheme(.dark)
    }
    private func send() { session.sendLine(line); line = "" }
}
