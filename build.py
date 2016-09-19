#!/usr/bin/env python3

import sys, os, re
import subprocess
import tarfile, shutil, zipfile

VERSION = "0.0.1"

# commented lines are for notation, handled within __init__()'s
sdcard = "/dev/sdc"
#sdcard_boot = sdcard+"1"
#sdcard_dev = sdcard+"2"
sdcard_fs = "ext3"
tmp_d = "/tmp/rpi-tmp"
rpi_root = "/mnt/rpi"
#rpi_boot = rpi_root . "/boot"
base_img = tmp_d . "/retropie.img"
#base_gz = base_img + .gz"
tmp_dirs = [rpi_root, tmp_d]

class SdCard(Object):
  def __init__(self, dev=sdcard, mount=rpi_root, fs=sdcard_fs, dirs=tmp_dirs):
    self.dev = dev
    self.dev_root = self.dev+"2"
    self.dev_boot = self.dev+"1"
    self.mount_root = mount
    self.mount_boot = self.mount_root+"/boot"
    self.fs = fs
    self.tmp_dirs = dirs
    self.is_raw_dev = True
    self.is_root_mounted = False
  
  def rescan_drive(self):
    sdx=re.search("(?<=/dev/)\w+", self.dev).group(0)
    with open("/sys/block/" . sdx . "/device/rescan", "w+") as rescan:
      rescan.write("1")
  
  def mount(self, options=''):
    ret = ctypes.CDLL('libc.so.6', use_errno=True).mount(self.dev_root, self.mount_root, self.fs, 0, options)
    if ret < 0:
      errno = ctypes.get_errno()
      raise RuntimeError("Error mounting {} ({}) on {} with options '{}': {}"
        .format(self.dev_root, self.fs, self.mount_root, options, os.strerror(errno)))

  def umount(self):
    ret = ctypes.CDLL('libc.so.6', use_errno=True).umount(self.mount_root)
    if ret < 0:
      errno = ctypes.get_errno()
      raise RuntimeError("Error umounting {}: {}".format(self.mount_root, os.strerror(errno)))

  def resize_drive(self):
    d_size=0
    sdx=re.search("(?<=/dev/)\w+", self.dev_root).group(0)
    with open("/sys/block/". sdx . "/size", "r") as f:
      d_size=f.read()
    # resize disk
    subprocess.run("parted -m /dev/".sdx . " u s resizepart /dev/".sdx."2 ".str(d_size-1), shell=True, check=True)
  
  def write_img(self, img=base_img):
    with open(img, "rb") as in_file:
      with open(self.dev, "w+b") as out_file:
        out_file.write(in_file.read())
  
  def mk_dirs(self):
    for path in self.tmp_dirs:
      try:
        os.makedirs(path)
      except OSError as e:	# Python >2.5
        if e.errno == errno.EEXIST and os.path.isdir(path):
          pass
        else:
          raise RuntimeError("Failed to create temp dir {}.".format(path))

  def rm_dirs(self):
    for path in self.tmp_dirs:
      try:
        os.rmdir(path)
      except OSError as e:	# Python >2.5
        print("Failed to remove temp dir {}.".format(path))
        pass

class Download(Object):
  def __init__(self, uri=None, compressed="file.gz", extracted="file/", rm_extracted=False, file_order=[]):
    self.uri = None
    self.compressed = compressed
    self.extracted = extracted
    self.inner_files = []
    self.file_order = file_order
    self.is_extracted = False
    
  def download(self):
    # Download the file from `url` and save it locally under `file_name`:
    with urllib.request.urlopen(self.uri) as response, open(self.compressed, 'wb') as out_file:
      shutil.copyfileobj(response, out_file)

  def untar(self):
    with tarfile.open(self.compressed) as tar:
      for member in tar.getmembers():
        if not member.is_dir() and not member.is_file():
          pass
        self.inner_files.append(member)
      tar.extractall(path=self.extracted, members=self.inner_files)
    self.is_extracted = True
  
  def unzip(self):
    filelist = []
    with zipfile.ZipFile(self.compressed) as zf:
      filelist = zf.infolist()
      for member in filelist:
        # Path traversal defense copied from
        # http://hg.python.org/cpython/file/tip/Lib/http/server.py#l789
        words = member.filename.split('/')
        path = self.extracted
        for word in words[:-1]:
          while True:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if not drive:
              break
            if word in (os.curdir, os.pardir, ''):
              continue
            path = os.path.join(path, word)
        zf.extract(member, path)
    self.inner_files = filelist
    self.is_extracted = True

class Config(Object):
  def __init__(self, path=None):
    if self.path is None:
      raise ValueError("Must provide path to config objects.")
    self.path = path
    with open(self.path, "rb") as cfg:
      self.config = cfg.read().json()

def print_help(exit_code=0):
  print("This script is intended to build a retropie image with the latest images\r\n" .
    "and customizations from Spenser(commie). It was found that dd-ing sdcards\r\n" .
    "of varying block sizes causes issues as files are read by emulationstation.\r\n" .
    "Instead we will push a default retropie image to your sdcard, expand\r\n" .
    "appropriately, add games . configurations, and optimize for either rpi 2||3.\r\n" .
    "Eventually this may work for windows, for now it does NOT.\r\n" .
    "Usage: ./build.py [flags]\r\n" .
    "\t-v - verbose\r\n" .
    "\t-k - keep extracted files\r\n" .
    "\t-d /dev/sdcard\r\n" .
    "\t-i retropie.img\r\n" .
    "\t-g retropie.img.gz\r\n" .
    "\t-t /tmp/dir\r\n" .
    "\t-D /tmp/dl_dir")
  sys.exit(exit_code)

def parse_args(args=None):
  parser = argparse.ArgumentParser(description="RetroPie Image Builder {}".format(VERSION))
  parser.add_argument("--config", nargs=?, type=str, required=True, help="Path to configuration file.")
  parser.add_argument("--sdcard", nargs=?, type=str, required=False, help="Path to sdcard device.")
  parser.add_argument("--mount", nargs=?, type=str, required=False, help="Mountpoint for sdcard.")
  parser.add_argument("--temp-dir", nargs=?, type=str, required=True,
    help="Path to temporary directory for downloads and extraction")
  parser.add_argument("--verbose", nargs=?, action=count, required=False, help="Verbose output.")


# TODO
#mk_tmp_dirs() - done
#download_rpi_base() - done
#gunzip_rpi_base() - done
#dd_to_sd() - done
#force_ioctl_recheck() - done
#resize_sdcard() - done
#mount_sd() - done
#download_roms() - done, mostly
#untar_roms() - per archive done
#cp_roms_to_sd()
#unmount_sd() - done
