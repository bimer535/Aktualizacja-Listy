import SwiftUI
import Network

@main
struct MKTelnetApp: App {
    @StateObject private var telnet = TelnetClient()
    var body: some Scene {
        WindowGroup { TerminalScreen().environmentObject(telnet) }
    }
}

@MainActor
final class TelnetClient: ObservableObject {
    @Published var output = ""
    @Published var status = "Rozłączono"
    @Published var connected = false
    @Published var connecting = false
    private var connection: NWConnection?
    private var generation = 0
    private var parser = TelnetDecoder()

    func open(_ host: String, _ portText: String) {
        close()
        let hostname = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !hostname.isEmpty, let number = UInt16(portText),
              let port = NWEndpoint.Port(rawValue: number), number > 0 else {
            output = "Nieprawidłowy adres IP lub port.\n"
            return
        }
        generation += 1
        let id = generation
        parser = TelnetDecoder()
        output = "Łączenie z \(hostname):\(number)...\n"
        status = "Łączenie..."
        connecting = true
        let socket = NWConnection(host: NWEndpoint.Host(hostname), port: port, using: .tcp)
        connection = socket
        socket.stateUpdateHandler = { [weak self] state in
            Task { @MainActor [weak self] in
                guard let self, id == self.generation else { return }
                switch state {
                case .ready:
                    self.connecting = false
                    self.connected = true
                    self.status = "Połączono"
                    self.add("Połączono.\n")
                    self.read(id)
                case .failed(let error):
                    self.add("\nBłąd: \(error.localizedDescription)\n")
                    self.close()
                case .cancelled:
                    self.connected = false
                    self.connecting = false
                    self.status = "Rozłączono"
                case .waiting(let error):
                    self.status = "Oczekiwanie: \(error.localizedDescription)"
                default: break
                }
            }
        }
        socket.start(queue: .global(qos: .userInitiated))
    }

    func close() {
        generation += 1
        connection?.stateUpdateHandler = nil
        connection?.cancel()
        connection = nil
        connecting = false
        connected = false
        status = "Rozłączono"
    }

    func line(_ command: String) {
        guard connected else { return }
        var bytes = [UInt8]()
        for b in command.utf8 { bytes.append(b); if b == 255 { bytes.append(255) } }
        bytes += [13, 10]
        write(Data(bytes))
    }

    func interrupt() { if connected { write(Data([3])) } }

    private func write(_ bytes: Data) {
        connection?.send(content: bytes, completion: .contentProcessed { _ in })
    }

    private func read(_ id: Int) {
        guard let socket = connection else { return }
        socket.receive(minimumIncompleteLength: 1, maximumLength: 8192) {
            [weak self] data, _, finished, error in
            Task { @MainActor [weak self] in
                guard let self, self.generation == id else { return }
                if let data, !data.isEmpty {
                    let (text, replies) = self.parser.decode(data)
                    for reply in replies { self.write(reply) }
                    if !text.isEmpty {
                        self.add(String(decoding: text, as: UTF8.self)
                            .replacingOccurrences(of: "\r\n", with: "\n")
                            .replacingOccurrences(of: "\r", with: "\n"))
                    }
                }
                if let error {
                    self.add("\nBłąd: \(error.localizedDescription)\n")
                    self.close()
                } else if finished {
                    self.add("\nPołączenie zakończone przez dekoder.\n")
                    self.close()
                } else {
                    self.read(id)
                }
            }
        }
    }

    private func add(_ s: String) {
        output += s
        if output.count > 80000 { output = String(output.suffix(60000)) }
    }
}

private struct TelnetDecoder {
    private enum Step { case plain, iac, option(UInt8), sub, subIAC }
    private var step: Step = .plain
    private var sub = [UInt8]()

