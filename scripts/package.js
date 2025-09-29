#!/usr/bin/env node

/**
 * Auralis Packaging Script
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Creates distributable Electron packages for Windows, macOS, and Linux.
 * Includes both frontend and backend in a single standalone application.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class PackageManager {
  constructor() {
    this.rootDir = path.join(__dirname, '..');
    this.desktopDir = path.join(this.rootDir, 'desktop');
    this.platform = process.argv[2] || 'all'; // win, mac, linux, or all
  }

  log(category, message) {
    const timestamp = new Date().toLocaleTimeString();
    console.log(`[${timestamp}] [${category}] ${message}`);
  }

  async runCommand(cmd, args, cwd, description) {
    return new Promise((resolve, reject) => {
      this.log('PACKAGE', `${description}...`);

      const process = spawn(cmd, args, {
        cwd: cwd || this.rootDir,
        stdio: 'inherit',
        shell: true
      });

      process.on('close', (code) => {
        if (code === 0) {
          this.log('PACKAGE', `✓ ${description} complete`);
          resolve();
        } else {
          this.log('PACKAGE', `✗ ${description} failed with code ${code}`);
          reject(new Error(`${description} failed`));
        }
      });

      process.on('error', (error) => {
        this.log('PACKAGE', `✗ ${description} error: ${error.message}`);
        reject(error);
      });
    });
  }

  async checkBuildExists() {
    this.log('PACKAGE', '🔍 Checking if build exists...');

    const frontendBuild = path.join(this.rootDir, 'auralis-web', 'frontend', 'build');
    const backendDist = path.join(this.rootDir, 'auralis-web', 'backend', 'dist');

    if (!fs.existsSync(frontendBuild) && !fs.existsSync(backendDist)) {
      this.log('PACKAGE', '⚠️  No build found. Running build first...');
      const BuildManager = require('./build.js');
      const buildManager = new BuildManager();
      await buildManager.build();
    } else {
      this.log('PACKAGE', '✓ Build exists');
    }
  }

  async installElectronDeps() {
    this.log('PACKAGE', '📦 Checking Electron dependencies...');

    const nodeModules = path.join(this.desktopDir, 'node_modules');
    if (!fs.existsSync(nodeModules)) {
      await this.runCommand('npm', ['install'], this.desktopDir, 'Installing Electron dependencies');
    } else {
      this.log('PACKAGE', '✓ Dependencies already installed');
    }
  }

  async packageApp() {
    this.log('PACKAGE', `📦 Packaging Auralis for ${this.platform}...`);

    const commands = {
      'win': ['run', 'build:win'],
      'mac': ['run', 'build:mac'],
      'linux': ['run', 'build:linux'],
      'all': ['run', 'build']
    };

    const command = commands[this.platform] || commands['all'];

    await this.runCommand(
      'npm',
      command,
      this.desktopDir,
      `Creating ${this.platform} package`
    );
  }

  async showResults() {
    const distDir = path.join(this.rootDir, 'dist');

    if (fs.existsSync(distDir)) {
      const files = fs.readdirSync(distDir);

      this.log('PACKAGE', '');
      this.log('PACKAGE', '✅ Packaging complete!');
      this.log('PACKAGE', '');
      this.log('PACKAGE', 'Distributable files created:');

      files.forEach(file => {
        const filePath = path.join(distDir, file);
        const stats = fs.statSync(filePath);
        const sizeMB = (stats.size / 1024 / 1024).toFixed(2);

        if (stats.isFile()) {
          this.log('PACKAGE', `  📦 ${file} (${sizeMB} MB)`);
        } else if (stats.isDirectory()) {
          this.log('PACKAGE', `  📁 ${file}/`);
        }
      });

      this.log('PACKAGE', '');
      this.log('PACKAGE', `Output directory: ${distDir}`);
      console.log('');
    }
  }

  async package() {
    try {
      this.log('PACKAGE', '🚀 Starting Auralis packaging process...');
      this.log('PACKAGE', `Platform: ${this.platform}`);
      this.log('PACKAGE', '');

      // Step 1: Check if build exists (and build if needed)
      await this.checkBuildExists();
      console.log('');

      // Step 2: Install Electron dependencies
      await this.installElectronDeps();
      console.log('');

      // Step 3: Package the app
      await this.packageApp();
      console.log('');

      // Step 4: Show results
      await this.showResults();

    } catch (error) {
      this.log('PACKAGE', `❌ Packaging failed: ${error.message}`);
      process.exit(1);
    }
  }
}

// Run packaging if executed directly
if (require.main === module) {
  const packageManager = new PackageManager();
  packageManager.package();
}

module.exports = PackageManager;