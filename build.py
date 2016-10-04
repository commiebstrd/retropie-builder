#!/usr/bin/env python3

import sys, os, re, time
import subprocess, ctypes
import tarfile, shutil, zipfile, lzma, gzip
import argparse, json, magic, logging
import urllib.request, hashlib
from enum import Enum

VERSION = "0.0.1"

# bitflags for command line opts
EF_NO_FLAGS = 0
EF_PARSE_CONFIG = 1
EF_IMAGE_SDCARD = 2
EF_INSTALL_ROMS = 4
EF_MAX_FLAGS = 255

# commented lines are for notation, handled within __init__()'s
sdcard = "/dev/sdc"
#sdcard_boot = sdcard+"1"
#sdcard_dev = sdcard+"2"
sdcard_fs = "ext4"
tmp_d = "/tmp/rpi-tmp"
rpi_root = "/mnt/rpi"
#rpi_boot = rpi_root + "/boot"
base_img = tmp_d + "/retropie.img"
#base_gz = base_img + ".gz"
tmp_dir = [rpi_root, tmp_d]

# regular expressions
RE_DEV_BASE = re.compile("(?<=/dev/)\w+") # SdCard::{rescan_drive,resize_drive}
RE_COMPRESSED = re.compile('\/(?P<cmp>[^\/]+)$') # Download::get_emulators()
RE_EXTRACTED = re.compile('(?P<file>.+)\.[^\.]{2,4}$') # Download::remove_ext()

class SdCard():
  """
  SdCard stores paths and details about the raw sd card and mount points used for writing the retropie image and roms.
  """
  def __init__(self, dev=sdcard, mount=rpi_root, fs=sdcard_fs, dir=tmp_dir):
    """
    Constructs a new SdCard object.
    Fairly linux specific, root/boot setting will need to be altered for windows at least.
    
    :param dev: Base device path, /dev/sdb, E:\.
    :param mount: Root mount point for sdcards second partition.
    :param fs: Filesystem type of image being written, not entirely necessary.
    :param dir: Temporary directory for downloading and extracting images.
    """
    self.dev = dev
    self.dev_boot = self.dev+"1"
    self.dev_root = self.dev+"2"
    self.mount_root = mount
    self.mount_boot = self.mount_root+"/boot"
    self.fs = fs
    self.tmp_dir = dir
    self.is_raw_dev = True
    self.is_root_mounted = False
  
  def rescan_drive(self):
    """
    Issues operating system specific commands to rescan partitions after writig of image or resize.
    Linux specific, needs windows/osx.
    """
    logging.info("Rescanning drive")
    sdx=RE_DEV_BASE.search(self.dev).group(0)
    path="/sys/block/" + sdx + "/device/rescan"
    print(sdx)
    while not os.path.exists(path):
      time.sleep(1)
    try:
      with open(path, "w+") as rescan:
        rescan.write("1")
    except PermissionError:
      logging.error("Failed to write rescan on {}".format(sdx))
      pass
  
  def mount(self):
    """
    Uses internal values to mount root and boot partitions of sdcard.
    Linux specific, needs windows/osx.
    """
    logging.info("Mounting sdcard")
    logging.debug("Mounting {} to {}".format(self.dev_root,self.mount_root))
    subprocess.run("mount "+self.dev_root+" "+self.mount_root, shell=True, check=True)
    logging.debug("Mounting {} to {}".format(self.dev_boot,self.mount_boot))
    subprocess.run("mount "+self.dev_boot+" "+self.mount_boot, shell=True, check=True)

  def umount(self):
    """
    Uses interal values to unmount root and boot partitions of sdcard.
    Linux specific, needs windows/osx.
    """
    logging.info("Unmounting sdcard")
    logging.debug("Umounting {} from {}".format(self.dev_boot,self.mount_boot))
    subprocess.run("umount "+self.mount_boot, shell=True, check=True)
    logging.debug("Umounting {} to {}".format(self.dev_root,self.mount_root))
    subprocess.run("umount "+self.mount_root, shell=True, check=True)

  def resize_drive(self):
    """
    Resizes second partition to full size of remaining sdcard.
    Linux specific, needs windows/osx
    """
    logging.info("Resizing drive")
    d_size=0
    sdx=RE_DEV_BASE.search(self.dev).group(0)
    s_path="/sys/block/"+sdx+"/size"
    while not os.path.exists(s_path):
      time.sleep(1)
    with open(s_path, "r") as f:
      d_size=int(f.read())
    subprocess.run("parted -m "+self.dev+" u s resizepart 2 "+str(d_size-1), shell=True, check=True)
  
  def write_img(self, img=base_img):
    """
    Block level write of img to self.dev. Needs to be rescanned and resized prior to rom addition.
    Works on windows and linux, needs osx testing but should work.
    
    :param img: Path to image for writing to sdcard.
    """
    logging.info("Writing image")
    with open(img, "rb") as in_file:
      with open(self.dev, "w+b") as out_file:
        out_file.write(in_file.read())
  
  def _mk_dir(self, path):
    """
    Internal general creation of directory function.
    Works on linux, should be agnostic. TEST
    
    :param path: Path to temporary directory for extraction and storage.
    """
    logging.info("Making {} dir".format(path))
    try:
      os.makedirs(path)
    except FileExistsError as e:
      if os.path.isdir(path) and os.access(path, os.R_OK|os.W_OK):
        pass
    except OSError as e:	# Python >2.5
      if e.errno == errno.EEXIST and os.path.isdir(path):
        pass
      else:
        raise RuntimeError("Failed to create temp dir {}.".format(path))
  
  def mk_dirs(self):
    """
    Creates temp and root mount point directories if not already created. Leverages self._mk_dir().
    Works on linux, should be cross compat. TEST
    """
    self._mk_dir(self.tmp_dir)
    self._mk_dir(self.mount_root)

  def rm_dirs(self):
    """
    Removes dirs created with self.mk_dirs()
    Works on linux, should be cross compat. TEST
    """
    logging.info("Removing temp dir")
    for path in self.tmp_dir:
      try:
        os.rmdir(path)
      except OSError as e:	# Python >2.5
        logging.error("Failed to remove temp dir {}.".format(path))
        pass