    mutating func decode(_ incoming: Data) -> (Data, [Data]) {
        var result = [UInt8]()
        var replies = [Data]()
        for byte in incoming {
            switch step {
            case .plain:
                if byte == 255 { step = .iac }
                else if byte != 0 { result.append(byte) }
            case .iac:
                switch byte {
                case 255: result.append(byte); step = .plain
                case 251, 252, 253, 254: step = .option(byte)
                case 250: sub = []; step = .sub
                default: step = .plain
                }
            case .option(let cmd):
                if cmd == 251 {
                    // Server WILL ECHO/SGA; client DO ECHO/SGA.
                    replies.append(Data([255, (byte == 1 || byte == 3) ? 253 : 254, byte]))
                } else if cmd == 253 {
                    // Server DO: client WILL SGA, TERM-TYPE or NAWS.
                    if [UInt8(3), 24, 31].contains(byte) {
                        replies.append(Data([255, 251, byte]))
                        if byte == 31 { replies.append(Data([255, 250, 31, 0, 80, 0, 24, 255, 240])) }
                    } else {
                        replies.append(Data([255, 252, byte]))
                    }
                }
                step = .plain
            case .sub:
                if byte == 255 { step = .subIAC }
                else { sub.append(byte) }
            case .subIAC:
                if byte == 240 {
                    if sub.count >= 2 && sub[0] == 24 && sub[1] == 1 {
                        replies.append(Data([255, 250, 24, 0] + Array("VT100".utf8) + [255, 240]))
                    }
                    step = .plain
                } else {
                    if byte == 255 { sub.append(255) }
                    step = .sub
                }
            }
        }
        return (Data(result), replies)
    }
}

struct TerminalScreen: View {
    @EnvironmentObject private var telnet: TelnetClient
    @AppStorage("MKLastIP") private var ip = "192.168.178.100"
    @AppStorage("MKLastPort") private var port = "23"
    @State private var command = ""
    @State private var secret = false
    @FocusState private var activeInput: Bool

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "terminal.fill").foregroundColor(.cyan)
                Text("MK Telnet").font(.title2.bold())
                Spacer()
                Circle().fill(telnet.connected ? Color.green : Color.gray)
                    .frame(width: 10, height: 10)
                Text(telnet.status).font(.caption)
            }
            HStack(spacing: 7) {
                TextField("Adres IP", text: $ip)
                    .keyboardType(.numbersAndPunctuation)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .textFieldStyle(.roundedBorder)
                    .disabled(telnet.connected || telnet.connecting)
                TextField("Port", text: $port)
                    .keyboardType(.numberPad)
                    .frame(width: 59)
                    .textFieldStyle(.roundedBorder)
                    .disabled(telnet.connected || telnet.connecting)
                Button(telnet.connected || telnet.connecting ? "Rozłącz" : "Połącz") {
                    if telnet.connected || telnet.connecting { telnet.close() }
                    else { telnet.open(ip, port) }
                }
                .buttonStyle(.borderedProminent)
            }
            ScrollViewReader { scroll in
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(telnet.output.isEmpty ?
                             "Wpisz IP dekodera i wybierz Połącz.\nNastępnie wpisz login, hasło i komendy." :
                             telnet.output)
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(.green)
                            .frame(maxWidth: .infinity, alignment: .topLeading)
                            .textSelection(.enabled)
                        Color.clear.frame(height: 1).id("end")
                    }.padding(12)
                }
                .background(Color(red: 0.035, green: 0.055, blue: 0.06))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .onChange(of: telnet.output) { _ in
                    scroll.scrollTo("end", anchor: .bottom)
                }
            }
            HStack {
                Group {
                    if secret {
                        SecureField("Hasło / polecenie", text: $command)
                    } else {
                        TextField("Komenda / login / hasło", text: $command)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }
                }
                .textFieldStyle(.roundedBorder)
                .font(.system(.body, design: .monospaced))
                .submitLabel(.send)
                .focused($activeInput)
                .onSubmit(sendCommand)
                .disabled(!telnet.connected)
                Button { secret.toggle() } label: {
                    Image(systemName: secret ? "eye.slash" : "eye")
                }
                .disabled(!telnet.connected)
                Button("Wyślij", action: sendCommand)
                    .buttonStyle(.borderedProminent)
                    .disabled(!telnet.connected)
            }
            HStack {
                Button("Wklej") {
                    if let value = UIPasteboard.general.string { command = value }
                    activeInput = true
                }
                Button("Ctrl+C") { telnet.interrupt() }
                    .disabled(!telnet.connected)
                Spacer()
                Text("Telnet · 23 · bez szyfrowania")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }.buttonStyle(.bordered)
        }
        .padding()
        .preferredColorScheme(.dark)
    }

    private func sendCommand() {
        guard telnet.connected else { return }
        telnet.line(command)
        command = ""
        activeInput = true
    }
}