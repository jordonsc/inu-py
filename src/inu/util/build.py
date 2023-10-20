import argparse
import glob
import json
import logging
import os
import tarfile
import tempfile
from os.path import dirname as up
import shutil

import aiofiles
import aiohttp

from mpremote import commands as mpremote
from mpremote.main import State

from inu.util import Utility


class MpArgs:
    verbose = False
    recursive = False

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class File:
    def __init__(self, abs_fn: str, short_fn: str, is_dir: bool):
        self.abs_fn = abs_fn
        self.short_fn = short_fn
        self.is_dir = is_dir


class Build(Utility):
    # Github repo details for the MicroPython library
    LIB_REPO = "micropython/micropython-lib"
    LIB_TAG = "v1.21.0"

    # Github archive structure
    GIT_PATH = "https://github.com/{lib}/archive/refs/tags/{tag}{ext}"

    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.logger = logging.getLogger('inu.util.build')
        self.root_dir = up(up(up(up(os.path.realpath(__file__)))))
        self.local_dir = None
        self.state = None

    async def run(self):
        """
        Run the device builder.
        """
        device_id = self.args.device_id[0].split(".")

        if not os.path.exists(f"{self.root_dir}/apps/{device_id[0]}"):
            self.logger.error(f"App files for '{device_id[0]}' do not exist")
            exit(1)

        cfg = self.create_config_file(device_id)
        self.logger.info(f"Generated configuration:\n{cfg}")

        port = self.args.port
        self.state = State()
        await self.get_libs(self.LIB_TAG)

        if self.args.local:
            self.local_dir = self.root_dir + f"/build/apps/{'.'.join(device_id)}/"
            if os.path.exists(self.local_dir):
                shutil.rmtree(self.local_dir)
            os.makedirs(self.local_dir, exist_ok=True)

        self.logger.info(f"Building {device_id}..")

        if self.local_dir:
            self.logger.info(f"Building to local directory: {self.local_dir}")
        else:
            self.logger.info(f"Connecting to device on {port}..")
            mpremote.do_connect(self.state, MpArgs(device=[port]))

        self.logger.info("Sending content..")

        # Core app
        self.send_files(f"apps/{device_id[0]}")
        with tempfile.NamedTemporaryFile('w') as fp:
            fp.write(cfg)
            fp.seek(0)
            self.send_file(fp.name, "settings.json")

        self.send_files("src/inu", "inu")
        self.send_files("src/micro_nats", "micro_nats")
        self.send_files("src/wifi", "wifi")

        # MicroPython libs
        self.mkdir("lib")
        mc = self.get_lib_root(short_form=True)
        self.send_file(f"{mc}/python-stdlib/base64/base64.py", "lib/base64.py")
        self.send_file(f"{mc}/python-stdlib/datetime/datetime.py", "lib/datetime.py")
        self.send_file(f"{mc}/python-stdlib/logging/logging.py", "lib/logging.py")

        if not self.local_dir:
            self.logger.debug("Disconnecting..")
            mpremote.do_disconnect(self.state, MpArgs())

        self.logger.info("Done")

    def create_config_file(self, device_id) -> str:
        """
        Merges all base & device config files into one and returns them as a string (containing valid JSON).
        """
        dvc_id_str = '.'.join(device_id)
        files = [
            f"{self.root_dir}/config/base.json",
            f"{self.root_dir}/config/{device_id[0]}.json",
        ]

        fn = device_id[0]
        for part in device_id[1:]:
            fn += f".{part}"
            files.append(f"{self.root_dir}/config/{fn}.json")

        def merge(source, destination):
            for key, value in source.items():
                if isinstance(value, dict):
                    # get node or create one
                    node = destination.setdefault(key, {})
                    merge(value, node)
                else:
                    destination[key] = value

            return destination

        out = {'device_id': dvc_id_str, 'hostname': '_'.join(device_id)}
        for file in files:
            if os.path.exists(file):
                self.logger.info(f"Loading device info from {file}")
                try:
                    with open(file, 'r') as fp:
                        merge(json.load(fp), out)
                except Exception as e:
                    self.logger.error(f"ERROR loading config: {type(e).__name__}: {e}")

        return json.dumps(out, indent=4)

    def has_lib_files(self) -> bool:
        """
        Checks if we have a copy of the MicroPython libraries downloaded.
        """
        return os.path.exists(self.get_lib_root())

    def get_lib_root(self, short_form: bool = False) -> str:
        """
        Returns the path to where the MicroPython libraries should be.
        """
        prefix = "build/" if short_form else f"{self.root_dir}/build/"
        return f"{prefix}{self.LIB_REPO.split('/')[1]}-{self.LIB_TAG[1:]}"

    def get_files(self, path) -> list[File]:
        """
        Get a list of files in a given local directory.
        """
        files = []
        base_len = len(self.root_dir + f'/{path}/')
        listing = glob.glob(self.root_dir + f'/{path}/**/*', recursive=True)
        for line in listing:
            if "__pycache__" in line[base_len:]:
                continue
            files.append(File(abs_fn=line, short_fn=line[base_len:], is_dir=os.path.isdir(line)))

        return files

    def mkdir(self, path: str) -> bool:
        """
        Create a directory on a device connected via serial.
        """
        self.logger.debug(f"mkdir {path}")

        if self.local_dir:
            os.makedirs(self.local_dir + path, exist_ok=True)
            return True

        try:
            self.state.ensure_raw_repl()
            self.state.did_action()
            self.state.transport.fs_mkdir(path)
            return True
        except mpremote.TransportError as e:
            if "[Errno 17] EEXIST" in str(e):
                return False
            else:
                raise e

    def mkdir_path(self, path: str):
        """
        Create a directory structure on target filesystem.
        """
        base_paths = path.split("/")
        base = ""
        for p in base_paths:
            if base:
                base += f"/{p}"
            else:
                base = p

            self.mkdir(f"{base}")

    def send_files(self, src: str, dest: str = None):
        """
        Send files in a local directory to the target directory.

        Will automatically create required directory structure.
        """
        if dest is None:
            dest = ""
        else:
            self.mkdir_path(dest)
            dest += "/"

        files = self.get_files(src)
        for file in files:
            tgt = f"{dest}{file.short_fn}"
            if file.is_dir:
                self.mkdir(tgt)
            else:
                self.logger.debug(f"cp {tgt}")

                if self.local_dir:
                    shutil.copy(file.abs_fn, self.local_dir + tgt)
                else:
                    mpremote.do_filesystem(self.state, MpArgs(command=["cp"], path=[file.abs_fn, f":{tgt}"]))

    def send_file(self, src: str, dest: str):
        """
        Send a single file to a remote device connected via serial.

        `dest` should be a file, and the base directory must already exist.
        """
        if src[0] != "/":
            src = f"{self.root_dir}/{src}"

        self.logger.debug(f"cp {dest}")
        if self.local_dir:
            shutil.copy(src, self.local_dir + dest)
        else:
            mpremote.do_filesystem(self.state, MpArgs(command=["cp"], path=[src, f":{dest}"]))

    async def get_libs(self, tag: str, ext: str = ".tar.gz"):
        """
        Grabs a given release archive from Github and extracts it to the build directory. Does nothing if required
        files already exist.
        """
        url = self.GIT_PATH.format(lib=self.LIB_REPO, tag=tag, ext=ext)
        local_fn = f"{self.LIB_REPO.replace('/', '_')}-{tag}{ext}"
        local_path = f"{self.root_dir}/build/{local_fn}"

        if not os.path.exists(local_path):
            # Download release archive from Github
            self.logger.info(f"Downloading library archive {tag}..")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    self.logger.debug(f"GET {url}: {response.status}")

                    resp = await response.read()

            # Write to local filesystem
            self.logger.debug(f"Writing to {local_path}..")
            async with aiofiles.open(local_path, "wb") as out:
                await out.write(resp)
                await out.flush()

        # Extract tarball
        if not self.has_lib_files():
            self.logger.debug(f"Extracting {local_fn}..")
            with tarfile.open(local_path, 'r') as tar:
                for item in tar:
                    tar.extract(item, f"{self.root_dir}/build/")
