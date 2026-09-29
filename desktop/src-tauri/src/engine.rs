//! The FALCON engine as a child process of the desktop app.
//!
//! The app picks a free loopback port, starts the engine with its data folder
//! and console bundle, and polls the API until it answers. The engine follows
//! this process (`FALCON_PARENT_PID`) and shuts itself down when the app exits,
//! so nothing is left running in the background.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// Starting includes applying database migrations on first run.
const READY_TIMEOUT: Duration = Duration::from_secs(90);
const PORT_ATTEMPTS: usize = 3;
/// The engine exits with 3 when its port was taken between choosing and binding it.
const EXIT_PORT_IN_USE: i32 = 3;

#[derive(Clone, Serialize)]
pub struct Status {
    pub state: &'static str,
    pub message: String,
    pub version: String,
}

pub struct Engine {
    child: Mutex<Option<Child>>,
    status: Mutex<Status>,
}

impl Engine {
    pub fn new(version: String) -> Self {
        Self {
            child: Mutex::new(None),
            status: Mutex::new(Status { state: "starting", message: "Starting the discovery engine…".into(), version }),
        }
    }

    pub fn status(&self) -> Status {
        self.status.lock().unwrap().clone()
    }

    fn set_status(&self, app: &AppHandle, state: &'static str, message: impl Into<String>) {
        let status = {
            let mut current = self.status.lock().unwrap();
            current.state = state;
            current.message = message.into();
            current.clone()
        };
        let _ = app.emit("engine-status", status);
    }

    /// Ends the engine immediately (used when start-up failed or is retried).
    pub fn stop(&self) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Starts the engine on a background thread and opens the console when it is ready.
pub fn launch(app: AppHandle) {
    thread::spawn(move || {
        let engine = app.state::<Engine>();
        engine.set_status(&app, "starting", "Starting the discovery engine…");
        match start(&app, &engine) {
            Ok(url) => {
                engine.set_status(&app, "ready", "Opening FALCON…");
                if let Err(err) = crate::open_console(&app, &url) {
                    engine.set_status(&app, "failed", format!("The FALCON window could not be opened: {err}"));
                }
            }
            Err(message) => {
                engine.stop();
                engine.set_status(&app, "failed", message);
                if let Some(splash) = app.get_webview_window("splash") {
                    let _ = splash.show();
                }
            }
        }
    });
}

fn start(app: &AppHandle, engine: &Engine) -> Result<String, String> {
    let data_dir = data_dir(app)?;
    std::fs::create_dir_all(&data_dir).map_err(|err| format!("FALCON cannot create its data folder {}: {err}", data_dir.display()))?;
    let (mut command, console_dist) = engine_command(app)?;

    for attempt in 1..=PORT_ATTEMPTS {
        let port = free_port().map_err(|err| format!("No local port is available for the engine: {err}"))?;
        command
            .env("FALCON_DESKTOP", "1")
            .env("FALCON_ENVIRONMENT", "production")
            .env("FALCON_SECURE_COOKIES", "false")
            .env("FALCON_HOST", "127.0.0.1")
            .env("FALCON_PORT", port.to_string())
            .env("FALCON_DATA_DIR", &data_dir)
            .env("FALCON_CONSOLE_DIST", &console_dist)
            .env("FALCON_PARENT_PID", std::process::id().to_string())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: the engine has no console of its own

        let child = command.spawn().map_err(|err| format!("The discovery engine could not be started: {err}"))?;
        *engine.child.lock().unwrap() = Some(child);

        match wait_until_ready(engine, port) {
            Ok(()) => return Ok(format!("http://127.0.0.1:{port}/")),
            Err(Some(EXIT_PORT_IN_USE)) if attempt < PORT_ATTEMPTS => continue,
            Err(code) => {
                let log = data_dir.join("logs").join("engine.log");
                let detail = match code {
                    Some(code) => format!("The discovery engine stopped during start-up (exit code {code})."),
                    None => "The discovery engine did not become ready in time.".to_string(),
                };
                return Err(format!("{detail} Details are in {}.", log.display()));
            }
        }
    }
    unreachable!("the last attempt always returns")
}

/// Ok when the API answers; Err(exit code) if the engine exited, Err(None) on timeout.
fn wait_until_ready(engine: &Engine, port: u16) -> Result<(), Option<i32>> {
    let deadline = Instant::now() + READY_TIMEOUT;
    while Instant::now() < deadline {
        if let Some(child) = engine.child.lock().unwrap().as_mut() {
            if let Ok(Some(status)) = child.try_wait() {
                return Err(Some(status.code().unwrap_or(-1)));
            }
        }
        if api_answers(port) {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(150));
    }
    Err(None)
}

/// A plain HTTP request to an unauthenticated endpoint: 200 means the engine is serving.
fn api_answers(port: u16) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(300)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(3)));
    let request = b"GET /api/v1/setup HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: application/json\r\nConnection: close\r\n\r\n";
    if stream.write_all(request).is_err() {
        return false;
    }
    let mut head = [0u8; 12];
    matches!(stream.read(&mut head), Ok(n) if n >= 12 && &head[..12] == b"HTTP/1.1 200")
}

fn free_port() -> std::io::Result<u16> {
    Ok(TcpListener::bind(("127.0.0.1", 0))?.local_addr()?.port())
}

pub fn data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    app.path().app_data_dir().map_err(|err| format!("FALCON cannot locate its data folder: {err}"))
}

/// The bundled engine in an installed app; the repository's Python environment in development.
fn engine_command(app: &AppHandle) -> Result<(Command, PathBuf), String> {
    if let Ok(resources) = app.path().resource_dir() {
        let engine_dir = resources.join("engine");
        let executable = engine_dir.join(if cfg!(windows) { "falcon-engine.exe" } else { "falcon-engine" });
        if executable.exists() {
            let mut command = Command::new(&executable);
            command.arg("desktop").current_dir(&engine_dir);
            return Ok((command, resources.join("console")));
        }
    }
    if cfg!(debug_assertions) {
        let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
        let server = repo.join("server");
        let python = if cfg!(windows) { server.join(".venv").join("Scripts").join("python.exe") } else { server.join(".venv").join("bin").join("python") };
        if python.exists() {
            let mut command = Command::new(python);
            command.args(["-m", "falcon", "desktop"]).current_dir(&server);
            return Ok((command, repo.join("console").join("dist")));
        }
    }
    Err("The FALCON engine is missing from this installation. Please reinstall FALCON.".into())
}
