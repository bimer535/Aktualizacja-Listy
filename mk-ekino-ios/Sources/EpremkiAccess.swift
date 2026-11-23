import SwiftUI
import Security

private enum SessionKey {
    static let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:"eu.epremki.kino.ios", kSecAttrAccount as String:"access"]
    static func read() -> String {
        var q=query; q[kSecReturnData as String]=true
        var object:CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary,&object)==errSecSuccess, let data=object as? Data else {return ""}
        return String(decoding:data,as:UTF8.self)
    }
    static func save(_ value:String){
        SecItemDelete(query as CFDictionary)
        guard !value.isEmpty else{return}
        var q=query;q[kSecValueData as String]=Data(value.utf8);q[kSecAttrAccessible as String]=kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        SecItemAdd(q as CFDictionary,nil)
    }
}

@MainActor final class EpremkiAccess: ObservableObject {
    @Published var allowed=false
    @Published var message=""
    @Published var busy=false
    @Published var expiry:Date?
    private var token=SessionKey.read()
    private var lastOK=Date.distantPast
    private let device:String
    init(){
        let defaults=UserDefaults.standard
        device=defaults.string(forKey:"install-id") ?? UUID().uuidString
        defaults.set(device,forKey:"install-id")
    }
    private struct Reply:Decodable {var ok:Bool;var expires:Double?;var token:String?}
    private func call(_ route:String,_ body:[String:String]) async throws -> (Int,Reply?){
        var fields=body;fields["client_id"]=device
        var req=URLRequest(url:URL(string:"https://ekino.hammdisplayfix.de/epremki-kino/api/"+route)!)
        req.httpMethod="POST";req.timeoutInterval=12;req.setValue("application/json",forHTTPHeaderField:"Content-Type")
        req.httpBody=try JSONEncoder().encode(fields)
        let (data,response)=try await URLSession.shared.data(for:req)
        return ((response as? HTTPURLResponse)?.statusCode ?? 0,try? JSONDecoder().decode(Reply.self,from:data))
    }
    private func confirm(_ until:Double){
        expiry=Date(timeIntervalSince1970:until);lastOK=Date();allowed=until>Date().timeIntervalSince1970;message=""
    }
    func login(_ name:String,_ password:String) async{
        guard !busy else{return};busy=true;defer{busy=false}
        do{
            let (code,r)=try await call("login",["username":name,"password":password])
            if code==200,r?.ok==true,let t=r?.token,t.count==64,let until=r?.expires{token=t;SessionKey.save(t);confirm(until)}
            else{message=[401:"Sprawdź login i hasło.",403:"Dostęp wygasł.",409:"Konto jest używane na innym urządzeniu.",429:"Za dużo prób. Spróbuj później."][code] ?? "Serwer jest chwilowo niedostępny."}
        }catch{message="Sprawdź połączenie z internetem."}
    }
    func check() async {
        let t=token;guard !t.isEmpty else{return}
        if Date().timeIntervalSince(lastOK)>60 || (expiry ?? .distantPast)<=Date(){allowed=false}
        do{
            let (code,r)=try await call("session",["token":t]);guard token==t else{return}
            if code==200,r?.ok==true,let until=r?.expires{confirm(until)}
            else if [401,403].contains(code){token="";SessionKey.save("");allowed=false;message="Zaloguj się ponownie."}
        }catch{}
    }
    func logout() async {
        let t=token;token="";SessionKey.save("");allowed=false;expiry=nil
        _ = try? await call("logout",["token":t])
    }
}

struct EpremkiRoot:View {
    @StateObject private var access=EpremkiAccess()
    @Environment(\.scenePhase) private var phase
    @State private var name=""
    @State private var password=""
    var body:some View{
        Group{
            if access.allowed{CinemaView().environmentObject(access)}
            else{ScrollView{VStack(spacing:16){
                Image("Brand").resizable().scaledToFit().frame(height:90)
                Text("Epremki kino").font(.largeTitle.bold())
                TextField("Login",text:$name).textInputAutocapitalization(.never).autocorrectionDisabled().textContentType(.username)
                SecureField("Hasło",text:$password).textContentType(.password)
                Button("Zaloguj się"){let pass=password;password="";Task{await access.login(name,pass)}}.disabled(name.isEmpty||password.isEmpty||access.busy)
                Text(access.message)
                Text("Dostęp w ramach Ultimate VIP na forum epremki.eu. W sprawie dostępu napisz do administratora Beliara.")
            }.textFieldStyle(.roundedBorder).padding(24).frame(maxWidth:520)}}
        }.task(id:phase){guard phase == .active else{return}
            while !Task.isCancelled{await access.check();try? await Task.sleep(nanoseconds:15_000_000_000)}
        }
    }
}