class Download():
  '''
  Download objects are used to track a single file from download through multiple levels of extraction. Depending on options set, they may leverage previously downloaded or extracted files. While not explicitly necessary, Download objects are expected to be extracted at least once prior to checking for rom extensions and copying to the sdcard.
  
  Once recursively extracted a tree of Download objects should exist within self.inner_files. Leaves should have self.extracted set to a single file or directory. They are files which either match the self.file_order expressions, or are unable to be decompressed further. Branches will have further Download objects listed within inner_Files, although they may only have been extracted and not downloaded directly. Branches are either the top level compressed file or each compressed file extracted from a previous layer of compressed Download objects.
  '''
  class FileType(Enum):
    '''
    Internal class holding filetype of this Download object.
    '''
    gzip = 1
    xz = 2
    p7zip = 3
    tar = 4
    zip = 5
    unknown = 99
    
    def get_filetype(path):
      '''
      Returns specific variant matching path's filetype.
      
      :param path: Full path of file to identify.
      '''
      logging.info("Finding filetype of {}".format(path+self.compressed))
      ty = ""
      with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
        ty = m.id_filename(path+self.compressed)
      sw = {
        base+'x-gzip': FileType.gzip,
        base+'x-xz': FileType.xz,
        base+'x-7z-compressed': FileType.p7zip,
        base+'x-tar': FileType.tar,
        base+'zip': FileType.zip
      }
      return sw.get(ty, FileType.unknown)
  
  def __init__(self, uri=None, compressed=None, extracted=None, rm_extracted=False, md5=None, file_order=[]):
    '''
    Initializes a Download object
    
    :param uri: Uri, presently only https(s), from which to download the file.
    :param compressed: Filename of compressed file, used when downloading and extracting files from this archive, and while being extracted from parent archives.
    :param extracted: Filename of extracted file, should only be set if you know this is a single step extraction, or when self.extractall() finds a leaf object, indicating it can no longer be extracted further.
    :param rm_extraced: Inidicator if self.compressed should be removed once all files are extracted.
    :param md5: String used to ensure file integrity. Should be used with downloaded files and can be used with extracted files to avoid extracting them a second time.
    :param file_order: Array of compiled regular expressions used to check if files extracted from this object are leaf or branch types.
    '''
    self.uri = uri
    self.compressed = compressed
    self.extracted = extracted
    self.inner_files = []
    self.file_order = file_order
    self.is_extracted = False
    self.md5 = md5
    self.type = FileType.get_filetype(self.compressed)
  
  def download(self, path):
    '''
    Downloads self.uri into path+self.compressed, or path+basename(self.uri)
    
    :param path: Path to temporary directory for extraction and storage.
    '''
    # Download the file from `url` and save it locally under `file_name`:
    logging.info("Downloading file: {} from: {}".format(self.compressed,self.uri))
    if os.access(path+self.compressed, mode=4) and self.md5 is not None:
      md5 = hashlib.md5(open(path+self.compressed, "rb").read()).hexdigest()
      if md5 == self.md5:
        return
    # no existing file, or not matching sum
    with urllib.request.urlopen(self.uri, timeout=300) as response, open(path+self.compressed, 'wb') as out_file:
      shutil.copyfileobj(response, out_file)
  
  def is_rom(self, f_name=""):
    '''
    Checks f_name for matches of self.extensions
    
    :param f_name: Filename string to be matched against
    :returns bool: Result of matching
    '''
    for ext in self.extensions:
      if ext.match(f_name) is not None:
        return True
    return False
  
  def lstar(self, path):
    '''
    Lists files within a tar archive.
    '''
    logging.info("Entering lstar for {}".format(path+self.compressed))
    ls = list()
    with tarfile.TarFile(path+self.compressed, 'r') as tar:
      ls = tar.getnames()
    return ls
  
  def lszip(self, path):
    '''
    Lists files within a zip archive.
    '''
    logging.info("Entering lszip for {}".format(path+self.compressed))
    ls = list()
    with zipfile.ZipFile(path+self.compressed, 'r') as zf:
      ls = zf.namelist()
    return ls
  
  def remove_ext(self):
    '''
    Removes the right most extension from self.compressed and returns as a list. If the regex does not match, returns None. Used to "list" inner files of xz and gzip files.
    '''
    logging.info("Entering remove_ext for {}".format(self.compressed))
    name = RE_EXTRACTED.match(self.compressed).group("file")
    if name is None:
      return None
    return list(name)
  
  def get_inner_files(self, path):
    '''
    Uses self.type to list files within self.compressed. If type is gzip or xz, the current extension will be removed, such that file.tar.gz will become file.tar, just as gunzip and like, would normally do.
    
    :param path: Temporary path location.
    '''
    logging.info("Entering get_inner_files for type {} at file {}".format(str(self.type), path+self.compressed))
    sw = {
      FileType.tar: self.lstar,
      FileType.gzip: self.remove_ext,
      FileType.xz: self.remove_ext,
      FileType.p7zip: None,
      FileType.zip: self.lszip
      # FileType.unknown: should be rom
    }
    if self.type in sw.keys():
      fn = sw.get(self.type)
      ret = fn(member, path)
    else:
      logging.info("found unknown type: {} for file: {}".format(str(self.type), path+member))
      ret = None
    return ret
  
  def untar(self, member, path):
    '''
    Untars member from self.compressed, outputs to path+member.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    '''
    logging.info("Untar file: {} to: {}".format(path+self.compessed,path+self.extracted))
    with tarfile.TarFile(path+self.compressed) as tar:
      with tar.extractfile(member) as xtar, open(path+member, 'w+') as fout:
        fout.write(xtar.read())
  
  def unzip(self, member, path):
    '''
    Opens self.compressed for extraction of member to path+member.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    '''
    logging.info("Unzip file: {} to: {}".format(path+self.compessed,pathmember))
    with zipfile.ZipF(self.compressed) as zf, open(path+member, 'wb') as fout:
      zf.extract(member, path+member)
  
  def unlzma(self, member, path):
    '''
    Extracts self.compressed into member+path. Xz compression has no idea of files, so hopefully one tars any sequential files first. This intends read from and to single but separate files.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    '''
    logging.info("Unlzma file: {} to: {}".format(path+self.compessed,path+member))
    with lzma.open(path+self.compressed) as fin, open(path+member, 'wb') as fout:
      fout.write(fin.read())
  
  def ungz(self, member, path):
    '''
    Gzip decompresses self.compressed writing to path+member. Gzip compression much like xz, has no real idea of files. This intends read from and to single but separate files.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    '''
    logging.info("Ungz file: {} to: {}".format(path+self.compressed,path+member))
    with gzip.open(path+self.compressed, 'rb') as fin, open(path+member, 'wb') as fout:
      fout.write(fin.read())
  
  def decompress(self, member, path):
    """
    Decompress a single file from self into a temporary path
    plus compressed name. Presently works with any combination
    of: tar, gzip, xz, and zip files. 7zip soon...
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    """
    logging.info("Starting magic based decompression")
    sw = {
      FileType.tar: self.untar,
      FileType.gzip: self.ungz,
      FileType.xz: self.unlzma,
      FileType.p7zip: None,
      FileType.zip: self.unzip
      # FileType.unknown: should be rom
    }
    if self.type in sw.keys():
      fn = sw.get(self.type)
      fn(member, path)
    else:
      logging.info("found unknown type: {} for file: {}".format(ty, path+member))
  
  def decompress_all(self, path):
    """
    Takes a download object and processes as needed.
    We build an object tree using objects with an extracted
    path set to indicate final rom files vs without being
    files of a further compressed file. the list of files
    contained within this parent is stored as a list of
    inner object types within the self.inner_objects.
    Once rom vs rar is determined, recurse if needed. After
    this the inner_files can of self can be walked for a
    file tree.
    
    :param path: Path to temporary directory for extraction and storage.
    """
    
    # get list of inner files for parsing
    list_t = self.get_inner_files() #todo
    # parse list of files into roms and compressed files, after this extraction
    rom_list = [file_t for file_t in list_t if self.is_rom(file_t)]
    rar_list = [file_t for file_t in list_t if not self.is_rom(file_t)]
    # append roms list and rar list to inner_files. use self.extracted to determine extract method
    self.inner_files.append(
      Download(
        compressed=rom,
        extracted=path+rom,
        rm_extracted=self.rm
      ) for rom in rom_list)
    self.inner_files.append(
      Download(
        compressed=rar,
        file_order=self.file_order,
        rm_extracted=self.rm
      ) for rar in rar_list)
    # cycle through list of files within this compressed file and extract and continue building tree if needed
    for i_f in self.inner_files:
      self.decompress(i_f.compressed_path, path)
      if i_f.extracted is None: # have final file we want
        i_f.decompress_all(path)
    if self.rm:
      self.delete(path)

