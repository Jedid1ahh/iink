"""Install exactly the toolchain declared by the repository during image creation."""
import subprocess
import sys
import tomllib
from pathlib import Path


def main():
    toolchain = tomllib.loads(Path(sys.argv[1]).read_text())["toolchain"]
    channel = toolchain["channel"]
    command = ["rustup", "toolchain", "install", channel,
               "--profile", toolchain.get("profile", "minimal")]
    for component in toolchain.get("components", []):
        command.extend(["--component", component])
    for target in toolchain.get("targets", []):
        command.extend(["--target", target])
    subprocess.run(command, check=True)
    subprocess.run(["rustup", "default", channel], check=True)


if __name__ == "__main__":
    main()
