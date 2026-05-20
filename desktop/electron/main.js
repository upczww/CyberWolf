const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

let mainWindow = null
let serverProcess = null
const SERVER_PORT = 8765
const DEV_PORT = 5173

function startPythonServer() {
  const projectRoot = path.join(__dirname, '../../')
  serverProcess = spawn('uv', ['run', 'uvicorn', 'server.api:app', '--port', String(SERVER_PORT), '--host', '0.0.0.0'], {
    cwd: projectRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  serverProcess.stdout.on('data', (data) => console.log(`[server] ${data}`))
  serverProcess.stderr.on('data', (data) => console.log(`[server] ${data}`))
  serverProcess.on('close', (code) => console.log(`[server] exited with code ${code}`))
}

function waitForServer(url, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now()
    const check = () => {
      http.get(url, (res) => {
        if (res.statusCode === 200) resolve()
        else setTimeout(check, 200)
      }).on('error', () => {
        if (Date.now() - start > timeout) reject(new Error('Server timeout'))
        else setTimeout(check, 200)
      })
    }
    check()
  })
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'LycanTUI - AI 狼人杀',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  // In dev mode, load Vite dev server; in production, load built files
  const isDev = !app.isPackaged
  if (isDev) {
    mainWindow.loadURL(`http://127.0.0.1:${DEV_PORT}`)
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => { mainWindow = null })
}

app.on('ready', async () => {
  startPythonServer()
  try {
    await waitForServer(`http://localhost:${SERVER_PORT}/health`)
    console.log('[electron] Server is ready')
  } catch (e) {
    console.error('[electron] Server failed to start:', e)
  }
  createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('quit', () => {
  if (serverProcess) {
    serverProcess.kill()
    serverProcess = null
  }
})