class Config():
  '''
  Config objects read the configuration provided by command line arguments and store json representations of other objects here. As needed the sdcard(SdCard), retropie(Download), and emulators(list(Download)) objects can be created. If manipulation or alteration of these base initializations is needed, it should be done either with the read configuration or after generation of object.
  '''
  def __init__(self, path=None):
    '''
    Initializes a Config object from the file provided byt path.
    
    :params path: Path to configuration file
    '''
    if path is None:
      raise ValueError("Must provide path to config objects.")
    self.path = path
    with open(self.path, "r+") as cfg:
      self.json = json.load(cfg)
    self.sdcard = self.json.get("sdcard")
    self.retropie = self.json.get("retropie")
    self.emulators = self.json.get("emulators")
  
  def get_sdcard(self, args):
    '''
    Generates an SdCard object from internal jsons objects. Allows cli args to override config, if provided.
    
    :params args: Argument structure provided buy parse_args().
    '''
    sdcard = SdCard(dev=self.sdcard.get("dev_path"),
      mount=self.sdcard.get("mount_path"), fs=self.sdcard.get("filesystem"),
      dirs=self.sdcard.get("temp_path"))
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
    '''
    Generates a Download object with for retropie image use. Specifically it sets extracted and compressed so we know it's a single extraction and the wanted output file.
    '''
    return Download(
      uri=self.retropie.get("uri"),
      compressed=self.retropie.get("compressed_path"),
      extracted=self.retropie.get("extracted_path"),
      md5=self.retropie.get("md5"),
      rm_extracted=True )
  
  def get_emulators(self):
    '''
    Generates a list of Download objects, set such that they will search internally and build the inner_files tree as needed.
    '''
    logging.debug("Entered get_emulators() with path: {}".format(path))
    emulators = []
    for name, settings in self.emulators.items():
      if settings.get("cp_to_sd") == True:
        logging.debug("rom_uris: {} sub_cmp: ".format(settings.get("rom_uris")))
        cmp = RE_COMPRESSED.match(settings.get("rom_uris")).group("cmp") # not working with arrays of uris, also how to handle them...
        f_o = [ re.compile('.+\.'+ext+'$') for ext in settings.get("extensions") ]
        emulators.append(Download(
                      uri=settings.get("rom_uris"),
                      compressed=cmp,
                      get_all=settings.get("dl_all_b4_extract"),
                      file_order=f_o))

