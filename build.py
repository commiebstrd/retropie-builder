#!/usr/bin/env python3

import sys, os, re
import subprocess
import tarfile, shutil, zipfile, lzma, gzip
import argparse, json, magic
import urllib.request, hashlib

VERSION = "0.0.1"

# commented lines are for notation, handled within __init__()'s
sdcard = "/dev/sdc"
#sdcard_boot = sdcard+"1"
#sdcard_dev = sdcard+"2"
sdcard_fs = "ext3"
tmp_d = "/tmp/rpi-tmp"
rpi_root = "/mnt/rpi"
#rpi_boot = rpi_root + "/boot"
base_img = tmp_d + "/retropie.img"
#base_gz = base_img + ".gz"
tmp_dir = [rpi_root, tmp_d]

class SdCard():
  def __init__(self, dev=sdcard, mount=rpi_root, fs=sdcard_fs, dirs=tmp_dir):
    self.dev = dev
    self.dev_boot = self.dev+"1"
    self.dev_root = self.dev+"2"
    self.mount_root = mount
    self.mount_boot = self.mount_root+"/boot"
    self.fs = fs
    self.tmp_dir = dirs
    self.is_raw_dev = True
    self.is_root_mounted = False
  
  def rescan_drive(self):
    sdx=re.search("(?<=/dev/)\w+", self.dev).group(0)
    with open("/sys/block/" + sdx + "/device/rescan", "w+") as rescan:
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
    with open("/sys/block/" + sdx + "/size", "r") as f:
      d_size=f.read()
    # resize disk
    subprocess.run("parted -m /dev/" + sdx + " u s resizepart /dev/" + sdx + "2 " + str(d_size-1), shell=True, check=True)
  
  def write_img(self, img=base_img):
    with open(img, "rb") as in_file:
      with open(self.dev, "w+b") as out_file:
        out_file.write(in_file.read())
  
  def mk_dirs(self):
    try:
      os.makedirs(self.tmp_dir)
    except FileExistsError as e:
      if os.path.isdir(self.tmp_dir) and os.access(self.tmp_dir, os.R_OK|os.W_OK):
        pass
    except OSError as e:	# Python >2.5
      if e.errno == errno.EEXIST and os.path.isdir(self.tmp_dir):
        pass
      else:
        raise RuntimeError("Failed to create temp dir {}.".format(path))

  def rm_dirs(self):
    for path in self.tmp_dir:
      try:
        os.rmdir(path)
      except OSError as e:	# Python >2.5
        print("Failed to remove temp dir {}.".format(path))
        pass

class Download():
  def __init__(self, uri=None, compressed="file.gz", extracted="file/", rm_extracted=False, md5="", file_order=[]):
    self.uri = uri
    self.compressed = compressed
    self.extracted = extracted
    self.inner_files = []
    self.file_order = file_order
    self.is_extracted = False
    self.md5 = md5
    
  def download(self, path):
    # Download the file from `url` and save it locally under `file_name`:
    print(self.uri)
    if os.access(path+self.compressed, mode=4) and self.md5 is not None:
      md5 = hashlib.md5(open(path+self.compressed, "rb").read()).hexdigest()
      if md5 == self.md5:
        return
    # no existing file, or not matching sum
    with urllib.request.urlopen(self.uri, timeout=300) as response, open(path+self.compressed, 'wb') as out_file:
      shutil.copyfileobj(response, out_file)

  def untar(self, path):
    print(path+self.compressed)
    with tarfile.open(path+self.compressed) as tar:
      for member in tar.getmembers():
        if not member.is_dir() and not member.is_file():
          pass
        self.inner_files.append(member)
      tar.extractall(path=path+self.extracted, members=self.inner_files)
  
  def unzip(self, path):
    filelist = []
    with zipfile.ZipFile(self.compressed) as zf:
      filelist = zf.infolist()
      for member in filelist:
        # Path traversal defense copied from
        # http://hg.python.org/cpython/file/tip/Lib/http/server.py#l789
        words = member.filename.split('/')
        epath = path+self.extracted
        for word in words[:-1]:
          while True:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if not drive:
              break
            if word in (os.curdir, os.pardir, ''):
              continue
            epath = os.path.join(epath, word)
        zf.extract(member, epath)
    self.inner_files = filelist
  
  def unlzma(self, path):
    cpath=path+self.compressed
    epath=path+self.extracted
    with lzma.open(cpath) as fin, open(epath, 'wb') as fout:
      fout.write(fin.read())
  
  def ungz(self, path):
    cpath=path+self.compressed
    epath=path+self.extracted
    with gzip.open(cpath, 'rb') as fin, open(epath, 'wb') as fout:
      fout.write(fin.read())
  
  def decompress(self, path):
    base = "application/"
    ty = ""
    with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
      ty = m.id_filename(path+self.compressed)
    if ty == base+'x-tar':
      print("found tar, attempting to untar")
      self.untar(path)
    elif ty == base+'x-gzip':
      print("found gzip, attempting to untar")
      self.ungz(path)
    elif ty == base+'x-xz':
      print("found xz, do something with me!")
      self.unlzma(path)
    elif ty == base+'x-bzip2':
      print("found bz2, do something with me!")
      self.unlzma(path)
    elif ty == base+'x-7z-compressed':
      print("found 7z, do something with me!")
    elif ty == base+'zip':
      print("found zip, attempting to unzip")
      self.unzip(path)
    else:
      print("found unknown type: {} for file: {}".format(ty, path+self.compressed))
    self.is_extracted = True
    self.extracted = path+self.extracted

