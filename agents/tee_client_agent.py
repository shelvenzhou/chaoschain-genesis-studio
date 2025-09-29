"""
TEE Client Agent

Simple client agent for testing TEE validation flow.
"""

import hashlib
import json
import os
import time
from typing import Dict, Any
from web3 import Web3

from .base_agent_genesis import GenesisBaseAgent

try:
    from dstack_sdk import DstackClient
    DSTACK_AVAILABLE = True
except ImportError:
    DSTACK_AVAILABLE = False


class TEEClientAgent(GenesisBaseAgent):
    """Simple client agent for TEE validation testing"""

    def __init__(self, agent_domain: str, wallet_address: str, wallet_manager=None):
        """Initialize TEE client agent"""
        super().__init__(agent_domain, wallet_address, wallet_manager)

        # dstack integration
        self.dstack_client = None
        if DSTACK_AVAILABLE:
            try:
                dstack_endpoint = os.getenv('DSTACK_SIMULATOR_ENDPOINT')
                self.dstack_client = DstackClient(endpoint=dstack_endpoint)
                if hasattr(self.dstack_client, 'is_reachable') and not self.dstack_client.is_reachable():
                    self.dstack_client = None
            except:
                self.dstack_client = None

        print(f"🤖 TEE Client Agent initialized")
        print(f"   Address: {self.address}")
        print(f"   dstack Available: {self.dstack_client is not None}")

    def generate_tee_quote(self) -> Dict[str, Any]:
        """Generate TEE quote using real dstack or mock data"""
        if self.dstack_client:
            try:
                return self._generate_real_tee_quote()
            except Exception as e:
                print(f"Warning: dstack failed ({e}), using mock")

        return self._generate_mock_tee_quote()

    def _generate_real_tee_quote(self) -> Dict[str, Any]:
        """Generate real TEE quote using dstack SDK"""
        report_data = f"chaoschain-client-{self.address}".encode()[:64]
        quote_response = self.dstack_client.get_quote(report_data)
        info_response = self.dstack_client.info()

        quote_data = {
            "dstack_quote": quote_response.quote,
            "tcb_info": {
                "app_id": info_response.app_id,
                "instance_id": info_response.instance_id,
                "device_id": info_response.device_id,
                "compose_hash": info_response.compose_hash,
                "os_image_hash": info_response.os_image_hash,
            },
            "rtmrs": quote_response.replay_rtmrs(),
            "quote_type": "real_dstack_tee",
            "timestamp": int(time.time())
        }

        print(f"✅ Generated real dstack TEE quote for client {self.address}")
        return quote_data

    def _generate_mock_tee_quote(self) -> Dict[str, Any]:
        """Generate mock TEE quote for development"""
        compose_hash = hashlib.sha256(
            f"client-{self.agent_domain}".encode()).digest()
        device_id = hashlib.sha256(
            f"device-{self.address}".encode()).digest()[:16]
        mr_data = hashlib.sha256(f"client-mr-{self.address}".encode()).digest()

        quote_data = {
            "measurement_register": mr_data.hex(),
            "device_id": device_id.hex(),
            "compose_hash": compose_hash.hex(),
            "timestamp": int(time.time()),
            "quote_type": "mock_tee_quote"
        }

        print(f"🔐 Generated mock TEE quote for client {self.address}")
        return quote_data

    def generate_work_report(self, task_type: str = "market_analysis") -> Dict[str, Any]:
        """Generate a work report to be validated"""
        return {
            "report_id": f"report_{int(time.time())}",
            "agent_address": self.address,
            "task_type": task_type,
            "timestamp": int(time.time()),
            "tee_quote": self.generate_tee_quote()
        }

    def request_validation(self, validator_agent_id: int, work_report: Dict[str, Any]) -> str:
        """Request validation from a validator agent"""
        report_json = json.dumps(work_report, sort_keys=True)
        data_hash = Web3.keccak(text=report_json).hex()

        print(f"📝 Requesting validation from agent {validator_agent_id}")
        print(f"   Report ID: {work_report['report_id']}")
        print(f"   Data Hash: {data_hash}")

        return super().request_validation(validator_agent_id, data_hash)