def parse_args(args=None):
  '''
  Parse commandline arguments. Natively handles help. Commandline arguments superscede config options.
  
  :param args: Argv
  '''
  parser = argparse.ArgumentParser(description="RetroPie Image Builder {}".format(VERSION))
  parser.add_argument("-c", "--config", type=str, required=True, help="Path to configuration file.")
  parser.add_argument("-s", "--sdcard", type=str, required=False, help="Path to sdcard device.")
  parser.add_argument("-m", "--mount", type=str, required=False, help="Mountpoint for sdcard.")
  parser.add_argument("-t", "--temp", type=str, required=False,
    help="Path to temporary directory for downloads and extraction")
  parser.add_argument("-v", "--verbose", action="count", required=False, help="Verbose output.")
  parser.add_argument("--parse-config", action="count", required=False, help="total_options+=parse config only")
  parser.add_argument("--image-sdcard", action="count", required=False, help="total_options+=download, extract, and image retropie onto sdcard")
  parser.add_argument("--install-roms", action="count", required=False, help="total_options+=download, extract and cp roms, mount and unmount sdcard")
  args = parser.parse_args(args)
  
  if not args.config:
    print("Please specify a configuration file")
    print_help(1)
  
  execute_flag = EF_NO_FLAGS
  if args.parse-config and 0 <= args.parse-config:
    execute_flag &= EF_PARSE_CONFIG
  if args.image-sdcard and 0 <= args.image-sdcard:
    execute_flag &= EF_IMAGE_SDCARD
  if args.install-roms and 0 <= args.install-roms:
    execute_flag &= EF_INSTALL_ROMS
  if execute_flag == EF_NO_FLAGS:
    execute_flag = EF_MAX_FLAGS # way more than any unique flags we would need... hopefully
  logging.debug("Generated execute flag: {}".format(execute_flag))
  args.e_flag = execute_flag
  
  return args

