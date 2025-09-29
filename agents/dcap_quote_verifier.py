"""
DCAP Quote Verifier

Python wrapper for dcap-qvl CLI tool to provide cryptographic quote verification.
Uses Intel DCAP-QVL for production-grade TEE attestation verification.
"""

import subprocess
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional


class DcapQuoteVerifier:
    """Python wrapper for dcap-qvl CLI providing cryptographic quote verification"""

    def __init__(self):
        """Initialize the DCAP quote verifier"""
        # Path to dcap-qvl CLI binary
        self.dcap_cli_path = Path(__file__).parent.parent / "external" / \
            "dcap-qvl" / "cli" / "target" / "release" / "dcap-qvl"
        self.available = self.dcap_cli_path.exists()

        if self.available:
            print(f"✅ DCAP-QVL CLI available at: {self.dcap_cli_path}")
        else:
            print(f"❌ DCAP-QVL CLI not found at: {self.dcap_cli_path}")
            print("   Run: ./scripts/build_dcap.sh to build it")

    def is_available(self) -> bool:
        """Check if dcap-qvl CLI is available"""
        return self.available

    def verify_quote_hex(self, quote_hex: str) -> Dict[str, Any]:
        """
        Cryptographically verify a TEE quote in hexadecimal format

        Args:
            quote_hex: Hexadecimal representation of the TEE quote

        Returns:
            Dict containing verification result with keys:
            - verified: bool - Whether verification succeeded
            - status: str - Verification status ("UpToDate", "OutOfDate", etc.)
            - advisory_ids: list - Security advisory IDs if any
            - error: str - Error message if verification failed
        """
        if not self.available:
            return {
                "verified": False,
                "error": "DCAP-QVL CLI not available - run ./scripts/build_dcap.sh"
            }

        # Write quote to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.hex', delete=False) as f:
            f.write(quote_hex)
            quote_file = f.name

        try:
            # Call dcap-qvl CLI for cryptographic verification
            cmd = [str(self.dcap_cli_path), "verify", "--hex", quote_file]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30  # 30 second timeout
            )

            # Parse verification result JSON
            try:
                verification_result = json.loads(result.stdout)

                return {
                    "verified": True,
                    "status": verification_result.get("status", "Unknown"),
                    "advisory_ids": verification_result.get("advisory_ids", []),
                    "report": verification_result.get("report", {}),
                    "raw_output": result.stdout
                }

            except json.JSONDecodeError as e:
                return {
                    "verified": False,
                    "error": f"Failed to parse verification result: {e}",
                    "raw_stdout": result.stdout,
                    "raw_stderr": result.stderr
                }

        except subprocess.CalledProcessError as e:
            # Include detailed error information for debugging
            error_msg = f"DCAP verification failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f"\nSTDERR: {e.stderr.strip()}"
            if e.stdout:
                error_msg += f"\nSTDOUT: {e.stdout.strip()}"

            return {
                "verified": False,
                "error": error_msg,
                "stdout": e.stdout,
                "stderr": e.stderr,
                "returncode": e.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "verified": False,
                "error": "DCAP verification timed out after 30 seconds"
            }

        except Exception as e:
            return {
                "verified": False,
                "error": f"Unexpected error during verification: {e}"
            }

        finally:
            # Cleanup temporary file
            try:
                os.unlink(quote_file)
            except:
                pass  # Ignore cleanup errors

    def decode_quote_hex(self, quote_hex: str) -> Dict[str, Any]:
        """
        Decode a TEE quote to extract information without verification

        Args:
            quote_hex: Hexadecimal representation of the TEE quote

        Returns:
            Dict containing decoded quote information
        """
        if not self.available:
            return {
                "success": False,
                "error": "DCAP-QVL CLI not available"
            }

        # Write quote to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.hex', delete=False) as f:
            f.write(quote_hex)
            quote_file = f.name

        try:
            # Call dcap-qvl CLI for decoding
            cmd = [str(self.dcap_cli_path), "decode", "--hex", quote_file]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=15
            )

            # Parse decoded result
            try:
                decoded_result = json.loads(result.stdout)
                return {
                    "success": True,
                    "data": decoded_result,
                    "raw_output": result.stdout
                }

            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Failed to parse decoded result: {e}",
                    "raw_stdout": result.stdout
                }

        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"DCAP decode failed: {e}",
                "stdout": e.stdout,
                "stderr": e.stderr
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "DCAP decode timed out"
            }

        finally:
            # Cleanup
            try:
                os.unlink(quote_file)
            except:
                pass

    def verify_quote_binary(self, quote_bytes: bytes) -> Dict[str, Any]:
        """
        Verify a TEE quote from binary data

        Args:
            quote_bytes: Binary representation of the TEE quote

        Returns:
            Dict containing verification result
        """
        # Convert to hex and verify
        quote_hex = quote_bytes.hex()
        return self.verify_quote_hex(quote_hex)


# Global instance for easy importing
dcap_verifier = DcapQuoteVerifier()
