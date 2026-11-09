// ContentView.swift — 根容器:三个原生 Tab(下载/历史/设置)
// 纯 SwiftUI 原生实现,无任何 WebView/网页套壳

import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            DownloadView()
                .tabItem { Label("下载", systemImage: "arrow.down.circle.fill") }
            HistoryView()
                .tabItem { Label("历史", systemImage: "clock.fill") }
            SettingsView()
                .tabItem { Label("设置", systemImage: "gearshape.fill") }
        }
        .tint(.blue)
    }
}