class Config():
  def __init__(self, path=None):
    if path is None:
      raise ValueError("Must provide path to config objects.")
    self.path = path
    with open(self.path, "r+") as cfg:
      self.json = json.load(cfg)
    self.sdcard = self.json.get("sdcard")
    self.retropie = self.json.get("retropie")
    self.emulators = self.json.get("emulators")
  
  def get_sdcard(self, args):
    sdcard = SdCard(dev=self.sdcard.get("dev_path"),
      mount=self.sdcard.get("mount_path"), dirs=self.sdcard.get("temp_path"))
    if args.sdcard is "" and 0 < len(args.sdcard) and len(args.sdcard) <= 255:
      sdcard.dev = args.sdcard
      sdcard.dev_boot = args.sdcard+"1"
      sdcard.dev_root = args.sdcard+"2"
    if args.mount is "" and 0 < len(args.mount) and len(args.mount) <= 255:
      sdcard.mount_root = args.mount
      sdcard.mount_boot = args.mount+"/boot"
    if args.temp is "" and 0 < len(args.temp) and len(args.temp) <= 255:
      sdcard.tmp_dir = args.temp
    return sdcard
  
  def get_retropie(self):
    return Download(
      uri=self.retropie.get("uri"),
      compressed=self.retropie.get("compressed_path"),
      extracted=self.retropie.get("extracted_path"),
      md5=self.retropie.get("md5"),
      rm_extracted=True )
  
  def get_emulators(self, path):
    emulators = []
    cmp_re = re.compile('\/(?P<cmp>[^\/]+)$')
    ext_re = re.compile('(?P<ext>[^\.]+)\.[^\.]+$')
    for name, settings in self.emulators.items():
      if settings.get("cp_to_sd") == True:
        cmp = cmp_re.match(settings.get("rom_uris")).group("cmp")
        ext = ext_re.match(cmp).group("ext")
        emulators.append(Download(
                      uri=settings.get("rom_uris"),
                      compressed=cmp,
                      extracted=path+ext,
                      get_all=settings.get("dl_all_b4_extract"),
                      file_order = settings.get("extensions")))

def parse_args(args=None):
  parser = argparse.ArgumentParser(description="RetroPie Image Builder {}".format(VERSION))
  parser.add_argument("-c", "--config", type=str, required=True, help="Path to configuration file.")
  parser.add_argument("-s", "--sdcard", type=str, required=False, help="Path to sdcard device.")
  parser.add_argument("-m", "--mount", type=str, required=False, help="Mountpoint for sdcard.")
  parser.add_argument("-t", "--temp", type=str, required=False,
    help="Path to temporary directory for downloads and extraction")
  parser.add_argument("-v", "--verbose", action="count", required=False, help="Verbose output.")
  args = parser.parse_args(args)
  
  if not args.config:
    print("Please specify a configuration file")
    print_help(1)
  return args

def main(argv):
  args = parse_args(argv)
  config = Config(args.config)
  sdcard = config.get_sdcard(args)
  retropie = config.get_retropie()
  emulators = config.get_emulators(sdcard.tmp_dir)
  sdcard.mk_dirs()
  retropie.download(sdcard.tmp_dir)
  retropie.decompress(sdcard.tmp_dir)
  sdcard.write_img(retropie.extracted)
  todo = '''
  sdcard.rescan_drive()
  sdcard.resize_drive()
  sdcard.rescan_drive()
  sdcard.mount()
  for each emulator:
    emulator.download()
    emulator.extract()
    emulator.cp_final_to_sd()
  sdcard.unmount()
  
  later:
    handle errors
    verify osx pathing and drives
    backup/restore of controllers and saves
  '''

if __name__ == "__main__":
  main(sys.argv[1:])
