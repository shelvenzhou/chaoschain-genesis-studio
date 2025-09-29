#!/bin/bash
set -e

echo "🔨 Building dcap-qvl for cryptographic quote verification..."

# Check if we're in the right directory
if [ ! -f "agents/validator_proof_service.py" ]; then
    echo "❌ Run from project root directory"
    exit 1
fi

# Check if dcap-qvl source exists
if [ ! -d "external/dcap-qvl" ]; then
    echo "❌ dcap-qvl source not found in external/dcap-qvl"
    exit 1
fi

cd external/dcap-qvl

# Install Rust if not available
if ! command -v cargo &> /dev/null; then
    echo "📦 Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source ~/.cargo/env
fi

echo "🔧 Building dcap-qvl library..."
cargo build --release

echo "🔧 Building dcap-qvl CLI tool..."
cd cli
cargo build --release

# Check if CLI build was successful
if [ -f "target/release/dcap-qvl" ]; then
    echo "✅ dcap-qvl CLI built successfully!"
    echo "📍 Binary location: $(pwd)/target/release/dcap-qvl"

    # Test the binary
    echo "🧪 Testing dcap-qvl CLI..."
    ./target/release/dcap-qvl --help || echo "⚠️ CLI test failed, but binary exists"
else
    echo "❌ Build failed - dcap-qvl binary not found"
    exit 1
fi

echo "🎉 dcap-qvl is ready for cryptographic quote verification!"