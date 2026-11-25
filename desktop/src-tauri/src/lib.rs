use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Duration;
use tauri::menu::{CheckMenuItem, CheckMenuItemBuilder, MenuBuilder, MenuItem, MenuItemBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_autostart::ManagerExt as AutostartExt;
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_global_shortcut::ShortcutState;
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_opener::OpenerExt;
use tokio::sync::Notify;

const DEFAULT_SERVER_URL: &str = "https://app.dev8084.io.vn";
const GITHUB_REPO: &str = "nguyenngocdantruong/TrackingOrder";
const POLL_INTERVAL_SECS: u64 = 90;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CachedAddress {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub is_default: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PersistedState {
    pub server_url: String,
    pub token: Option<String>,
    pub username: Option<String>,
    pub desktop_notify: bool,
    pub start_minimized: bool,
    pub clipboard_watch: bool,
    pub close_hint_shown: bool,
    pub seeded_initial_hashes: bool,
    pub seen_hashes: HashSet<String>,
    pub last_updated_tracking_id: Option<String>,
    #[serde(default)]
    pub cached_addresses: Vec<CachedAddress>,
}

impl Default for PersistedState {
    fn default() -> Self {
        Self {
            server_url: DEFAULT_SERVER_URL.to_string(),
            token: None,
            username: None,
            desktop_notify: true,
            start_minimized: true,
            clipboard_watch: true,
            close_hint_shown: false,
            seeded_initial_hashes: false,
            seen_hashes: HashSet::new(),
            last_updated_tracking_id: None,
            cached_addresses: Vec::new(),
        }
    }
}

pub struct TrayHandles {
    pub status_item: MenuItem<tauri::Wry>,
    pub notify_check: CheckMenuItem<tauri::Wry>,
    pub autostart_check: CheckMenuItem<tauri::Wry>,
}

pub struct AppState {
    pub store_path: PathBuf,
    pub data: Mutex<PersistedState>,
    pub sync_wakeup: Notify,
    pub tray: Mutex<Option<TrayHandles>>,
}

impl AppState {
    fn load(store_path: PathBuf) -> Self {
        let data = fs::read_to_string(&store_path)
            .ok()
            .and_then(|raw| serde_json::from_str::<PersistedState>(&raw).ok())
            .unwrap_or_default();
        Self {
            store_path,
            data: Mutex::new(data),
            sync_wakeup: Notify::new(),
            tray: Mutex::new(None),
        }
    }

    fn save(&self, snapshot: &PersistedState) {
        if let Some(parent) = self.store_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(json) = serde_json::to_string_pretty(snapshot) {
            let _ = fs::write(&self.store_path, json);
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopPrefsResponse {
    pub app_version: String,
    pub server_url: String,
    pub has_token: bool,
    pub username: Option<String>,
    pub desktop_notify: bool,
    pub autostart: bool,
    pub start_minimized: bool,
    pub clipboard_watch: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateCheckResult {
    pub current_version: String,
    pub latest_version: String,
    pub update_available: bool,
    pub download_url: String,
    pub release_url: String,
    pub published_at: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ServerReleaseEnvelope {
    success: bool,
    data: Option<ServerReleasePayload>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ServerReleasePayload {
    version: String,
    exe_url: Option<String>,
    msi_url: Option<String>,
    release_url: Option<String>,
    published_at: Option<String>,
}

#[derive(Debug, Deserialize)]
struct GitHubRelease {
    tag_name: Option<String>,
    html_url: Option<String>,
    published_at: Option<String>,
    #[serde(default)]
    assets: Vec<GitHubAsset>,
}

#[derive(Debug, Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct QuickAddContext {
    pub has_token: bool,
    pub clipboard_candidate: Option<String>,
    pub addresses: Vec<CachedAddress>,
}

#[derive(Debug, Deserialize)]
struct DesktopStateEnvelope {
    success: bool,
    data: Option<DesktopStatePayload>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DesktopStatePayload {
    #[serde(default)]
    addresses: Vec<CachedAddress>,
    summary: DesktopSummary,
    #[serde(default)]
    checkpoints: Vec<DesktopCheckpoint>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DesktopSummary {
    scoped_active_count: u32,
    scoped_active_cod: u64,
    scope_label: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DesktopCheckpoint {
    tracking_id: Option<String>,
    tracking_number: String,
    alias: String,
    address_name: String,
    cod_amount: u64,
    event_hash: String,
    event_name: String,
    location: String,
    stage: String,
    stage_label: String,
    notify_allowed: bool,
}

fn format_vnd(amount: u64) -> String {
    let s = amount.to_string();
    let mut out = String::new();
    for (count, ch) in s.chars().rev().enumerate() {
        if count > 0 && count % 3 == 0 {
            out.push('.');
        }
        out.push(ch);
    }
    let formatted: String = out.chars().rev().collect();
    format!("{} ₫", formatted)
}

fn extract_tracking_candidate(raw: &str) -> Option<String> {
    let trimmed = raw.trim().to_uppercase();
    if trimmed.len() < 8 || trimmed.len() > 36 || trimmed.contains(char::is_whitespace) {
        return None;
    }
    let is_spx_or_lex = trimmed.starts_with("SPX")
        || trimmed.starts_with("LEX")
        || trimmed.starts_with("LZD")
        || (trimmed.starts_with("VN") && trimmed.len() >= 12);
    let is_jt = {
        let parts: Vec<&str> = trimmed.split('-').collect();
        match parts.as_slice() {
            [code] => code.len() >= 10 && code.len() <= 15 && code.chars().all(|c| c.is_ascii_digit()),
            [code, suffix] => {
                code.len() >= 10
                    && code.len() <= 15
                    && suffix.len() == 4
                    && code.chars().all(|c| c.is_ascii_digit())
                    && suffix.chars().all(|c| c.is_ascii_digit())
            }
            _ => false,
        }
    };
    if is_spx_or_lex || is_jt {
        Some(trimmed)
    } else {
        None
    }
}

fn focus_and_navigate_main(app: &AppHandle, path: Option<&str>) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.show();
        let _ = win.unminimize();
        let _ = win.set_focus();
        if let Some(subpath) = path {
            let state = app.state::<AppState>();
            let base = state.data.lock().unwrap().server_url.clone();
            let target = format!("{}/{}", base.trim_end_matches('/'), subpath.trim_start_matches('/'));
            if let Ok(parsed) = target.parse() {
                let _ = win.navigate(parsed);
            }
        }
    }
}

fn show_quick_add_window(app: &AppHandle) {
    if let Some(existing) = app.get_webview_window("quick-add") {
        let _ = existing.show();
        let _ = existing.set_focus();
        return;
    }
    let _ = WebviewWindowBuilder::new(app, "quick-add", WebviewUrl::App("quick-add.html".into()))
        .title("Thêm vận đơn nhanh · Order Tracker")
        .inner_size(460.0, 320.0)
        .resizable(false)
        .always_on_top(true)
        .center()
        .build();
}

#[tauri::command]
fn get_desktop_prefs(app: AppHandle, state: tauri::State<'_, AppState>) -> DesktopPrefsResponse {
    let guard = state.data.lock().unwrap();
    let autostart = app.autolaunch().is_enabled().unwrap_or(false);
    DesktopPrefsResponse {
        app_version: env!("CARGO_PKG_VERSION").to_string(),
        server_url: guard.server_url.clone(),
        has_token: guard.token.is_some(),
        username: guard.username.clone(),
        desktop_notify: guard.desktop_notify,
        autostart,
        start_minimized: guard.start_minimized,
        clipboard_watch: guard.clipboard_watch,
    }
}

#[tauri::command]
fn set_desktop_prefs(
    app: AppHandle,
    state: tauri::State<'_, AppState>,
    desktop_notify: bool,
    autostart: bool,
    start_minimized: bool,
    clipboard_watch: bool,
) -> Result<(), String> {
    if autostart {
        let _ = app.autolaunch().enable();
    } else {
        let _ = app.autolaunch().disable();
    }

    let snapshot = {
        let mut guard = state.data.lock().unwrap();
        guard.desktop_notify = desktop_notify;
        guard.start_minimized = start_minimized;
        guard.clipboard_watch = clipboard_watch;
        guard.clone()
    };
    state.save(&snapshot);

    if let Some(handles) = state.tray.lock().unwrap().as_ref() {
        let _ = handles.notify_check.set_checked(desktop_notify);
        let _ = handles.autostart_check.set_checked(autostart);
    }
    Ok(())
}

#[tauri::command]
fn sync_desktop_auth(
    state: tauri::State<'_, AppState>,
    server_url: String,
    token: String,
    username: String,
) {
    let snapshot = {
        let mut guard = state.data.lock().unwrap();
        let clean_url = server_url.trim().trim_end_matches('/').to_string();
        if !clean_url.is_empty() {
            guard.server_url = clean_url;
        }
        let token_changed = guard.token.as_deref() != Some(token.as_str());
        guard.token = Some(token);
        guard.username = if username.is_empty() { None } else { Some(username) };
        if token_changed {
            guard.seeded_initial_hashes = false;
        }
        guard.clone()
    };
    state.save(&snapshot);
    state.sync_wakeup.notify_one();
}

#[tauri::command]
async fn clear_desktop_auth(app: AppHandle, state: tauri::State<'_, AppState>) -> Result<(), String> {
    let (server_url, old_token, snapshot) = {
        let mut guard = state.data.lock().unwrap();
        let srv = guard.server_url.clone();
        let tok = guard.token.take();
        guard.username = None;
        guard.seeded_initial_hashes = false;
        guard.seen_hashes.clear();
        guard.cached_addresses.clear();
        (srv, tok, guard.clone())
    };
    state.save(&snapshot);

    if let Some(handles) = state.tray.lock().unwrap().as_ref() {
        let _ = handles.status_item.set_text("Chưa đăng nhập tài khoản");
    }
    if let Some(tray) = app.tray_by_id("main-tray") {
        let _ = tray.set_tooltip(Some("Order Tracker · Chưa đăng nhập"));
    }

    if let Some(tok) = old_token {
        let client = reqwest::Client::builder().timeout(Duration::from_secs(5)).build().ok();
        if let Some(http) = client {
            let _ = http
                .post(format!("{}/api/v1/desktop/logout", server_url.trim_end_matches('/')))
                .bearer_auth(tok)
                .send()
                .await;
        }
    }
    Ok(())
}

#[tauri::command]
fn switch_server_url(state: tauri::State<'_, AppState>, server_url: String) {
    let clean = server_url.trim().trim_end_matches('/').to_string();
    if clean.is_empty() {
        return;
    }
    let snapshot = {
        let mut guard = state.data.lock().unwrap();
        if guard.server_url != clean {
            guard.server_url = clean;
            guard.token = None;
            guard.seeded_initial_hashes = false;
        }
        guard.clone()
    };
    state.save(&snapshot);
}

#[tauri::command]
fn trigger_sync_now(state: tauri::State<'_, AppState>) {
    state.sync_wakeup.notify_one();
}

#[tauri::command]
fn send_test_desktop_notification(app: AppHandle) -> Result<(), String> {
    app.notification()
        .builder()
        .title("Order Tracker · Thông báo thử nghiệm")
        .body("Kết nối thông báo gốc trên Windows hoạt động bình thường!")
        .show()
        .map_err(|e| e.to_string())
}

fn clean_version_str(raw: &str) -> String {
    let s = raw.trim();
    let s = s.strip_prefix("desktop-").unwrap_or(s);
    let s = s.strip_prefix('v').or_else(|| s.strip_prefix('V')).unwrap_or(s);
    s.trim().to_string()
}

fn parse_version_tuple(v: &str) -> Vec<u64> {
    let clean = clean_version_str(v);
    let core = clean.split('-').next().unwrap_or(&clean);
    core.split('.')
        .map(|part| part.parse::<u64>().unwrap_or(0))
        .collect()
}

fn is_newer_version(latest: &str, current: &str) -> bool {
    let a = parse_version_tuple(latest);
    let b = parse_version_tuple(current);
    let max_len = a.len().max(b.len());
    for i in 0..max_len {
        let av = *a.get(i).unwrap_or(&0);
        let bv = *b.get(i).unwrap_or(&0);
        if av != bv {
            return av > bv;
        }
    }
    false
}

async fn perform_update_check(app: &AppHandle) -> Result<UpdateCheckResult, String> {
    let current_version = env!("CARGO_PKG_VERSION").to_string();
    let server_url = {
        let st = app.state::<AppState>();
        let guard = st.data.lock().unwrap();
        guard.server_url.clone()
    };

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .user_agent(format!("OrderTracker-Windows-Tauri/{}", current_version))
        .build()
        .map_err(|e| e.to_string())?;

    let fallback_releases_url = format!("https://github.com/{}/releases", GITHUB_REPO);

    // 1) Try backend cached endpoint first
    let api_endpoint = format!(
        "{}/api/v1/desktop/latest-release",
        server_url.trim_end_matches('/')
    );
    if let Ok(resp) = client.get(&api_endpoint).send().await {
        if resp.status().is_success() {
            if let Ok(env) = resp.json::<ServerReleaseEnvelope>().await {
                if env.success {
                    if let Some(data) = env.data {
                        let latest = clean_version_str(&data.version);
                        let release_url = data
                            .release_url
                            .filter(|u| !u.is_empty())
                            .unwrap_or_else(|| fallback_releases_url.clone());
                        let download_url = data
                            .exe_url
                            .or(data.msi_url)
                            .unwrap_or_else(|| release_url.clone());
                        let update_available = is_newer_version(&latest, &current_version);
                        return Ok(UpdateCheckResult {
                            current_version,
                            latest_version: latest,
                            update_available,
                            download_url,
                            release_url,
                            published_at: data.published_at,
                        });
                    }
                }
            }
        }
    }

    // 2) Fallback directly to GitHub Releases API
    let gh_endpoint = format!(
        "https://api.github.com/repos/{}/releases/latest",
        GITHUB_REPO
    );
    let gh_resp = client
        .get(&gh_endpoint)
        .header("Accept", "application/vnd.github+json")
        .send()
        .await
        .map_err(|_| "Không thể kết nối máy chủ để kiểm tra cập nhật.".to_string())?;

    if gh_resp.status().as_u16() == 404 {
        return Ok(UpdateCheckResult {
            current_version: current_version.clone(),
            latest_version: current_version,
            update_available: false,
            download_url: fallback_releases_url.clone(),
            release_url: fallback_releases_url,
            published_at: None,
        });
    }

    if !gh_resp.status().is_success() {
        return Err(format!(
            "Máy chủ cập nhật phản hồi lỗi (HTTP {}).",
            gh_resp.status().as_u16()
        ));
    }

    let rel: GitHubRelease = gh_resp
        .json()
        .await
        .map_err(|_| "Không đọc được thông tin phiên bản mới nhất.".to_string())?;

    let latest = rel
        .tag_name
        .as_deref()
        .map(clean_version_str)
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| current_version.clone());

    let release_url = rel
        .html_url
        .filter(|u| !u.is_empty())
        .unwrap_or_else(|| fallback_releases_url.clone());

    let exe_url = rel
        .assets
        .iter()
        .find(|a| a.name.to_lowercase().ends_with(".exe"))
        .map(|a| a.browser_download_url.clone());
    let msi_url = rel
        .assets
        .iter()
        .find(|a| a.name.to_lowercase().ends_with(".msi"))
        .map(|a| a.browser_download_url.clone());

    let download_url = exe_url.or(msi_url).unwrap_or_else(|| release_url.clone());
    let published_at = rel
        .published_at
        .map(|p| p.chars().take(10).collect::<String>());
    let update_available = is_newer_version(&latest, &current_version);

    Ok(UpdateCheckResult {
        current_version,
        latest_version: latest,
        update_available,
        download_url,
        release_url,
        published_at,
    })
}

#[tauri::command]
async fn check_for_updates(app: AppHandle) -> Result<UpdateCheckResult, String> {
    perform_update_check(&app).await
}

#[tauri::command]
fn open_external_url(app: AppHandle, url: String) -> Result<(), String> {
    let trimmed = url.trim();
    if !(trimmed.starts_with("https://") || trimmed.starts_with("http://")) {
        return Err("Đường dẫn không hợp lệ.".to_string());
    }
    app.opener()
        .open_url(trimmed, None::<&str>)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn get_quick_add_context(app: AppHandle, state: tauri::State<'_, AppState>) -> QuickAddContext {
    let (has_token, watch_clip, addresses) = {
        let guard = state.data.lock().unwrap();
        (guard.token.is_some(), guard.clipboard_watch, guard.cached_addresses.clone())
    };
    let clipboard_candidate = if watch_clip {
        app.clipboard()
            .read_text()
            .ok()
            .and_then(|txt| extract_tracking_candidate(&txt))
    } else {
        None
    };
    QuickAddContext {
        has_token,
        clipboard_candidate,
        addresses,
    }
}

#[tauri::command]
fn close_quick_add(app: AppHandle) {
    if let Some(win) = app.get_webview_window("quick-add") {
        let _ = win.close();
    }
}

#[tauri::command]
async fn submit_quick_add(
    app: AppHandle,
    state: tauri::State<'_, AppState>,
    tracking_number: String,
    alias: Option<String>,
    address_id: Option<String>,
) -> Result<(), String> {
    let (server_url, token) = {
        let guard = state.data.lock().unwrap();
        (guard.server_url.clone(), guard.token.clone())
    };
    let tok = token.ok_or_else(|| "Chưa đăng nhập tài khoản.".to_string())?;

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(20))
        .build()
        .map_err(|e| e.to_string())?;

    let payload = serde_json::json!({
        "tracking_number": tracking_number,
        "alias": alias,
        "address_id": address_id,
    });

    let resp = client
        .post(format!("{}/api/v1/desktop/quick-add", server_url.trim_end_matches('/')))
        .bearer_auth(tok)
        .json(&payload)
        .send()
        .await
        .map_err(|_| "Không thể kết nối máy chủ Order Tracker.".to_string())?;

    let status = resp.status();
    let body: serde_json::Value = resp.json().await.unwrap_or_default();
    if status.is_success() || status.as_u16() == 409 {
        state.sync_wakeup.notify_one();
        if let Some(win) = app.get_webview_window("main") {
            let _ = win.eval("if (window.location.pathname === '/dashboard') window.location.reload();");
        }
        return Ok(());
    }

    let err_msg = body
        .get("error")
        .and_then(|e| e.get("message"))
        .and_then(|m| m.as_str())
        .unwrap_or("Không thể thêm mã vận đơn này.");
    Err(err_msg.to_string())
}

async fn poll_once(app: &AppHandle, client: &reqwest::Client) {
    let (server_url, token, notify_enabled) = {
        let state = app.state::<AppState>();
        let guard = state.data.lock().unwrap();
        match &guard.token {
            Some(t) => (guard.server_url.clone(), t.clone(), guard.desktop_notify),
            None => return,
        }
    };

    let endpoint = format!("{}/api/v1/desktop/state", server_url.trim_end_matches('/'));
    let resp = match client.get(&endpoint).bearer_auth(&token).send().await {
        Ok(r) => r,
        Err(_) => return,
    };

    if resp.status().as_u16() == 401 {
        let state = app.state::<AppState>();
        let snapshot = {
            let mut guard = state.data.lock().unwrap();
            guard.token = None;
            guard.clone()
        };
        state.save(&snapshot);
        return;
    }

    let parsed: DesktopStateEnvelope = match resp.json().await {
        Ok(v) => v,
        Err(_) => return,
    };
    if !parsed.success {
        return;
    }
    let Some(payload) = parsed.data else {
        return;
    };

    // Update System Tray summary line & tooltip
    let summary_line = if payload.summary.scoped_active_cod > 0 {
        format!(
            "{} · {} đơn đang giao · COD {}",
            payload.summary.scope_label,
            payload.summary.scoped_active_count,
            format_vnd(payload.summary.scoped_active_cod)
        )
    } else {
        format!(
            "{} · {} đơn đang theo dõi",
            payload.summary.scope_label, payload.summary.scoped_active_count
        )
    };

    let state = app.state::<AppState>();
    if let Some(handles) = state.tray.lock().unwrap().as_ref() {
        let _ = handles.status_item.set_text(&summary_line);
    }
    if let Some(tray) = app.tray_by_id("main-tray") {
        let _ = tray.set_tooltip(Some(format!("Order Tracker · {}", summary_line)));
    }

    // Diff checkpoints & fire native Windows Toast notifications
    let mut to_notify: Vec<(String, String, Option<String>)> = Vec::new();
    let snapshot = {
        let mut guard = state.data.lock().unwrap();
        guard.cached_addresses = payload.addresses;

        if !guard.seeded_initial_hashes {
            for cp in &payload.checkpoints {
                guard.seen_hashes.insert(cp.event_hash.clone());
            }
            if let Some(first) = payload.checkpoints.first() {
                guard.last_updated_tracking_id = first.tracking_id.clone();
            }
            guard.seeded_initial_hashes = true;
        } else {
            for cp in &payload.checkpoints {
                if guard.seen_hashes.insert(cp.event_hash.clone()) {
                    guard.last_updated_tracking_id = cp.tracking_id.clone();
                    if notify_enabled && cp.notify_allowed {
                        let label = if cp.alias.is_empty() {
                            cp.tracking_number.clone()
                        } else {
                            cp.alias.clone()
                        };
                        let title = format!("{} · {}", label, cp.stage_label);
                        let mut body_parts = vec![cp.event_name.clone()];
                        if !cp.location.is_empty() {
                            body_parts.push(cp.location.clone());
                        }
                        if cp.stage == "out_for_delivery" && cp.cod_amount > 0 {
                            body_parts.push(format!("COD {}", format_vnd(cp.cod_amount)));
                        }
                        if !cp.address_name.is_empty() {
                            body_parts.push(format!("({})", cp.address_name));
                        }
                        to_notify.push((title, body_parts.join(" · "), cp.tracking_id.clone()));
                    }
                }
            }
        }
        if guard.seen_hashes.len() > 500 {
            let keep: HashSet<String> = payload.checkpoints.iter().map(|c| c.event_hash.clone()).collect();
            guard.seen_hashes = keep;
        }
        guard.clone()
    };
    state.save(&snapshot);

    for (title, body, _) in to_notify.into_iter().take(4) {
        let _ = app.notification().builder().title(&title).body(&body).show();
    }
}

pub fn run() {
    let started_minimized = std::env::args().any(|a| a == "--minimized");

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            focus_and_navigate_main(app, None);
        }))
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_opener::init())
        .setup(move |app| {
            let app_dir = app
                .path()
                .app_data_dir()
                .unwrap_or_else(|_| PathBuf::from("."));
            let store_path = app_dir.join("desktop_state.json");
            let app_state = AppState::load(store_path);
            let initial_notify = app_state.data.lock().unwrap().desktop_notify;
            let should_hide_boot = started_minimized && app_state.data.lock().unwrap().start_minimized;
            app.manage(app_state);

            if should_hide_boot {
                if let Some(main_win) = app.get_webview_window("main") {
                    let _ = main_win.hide();
                }
            }

            // Global Hotkey: Ctrl+Shift+T opens floating Quick Add window
            #[cfg(desktop)]
            {
                let _ = app.handle().plugin(
                    tauri_plugin_global_shortcut::Builder::new()
                        .with_shortcuts(["ctrl+shift+t"])?
                        .with_handler(|app_handle, _shortcut, event| {
                            if event.state() == ShortcutState::Pressed {
                                show_quick_add_window(app_handle);
                            }
                        })
                        .build(),
                );
            }

            // System Tray Menu
            let initial_autostart = app.autolaunch().is_enabled().unwrap_or(false);
            let status_item = MenuItemBuilder::with_id("status", "Order Tracker · Đang đồng bộ…")
                .enabled(false)
                .build(app)?;
            let open_dash = MenuItemBuilder::with_id("open_dash", "Mở bảng điều khiển").build(app)?;
            let quick_add = MenuItemBuilder::with_id("quick_add", "Thêm vận đơn nhanh (Ctrl+Shift+T)").build(app)?;
            let open_latest = MenuItemBuilder::with_id("open_latest", "Mở đơn vừa cập nhật").build(app)?;
            let sync_now = MenuItemBuilder::with_id("sync_now", "Làm mới ngay").build(app)?;
            let notify_check = CheckMenuItemBuilder::with_id("toggle_notify", "Nhận thông báo trên Windows")
                .checked(initial_notify)
                .build(app)?;
            let test_notify = MenuItemBuilder::with_id("test_notify", "Gửi thông báo test").build(app)?;
            let autostart_check = CheckMenuItemBuilder::with_id("toggle_autostart", "Khởi động cùng Windows")
                .checked(initial_autostart)
                .build(app)?;
            let check_updates = MenuItemBuilder::with_id("check_updates", "Kiểm tra cập nhật…").build(app)?;
            let switch_srv = MenuItemBuilder::with_id("switch_srv", "Đổi máy chủ kết nối…").build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "Thoát hoàn toàn").build(app)?;

            let tray_menu = MenuBuilder::new(app)
                .item(&status_item)
                .separator()
                .item(&open_dash)
                .item(&quick_add)
                .item(&open_latest)
                .item(&sync_now)
                .separator()
                .item(&notify_check)
                .item(&test_notify)
                .item(&autostart_check)
                .separator()
                .item(&check_updates)
                .item(&switch_srv)
                .item(&quit_item)
                .build()?;

            {
                let st = app.state::<AppState>();
                *st.tray.lock().unwrap() = Some(TrayHandles {
                    status_item,
                    notify_check: notify_check.clone(),
                    autostart_check: autostart_check.clone(),
                });
            }

            let mut tray_builder = TrayIconBuilder::with_id("main-tray")
                .menu(&tray_menu)
                .tooltip("Order Tracker")
                .show_menu_on_left_click(false)
                .on_menu_event(move |app_handle, event| match event.id().as_ref() {
                    "open_dash" => focus_and_navigate_main(app_handle, Some("/dashboard")),
                    "quick_add" => show_quick_add_window(app_handle),
                    "open_latest" => {
                        let st = app_handle.state::<AppState>();
                        let latest_id = st.data.lock().unwrap().last_updated_tracking_id.clone();
                        if let Some(tid) = latest_id {
                            focus_and_navigate_main(app_handle, Some(&format!("/tracking/{}", tid)));
                        } else {
                            focus_and_navigate_main(app_handle, Some("/dashboard"));
                        }
                    }
                    "sync_now" => {
                        app_handle.state::<AppState>().sync_wakeup.notify_one();
                    }
                    "toggle_notify" => {
                        let checked = notify_check.is_checked().unwrap_or(true);
                        let st = app_handle.state::<AppState>();
                        let snap = {
                            let mut g = st.data.lock().unwrap();
                            g.desktop_notify = checked;
                            g.clone()
                        };
                        st.save(&snap);
                    }
                    "test_notify" => {
                        let _ = send_test_desktop_notification(app_handle.clone());
                    }
                    "toggle_autostart" => {
                        let checked = autostart_check.is_checked().unwrap_or(false);
                        if checked {
                            let _ = app_handle.autolaunch().enable();
                        } else {
                            let _ = app_handle.autolaunch().disable();
                        }
                    }
                    "check_updates" => {
                        let handle = app_handle.clone();
                        tauri::async_runtime::spawn(async move {
                            match perform_update_check(&handle).await {
                                Ok(res) if res.update_available => {
                                    let title = format!("Có bản cập nhật mới v{}", res.latest_version);
                                    let body = format!(
                                        "Phiên bản hiện tại v{}. Đang mở liên kết tải bộ cài mới…",
                                        res.current_version
                                    );
                                    let _ = handle.notification().builder().title(&title).body(&body).show();
                                    if !res.download_url.is_empty() {
                                        let _ = handle.opener().open_url(&res.download_url, None::<&str>);
                                    } else {
                                        focus_and_navigate_main(&handle, Some("/download"));
                                    }
                                }
                                Ok(res) => {
                                    let body = format!("Bạn đang dùng phiên bản v{}.", res.current_version);
                                    let _ = handle
                                        .notification()
                                        .builder()
                                        .title("Order Tracker đã ở bản mới nhất")
                                        .body(&body)
                                        .show();
                                }
                                Err(err) => {
                                    let _ = handle
                                        .notification()
                                        .builder()
                                        .title("Không thể kiểm tra cập nhật")
                                        .body(&err)
                                        .show();
                                }
                            }
                        });
                    }
                    "switch_srv" => {
                        if let Some(win) = app_handle.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                            if let Ok(local_cfg) = "tauri://localhost/index.html?configure=1".parse() {
                                let _ = win.navigate(local_cfg);
                            }
                        }
                    }
                    "quit" => {
                        app_handle.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        focus_and_navigate_main(tray.app_handle(), None);
                    }
                });

            if let Some(default_icon) = app.default_window_icon() {
                tray_builder = tray_builder.icon(default_icon.clone());
            }
            let _ = tray_builder.build(app)?;

            // Background Tokio polling loop
            let bg_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let Ok(client) = reqwest::Client::builder()
                    .timeout(Duration::from_secs(15))
                    .user_agent("OrderTracker-Windows-Tauri/1.0")
                    .build()
                else {
                    return;
                };

                loop {
                    poll_once(&bg_handle, &client).await;
                    let st = bg_handle.state::<AppState>();
                    tokio::select! {
                        _ = tokio::time::sleep(Duration::from_secs(POLL_INTERVAL_SECS)) => {}
                        _ = st.sync_wakeup.notified() => {}
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() == "main" {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window.hide();

                    let app_handle = window.app_handle();
                    let st = app_handle.state::<AppState>();
                    let show_hint = {
                        let mut guard = st.data.lock().unwrap();
                        if !guard.close_hint_shown {
                            guard.close_hint_shown = true;
                            true
                        } else {
                            false
                        }
                    };
                    if show_hint {
                        let snap = st.data.lock().unwrap().clone();
                        st.save(&snap);
                        let _ = app_handle
                            .notification()
                            .builder()
                            .title("Order Tracker đang chạy ngầm")
                            .body("Ứng dụng đã thu gọn xuống khay hệ thống Windows để tiếp tục báo tin đơn hàng.")
                            .show();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_desktop_prefs,
            set_desktop_prefs,
            sync_desktop_auth,
            clear_desktop_auth,
            switch_server_url,
            trigger_sync_now,
            send_test_desktop_notification,
            check_for_updates,
            open_external_url,
            get_quick_add_context,
            close_quick_add,
            submit_quick_add,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Order Tracker desktop application");
}