def main(argv):
  '''
  Execute as arguments indicated by cli.
  
  :param argv: sys.argv array for parsing.
  '''
  args = parse_args(argv)
  if args.verbose:
    print("got verbose {}", args.verbose)
    sw = {
      0: logging.NOTSET,
      1: logging.INFO,
      2: logging.CRITICAL,
    }
    args.verbose = args.verbose if args.verbose <= 2 else 2
    logging.basicConfig(level=sw.get(args.verbose),
                      format='%(levelname)-8s %(message)s',
                      datefmt='%m-%d %H:%M')
  
  if (args.e_flag & EF_PARSE_CONFIG) == EF_PARSE_CONFIG:
    config = Config(args.config)
    sdcard = config.get_sdcard(args)
    retropie = config.get_retropie()
    emulators = config.get_emulators(sdcard.tmp_dir)
  if (args.e_flag & EF_IMAGE_SDCARD) == EF_IMAGE_SDCARD:
    sdcard.mk_dirs(sdcard.tmp_dir)
    retropie.download(sdcard.tmp_dir)
    retropie.decompress(sdcard.tmp_dir)
    sdcard.write_img(retropie.extracted)
    
    try:
      sdcard.rescan_drive()
    except PermissionError as e:
      logging.ERROR("Rescan error, sleeping 5s")
      time.sleep(5)
    
    try:
      sdcard.resize_drive()
    except PermissionError as e:
      logging.ERROR("Resize error, exiting: {}".format(e))
      return 1
  
  if (args.e_flag & EF_INSTALL_ROMS) == EF_INSTALL_ROMS:
    try:
      sdcard.mount()
    except RuntimeError as e:
      print(e)
      return 1
    
    for emulator in emulators:
      emulator.download()
      emulator.decompress()
      emulator.cp_to_sd()
    
    sdcard.unmount()
  
  later = """
    handle more errors
    verify osx pathing and drives
    backup/restore of controllers and saves
  """

'''
Are we actually in main? If so, someone called us directly and we should process as such...
'''
if __name__ == "__main__":
  exit_code = main(sys.argv[1:])
  sys.exit(exit_code)
