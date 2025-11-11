#!/usr/bin/env node

/**
 * Auralis Build Script
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive build system that:
 * 1. Builds React frontend (production build)
 * 2. Bundles Python backend with PyInstaller
 * 3. Prepares everything for Electron packaging
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class BuildManager {
  constructor() {
    this.rootDir = path.join(__dirname, '..');
    this.frontendDir = path.join(this.rootDir, 'auralis-web', 'frontend');
    this.backendDir = path.join(this.rootDir, 'auralis-web', 'backend');
    this.desktopDir = path.join(this.rootDir, 'desktop');
    this.distDir = path.join(this.rootDir, 'dist');

    this.frontendBuildDir = path.join(this.frontendDir, 'build');
    this.backendDistDir = path.join(this.backendDir, 'dist');
  }

  log(category, message) {
    const timestamp = new Date().toLocaleTimeString();
    console.log(`[${timestamp}] [${category}] ${message}`);
  }

  async runCommand(cmd, args, cwd, description) {
    return new Promise((resolve, reject) => {
      this.log('BUILD', `${description}...`);

      const process = spawn(cmd, args, {
        cwd: cwd || this.rootDir,
        stdio: 'inherit',
        shell: true
      });

      process.on('close', (code) => {
        if (code === 0) {
          this.log('BUILD', `✓ ${description} complete`);
          resolve();
        } else {
          this.log('BUILD', `✗ ${description} failed with code ${code}`);
          reject(new Error(`${description} failed`));
        }
      });

      process.on('error', (error) => {
        this.log('BUILD', `✗ ${description} error: ${error.message}`);
        reject(error);
      });
    });
  }

  async checkRequirements() {
    this.log('BUILD', '🔍 Checking requirements...');

    // Check Node.js
    try {
      await this.runCommand('node', ['--version'], this.rootDir, 'Node.js version check');
    } catch (error) {
      throw new Error('Node.js not found. Please install Node.js 16+');
    }

    // Check Python
    try {
      await this.runCommand('python', ['--version'], this.rootDir, 'Python version check');
    } catch (error) {
      throw new Error('Python not found. Please install Python 3.8+');
    }

    // Check PyInstaller
    try {
      await this.runCommand('pyinstaller', ['--version'], this.rootDir, 'PyInstaller version check');
    } catch (error) {
      this.log('BUILD', '⚠️  PyInstaller not found, installing...');
      await this.runCommand('pip', ['install', 'pyinstaller'], this.rootDir, 'Installing PyInstaller');
    }

    this.log('BUILD', '✓ All requirements met');
  }

  async cleanDist() {
    this.log('BUILD', '🧹 Cleaning previous builds...');

    const dirsToClean = [
      this.frontendBuildDir,
      this.backendDistDir,
      path.join(this.backendDir, 'build'),
      path.join(this.backendDir, '*.spec'),
      this.distDir
    ];

    for (const dir of dirsToClean) {
      if (fs.existsSync(dir)) {
        if (dir.includes('*')) {
          // Handle glob patterns for spec files
          const dirPath = path.dirname(dir);
          const pattern = path.basename(dir);
          if (fs.existsSync(dirPath)) {
            const files = fs.readdirSync(dirPath);
            files.forEach(file => {
              if (file.endsWith('.spec')) {
                fs.unlinkSync(path.join(dirPath, file));
              }
            });
          }
        } else {
          fs.rmSync(dir, { recursive: true, force: true });
        }
        this.log('BUILD', `  Removed ${path.basename(dir)}`);
      }
    }

    this.log('BUILD', '✓ Clean complete');
  }

  async buildFrontend() {
    this.log('BUILD', '⚛️  Building React frontend...');

    // Check if frontend directory exists
    if (!fs.existsSync(this.frontendDir)) {
      this.log('BUILD', '⚠️  Frontend directory not found, skipping');
      return;
    }

    // Install dependencies if needed
    if (!fs.existsSync(path.join(this.frontendDir, 'node_modules'))) {
      await this.runCommand('npm', ['install'], this.frontendDir, 'Installing frontend dependencies');
    }

    // Build frontend
    await this.runCommand('npm', ['run', 'build'], this.frontendDir, 'Building frontend');

    // Verify build
    if (!fs.existsSync(this.frontendBuildDir)) {
      throw new Error('Frontend build failed - build directory not created');
    }

    this.log('BUILD', '✓ Frontend built successfully');
  }

  async buildBackend() {
    this.log('BUILD', '🐍 Bundling Python backend with PyInstaller...');

    // Create PyInstaller spec if it doesn't exist
    const specPath = path.join(this.backendDir, 'auralis-backend.spec');
    if (!fs.existsSync(specPath)) {
      this.log('BUILD', 'Creating PyInstaller spec file...');
      await this.createPyInstallerSpec();
    }

    // Run PyInstaller
    await this.runCommand(
      'pyinstaller',
      [
        '--clean',
        '--noconfirm',
        'auralis-backend.spec'
      ],
      this.backendDir,
      'Bundling backend with PyInstaller'
    );

    // Verify build
    if (!fs.existsSync(this.backendDistDir)) {
      throw new Error('Backend build failed - dist directory not created');
    }

    this.log('BUILD', '✓ Backend bundled successfully');
  }

  async createPyInstallerSpec() {
    const specContent = `# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller Spec for Auralis Backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bundles the FastAPI backend with all dependencies into a standalone executable.
"""

block_cipher = None

# Collect all auralis module files
from PyInstaller.utils.hooks import collect_all, collect_data_files

auralis_imports = collect_all('auralis')
fastapi_imports = collect_all('fastapi')
uvicorn_imports = collect_all('uvicorn')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include any data files needed by the backend
        ('*.py', '.'),
    ] + auralis_imports[0] + fastapi_imports[0] + uvicorn_imports[0],
    hiddenimports=[
        'auralis',
        'auralis.core',
        'auralis.core.hybrid_processor',
        'auralis.core.unified_config',
        'auralis.dsp',
        'auralis.io',
        'auralis.io.unified_loader',
        'auralis.io.saver',
        'auralis.analysis',
        'auralis.learning',
        'auralis.optimization',
        'auralis.library',
        'auralis.player',
        'fastapi',
        'uvicorn',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'pydantic',
        'sqlalchemy',
        'numpy',
        'scipy',
        'soundfile',
        'resampy',
        'processing_engine',
        'processing_api',
    ] + auralis_imports[1] + fastapi_imports[1] + uvicorn_imports[1],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='auralis-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='auralis-backend',
)
`;

    const specPath = path.join(this.backendDir, 'auralis-backend.spec');
    fs.writeFileSync(specPath, specContent);
    this.log('BUILD', '✓ PyInstaller spec created');
  }

  async prepareElectronResources() {
    this.log('BUILD', '📦 Preparing Electron resources...');

    // Ensure directories exist
    const resourcesDir = path.join(this.desktopDir, 'resources');
    fs.mkdirSync(resourcesDir, { recursive: true });

    // Copy frontend build if it exists
    if (fs.existsSync(this.frontendBuildDir)) {
      const frontendResourceDir = path.join(resourcesDir, 'frontend');
      if (fs.existsSync(frontendResourceDir)) {
        fs.rmSync(frontendResourceDir, { recursive: true, force: true });
      }
      this.copyRecursive(this.frontendBuildDir, frontendResourceDir);
      this.log('BUILD', '  ✓ Frontend resources copied');
    }

    // Copy backend build if it exists
    if (fs.existsSync(this.backendDistDir)) {
      const backendResourceDir = path.join(resourcesDir, 'backend');
      if (fs.existsSync(backendResourceDir)) {
        fs.rmSync(backendResourceDir, { recursive: true, force: true });
      }
      this.copyRecursive(this.backendDistDir, backendResourceDir);
      this.log('BUILD', '  ✓ Backend resources copied');
    }

    this.log('BUILD', '✓ Electron resources prepared');
  }

  copyRecursive(src, dest) {
    const stats = fs.statSync(src);

    if (stats.isDirectory()) {
      fs.mkdirSync(dest, { recursive: true });
      const files = fs.readdirSync(src);

      files.forEach(file => {
        const srcPath = path.join(src, file);
        const destPath = path.join(dest, file);
        this.copyRecursive(srcPath, destPath);
      });
    } else {
      fs.copyFileSync(src, dest);
    }
  }

  async build() {
    try {
      this.log('BUILD', '🚀 Starting Auralis build process...');
      this.log('BUILD', '');

      // Step 1: Check requirements
      await this.checkRequirements();
      console.log('');

      // Step 2: Clean previous builds
      await this.cleanDist();
      console.log('');

      // Step 3: Build frontend
      await this.buildFrontend();
      console.log('');

      // Step 4: Build backend
      await this.buildBackend();
      console.log('');

      // Step 5: Prepare Electron resources
      await this.prepareElectronResources();
      console.log('');

      this.log('BUILD', '✅ Build complete!');
      this.log('BUILD', '');
      this.log('BUILD', 'Next steps:');
      this.log('BUILD', '  1. Run "npm run package" to create distributable app');
      this.log('BUILD', '  2. Or run "npm run package:win/mac/linux" for specific platform');
      console.log('');

    } catch (error) {
      this.log('BUILD', `❌ Build failed: ${error.message}`);
      process.exit(1);
    }
  }
}

// Run build if executed directly
if (require.main === module) {
  const buildManager = new BuildManager();
  buildManager.build();
}

module.exports = BuildManager;