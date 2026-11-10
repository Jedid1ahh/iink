"""Offline checks for private-testnet key handling and finality verification.

These tests simulate the node CLI/RPC. They do not establish live consensus.
"""

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.request import urlopen


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
private = load("private_testnet", HERE / "private-testnet.py")
server_module = load("payment_server", HERE.parent / "apps/payments/serve.py")


class PrivateTestnetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.node = self.root / "iink-node"
        self.node.write_text("test executable")
        self.node.chmod(0o700)
        self.secrets = []
        self.console = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.console))
        self.enterContext(patch.object(private, "command", side_effect=self.cli))
        self.enterContext(patch.object(private, "host_id", return_value="codespace-a"))
        self.previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, self.previous_umask)

    def cli(self, node, *args):
        args = list(map(str, args))
        if args[:2] == ["key", "generate"]:
            seed = "0x" + os.urandom(32).hex()
            self.secrets.append(seed)
            return json.dumps({"secretSeed": seed, "publicKey": "0x" + hashlib.sha256(seed.encode()).hexdigest()})
        if args[:2] == ["key", "inspect"]:
            seed = Path(args[-1]).read_text()
            return json.dumps({"publicKey": "0x" + hashlib.sha256(seed.encode()).hexdigest()})
        if args[:2] == ["key", "generate-node-key"]:
            Path(args[-1]).write_text(os.urandom(32).hex())
            return ""
        if args[:2] == ["key", "inspect-node-key"]:
            number = int(Path(args[-1]).read_text(), 16) % 2
            return "12D3KooW" + ("A" if number else "B") * 44
        if args[0] == "build-spec":
            if "--raw" in args:
                spec = private.read_json(args[2])
                spec["genesis"] = {"raw": {"top": {"0x00": "0x01"}, "childrenDefault": {}}}
                return json.dumps(spec)
            return json.dumps({"properties": {"tokenSymbol": "IINK", "tokenDecimals": 18},
                               "genesis": {"runtimeGenesis": {"patch": {}}}})
        if args[:2] == ["key", "insert"]:
            self.assertEqual(Path(args[-1]).suffix, ".suri")
            return ""
        self.fail(f"Unexpected CLI command {args[:2]}")

    def prepared(self, role):
        root = self.root / role
        # Make network identities deterministically different for the test.
        root.mkdir(mode=0o700)
        (root / "network.key").write_text("01" if role == "a" else "02")
        with patch.object(private, "host_id", return_value=f"codespace-{role}"):
            private.prepare(argparse.Namespace(role=role, root=str(root), node=str(self.node)))
        return root

    def created(self):
        a, b = self.prepared("a"), self.prepared("b")
        output = self.root / "public-network"
        private.create(argparse.Namespace(node=str(self.node), a=a / "public.json", b=b / "public.json",
                       output=output, wallet=["0x" + "11" * 20, "0x" + "22" * 20]))
        return output, a, b

    def test_prepare_retains_secrets_and_never_prints_them(self):
        root = self.prepared("a")
        original = (root / "public.json").read_bytes()
        private.prepare(argparse.Namespace(role="a", root=str(root), node=str(self.node)))
        self.assertEqual(original, (root / "public.json").read_bytes())
        self.assertEqual(len(self.secrets), 2)
        for name in ("aura.suri", "grandpa.suri", "network.key"):
            self.assertEqual(stat.S_IMODE((root / name).stat().st_mode), 0o600)
        for secret in self.secrets:
            self.assertNotIn(secret, self.console.getvalue())
            self.assertNotIn(secret, original.decode())

    def test_prepare_rejects_damaged_key_without_replacing_it(self):
        root = self.prepared("a")
        (root / "aura.suri").write_text("damaged")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            private.prepare(argparse.Namespace(role="a", root=str(root), node=str(self.node)))
        self.assertEqual((root / "aura.suri").read_text(), "damaged")

    def test_genesis_has_only_selected_wallets_and_fresh_authorities(self):
        output, a, b = self.created()
        spec = private.read_json(output / "plain-spec.json")
        genesis = spec["genesis"]["runtimeGenesis"]["patch"]
        self.assertEqual(spec["id"], "iink_private_31343")
        self.assertEqual(spec["bootNodes"], [])
        self.assertEqual(genesis["sudo"], {"key": None})
        self.assertEqual(genesis["evmChainId"]["chainId"], 31343)
        self.assertEqual(genesis["aura"]["authorities"], [private.read_json(root / "public.json")["aura"] for root in (a, b)])
        self.assertEqual(len(genesis["balances"]["balances"]), 2)
        self.assertTrue(all(balance == 1000 * 10**18 for _, balance in genesis["balances"]["balances"]))
        wallet_account = "0x" + hashlib.blake2b(b"evm:" + bytes.fromhex("11" * 20), digest_size=32).hexdigest()
        self.assertEqual(genesis["balances"]["balances"][0][0], wallet_account)
        private.network_file(output / "network.json")

    def test_refuses_same_host_or_binary_mismatch(self):
        output, _, _ = self.created()
        identities = private.read_json(output / "network.json")["validators"]
        identities[1]["host"] = identities[0]["host"]
        with self.assertRaisesRegex(RuntimeError, "same host"):
            private.validate_pair(identities)
        identities[1]["host"] = "other-host"
        identities[1]["binarySha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "same binary"):
            private.validate_pair(identities)

    def test_tampered_spec_is_rejected(self):
        output, _, _ = self.created()
        with (output / "chain-spec.json").open("a") as stream:
            stream.write(" ")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            private.network_file(output / "network.json")

    def test_failed_cli_does_not_disclose_stderr(self):
        # Restore the real command wrapper for this test.
        real = load("real_private", HERE / "private-testnet.py")
        with patch.object(real.subprocess, "run", return_value=argparse.Namespace(returncode=1, stderr="secret seed", stdout="secret seed")):
            with self.assertRaises(RuntimeError) as error:
                real.command(self.node, "key", "generate")
        self.assertNotIn("secret seed", str(error.exception))

    def test_launcher_uses_private_ports_reserved_peers_and_persistent_state(self):
        output, a, _ = self.created()
        with patch.object(private.subprocess, "Popen") as popen:
            popen.return_value.__enter__.return_value.wait.return_value = 0
            private.run(argparse.Namespace(role="a", root=str(a), network=output / "network.json", node=str(self.node)))
        argv = popen.call_args.args[0]
        self.assertIn("--reserved-only", argv)
        self.assertIn("/ip4/127.0.0.1/tcp/30333", argv)
        self.assertIn(str(a / "data"), argv)
        self.assertEqual(argv[argv.index("--rpc-methods") + 1], "Safe")
        self.assertNotIn("--rpc-external", argv)
        self.assertNotIn("--alice", argv)
        self.assertTrue(all(secret not in " ".join(argv) for secret in self.secrets))

    def rpc_fixture(self, output):
        identities = private.read_json(output / "network.json")["validators"]

        def request(method, params=None, *, url):
            if method == "system_localPeerId":
                return identities[0 if url.endswith(":9944") else 1]["peerId"]
            if method == "system_health":
                return {"peers": 1}
            if method == "chain_getBlockHash":
                return "0x" + f"{params[0]:064x}"
            self.fail(f"Unexpected RPC {method}")
        return request

    def test_check_saves_history_and_rechecks_it_after_restart(self):
        output, _, _ = self.created()
        args = argparse.Namespace(network=output / "network.json", a_rpc="http://127.0.0.1:9944",
                                  b_rpc="http://127.0.0.1:9945", checkpoint=self.root / "checkpoint.json",
                                  timeout=5, transaction=None)
        with patch.object(private, "check_chain"), patch.object(private, "rpc", side_effect=self.rpc_fixture(output)), \
                patch.object(private, "finalized_height", side_effect=[10, 10, 11, 11, 11, 11, 12, 12]):
            private.check(args)
            self.assertEqual(private.read_json(args.checkpoint)["height"], 11)
            private.check(args)
            self.assertEqual(private.read_json(args.checkpoint)["height"], 12)
        self.assertIn("Saved finalized block 11 is intact", self.console.getvalue())

    def test_finalized_history_change_is_rejected(self):
        output, _, _ = self.created()
        args = argparse.Namespace(network=output / "network.json", a_rpc="http://127.0.0.1:9944",
                                  b_rpc="http://127.0.0.1:9945", checkpoint=self.root / "checkpoint.json",
                                  timeout=5, transaction=None)
        network = private.read_json(args.network)
        private.write_json(args.checkpoint, {"chainSpecSha256": network["chainSpecSha256"],
                          "genesisHash": "0x" + "0" * 64, "height": 9, "hash": "wrong-history"})
        with patch.object(private, "check_chain"), patch.object(private, "rpc", side_effect=self.rpc_fixture(output)), \
                patch.object(private, "finalized_height", return_value=10):
            with self.assertRaisesRegex(RuntimeError, "history changed"):
                private.check(args)

    def test_unfinalized_receipt_is_rejected(self):
        tx = "0x" + "a" * 64
        receipt = {"transactionHash": tx, "status": "0x1", "blockNumber": "0x20"}
        with patch.object(private, "rpc", return_value=receipt):
            with self.assertRaisesRegex(RuntimeError, "not finalized"):
                private.receipt_check(["a", "b"], tx, 31)

    def test_wrong_rpc_identity_is_rejected(self):
        output, _, _ = self.created()
        args = argparse.Namespace(network=output / "network.json", a_rpc="http://127.0.0.1:9944",
                                  b_rpc="http://127.0.0.1:9945", checkpoint=self.root / "checkpoint.json",
                                  timeout=5, transaction=None)
        with patch.object(private, "check_chain"), patch.object(private, "rpc", return_value="wrong-peer"):
            with self.assertRaisesRegex(RuntimeError, "wrong validator"):
                private.check(args)

    def test_disagreement_and_stalled_finality_are_rejected(self):
        with patch.object(private, "finalized_height", return_value=5), \
                patch.object(private, "rpc", side_effect=["hash-a", "hash-b"]):
            with self.assertRaisesRegex(RuntimeError, "disagree"):
                private.agreed(["a", "b"])
        output, _, _ = self.created()
        args = argparse.Namespace(network=output / "network.json", a_rpc="http://127.0.0.1:9944",
                                  b_rpc="http://127.0.0.1:9945", checkpoint=self.root / "checkpoint.json",
                                  timeout=0, transaction=None)
        with patch.object(private, "check_chain"), patch.object(private, "rpc", side_effect=self.rpc_fixture(output)), \
                patch.object(private, "finalized_height", return_value=10):
            with self.assertRaisesRegex(RuntimeError, "Finality did not advance"):
                private.check(args)
        self.assertFalse(args.checkpoint.exists())

    def test_app_server_selects_network_without_exposing_the_spec(self):
        output, _, _ = self.created()

        class QuietServer(server_module.PaymentServer):
            network = private.read_json(output / "network.json")

            def log_message(self, *_):
                pass

        handler = partial(QuietServer, directory=HERE.parent / "apps/payments")
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/network.mjs") as response:
                    module = response.read().decode()
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(response.headers["Content-Type"], "text/javascript")
                self.assertIn('"0x7a6f"', module)
                self.assertIn('"IINK Private Testnet"', module)
                self.assertIn(QuietServer.network["chainSpecSha256"], module)
                self.assertNotIn("validators", module)
            finally:
                server.shutdown()
                worker.join()


if __name__ == "__main__":
    unittest.main()
