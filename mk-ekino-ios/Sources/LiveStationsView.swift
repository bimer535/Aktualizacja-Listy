import SwiftUI
import AVKit

private struct Station: Identifiable, Hashable {
    let name:String
    let id:String
    static var defaults:[Station] {
        guard let url=Bundle.main.url(forResource:"free-tv",withExtension:"json"),let data=try? Data(contentsOf:url),let rows=try? JSONDecoder().decode([String:String].self,from:data) else{return []}
        return rows.map{Station(name:$0.key,id:$0.value)}.sorted{$0.name.localizedStandardCompare($1.name) == .orderedAscending}
    }
}

struct LiveStationsView:View{
    @Environment(\.dismiss) private var dismiss
    @State private var stations=Station.defaults
    @State private var selected:Station?
    var body:some View{
        NavigationStack{ScrollView{LazyVGrid(columns:[GridItem(.adaptive(minimum:135))],spacing:12){
            ForEach(stations){s in Button(s.name){selected=s}.buttonStyle(CinemaButtonStyle()).frame(minHeight:58)}
        }.padding()}.navigationTitle("Kanały TV").toolbar{ToolbarItem(placement:.cancellationAction){Button("Zamknij"){dismiss()}}}}
        .fullScreenCover(item:$selected){s in LivePlayback(stations:stations,initial:s)}
    }
}

private struct LivePlayback:View{
    let stations:[Station]
    @State var current:Station
    @State private var player=AVPlayer()
    @State private var status=""
    @State private var controls=true
    @State private var choosing=false
    @State private var timer=UUID()
    @State private var revision=0
    @Environment(\.dismiss) private var dismiss
    init(stations:[Station],initial:Station){self.stations=stations;_current=State(initialValue:initial)}
    func switchBy(_ d:Int){guard let i=stations.firstIndex(of:current) else{return};current=stations[(i+d+stations.count)%stations.count];revision+=1;timer=UUID()}
    var body:some View{
        ZStack{Color.black.ignoresSafeArea()
            LiveSurface(player:player).ignoresSafeArea().contentShape(Rectangle()).onTapGesture{controls.toggle();timer=UUID()}
            if !status.isEmpty{Text(status).padding().background(.black.opacity(0.75))}
            if controls{VStack{HStack{Button("Wróć"){dismiss()};Spacer()};Spacer()
                HStack{Button("Kanał −"){switchBy(-1)};Button(current.name){choosing=true};Button("Kanał +"){switchBy(1)}}
            }.buttonStyle(.borderedProminent).padding()}
        }.sheet(isPresented:$choosing){NavigationStack{List(stations){s in Button(s.name){current=s;revision+=1;choosing=false;timer=UUID()}}.navigationTitle("Wybierz kanał")}}
        .task(id:timer){try? await Task.sleep(nanoseconds:3_000_000_000);if !Task.isCancelled && !choosing && status.isEmpty{controls=false}}
        .task(id:revision){
            let station=current
            player.replaceCurrentItem(with:nil);status="Łączenie…"
            for attempt in 0..<2 {
                do{
                    var req=URLRequest(url:URL(string:"https://turbotv.cc/pl/live/stream/")!.appendingPathComponent(station.id));req.timeoutInterval=12
                    req.cachePolicy = .reloadIgnoringLocalCacheData
                    req.setValue("application/json",forHTTPHeaderField:"Accept")
                    let (data,response)=try await URLSession.shared.data(for:req);try Task.checkCancellation()
                    guard let http=response as? HTTPURLResponse,http.statusCode==200 else{status="TurboTV nie udostępniło teraz kanału.";return}
                    struct Reply:Decodable{let url:URL}
                    let url=try JSONDecoder().decode(Reply.self,from:data).url
                    guard url.scheme=="https",url.host != nil,url.user==nil,url.password==nil else{throw URLError(.badURL)}
                    let item=AVPlayerItem(url:url);player.replaceCurrentItem(with:item);player.play()
                    var started=false,polls=0
                    while !Task.isCancelled{
                        if item.status == .failed || player.error != nil{throw URLError(.cannotDecodeContentData)}
                        if !started && player.timeControlStatus == .playing{started=true;status="";timer=UUID()}
                        polls+=1;if !started && polls>=100{throw URLError(.timedOut)}
                        try await Task.sleep(nanoseconds:250_000_000)
                    }
                    return
                }catch{if Task.isCancelled{return};player.replaceCurrentItem(with:nil);status=attempt==0 ? "Odnawianie połączenia…" : "Kanał jest chwilowo niedostępny."}
            }
        }.onDisappear{player.pause();player.replaceCurrentItem(with:nil)}
    }
}
private final class LiveScreen:UIView{
    override class var layerClass:AnyClass{AVPlayerLayer.self}
}
private struct LiveSurface:UIViewRepresentable{
    let player:AVPlayer
    func makeUIView(context:Context)->LiveScreen{let view=LiveScreen();(view.layer as? AVPlayerLayer)?.videoGravity = .resizeAspect;return view}
    func updateUIView(_ view:LiveScreen,context:Context){(view.layer as? AVPlayerLayer)?.player=player}
}
