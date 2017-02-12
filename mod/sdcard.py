#!/usr/bin/env python3

import logging, json
import subprocess, platform
import sys, os, re, time

logger = logging.getLogger(__name__)

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
    logger.info("Rescanning drive")
    sdx=RE_DEV_BASE.search(self.dev).group(0)
    path="/sys/block/" + sdx + "/device/rescan"
    print(sdx)
    while not os.path.exists(path):
      time.sleep(1)
    try:
      with open(path, "w+") as rescan:
        rescan.write("1")
    except PermissionError:
      logger.error("Failed to write rescan on {}".format(sdx))
      pass
  
  def mount(self):
    """
    Uses internal values to mount root and boot partitions of sdcard.
    Linux specific, needs windows/osx.
    """
    logger.info("Mounting sdcard")
    logger.debug("Mounting {} to {}".format(self.dev_root,self.mount_root))
    try:
      subprocess.run("mount "+self.dev_root+" "+self.mount_root, shell=True, check=True)
    except subprocess.CalledProcessError as e:
      if e == 32:
        logger.warning("Failed to mount rpi root, likely already mounted")
    logger.debug("Mounting {} to {}".format(self.dev_boot,self.mount_boot))
    try:
      subprocess.run("mount "+self.dev_boot+" "+self.mount_boot, shell=True, check=True)
    except subprocess.CalledProcessError as e:
      if e == 32:
        logger.warning("Failed to mount rpi root, likely already mounted")

  def umount(self):
    """
    Uses interal values to unmount root and boot partitions of sdcard.
    Linux specific, needs windows/osx.
    """
    logger.info("Unmounting sdcard")
    logger.debug("Umounting {} from {}".format(self.dev_boot,self.mount_boot))
    try:
      subprocess.run("umount "+self.mount_boot, shell=True, check=True)
    except subprocess.CalledProcessError as e:
      logger.warning("Failed to unmount rpi boot!")
    logger.debug("Umounting {} to {}".format(self.dev_root,self.mount_root))
    try:
      subprocess.run("umount "+self.mount_root, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to unmount rpi root!")

  def resize_drive(self):
    """
    Resizes second partition to full size of remaining sdcard.
    Linux specific, needs windows/osx
    """
    logger.info("Resizing drive")
    if platform.system() == "Linux":
        d_size=0
        dev_base = re.compile("(?<=/dev/((disk-by)[^/]*/)?)\w+")
        sdx=dev_base.search(self.dev).group(0)
        s_path="/sys/block/"+sdx+"/size"
        while not os.path.exists(s_path): # inifinite loop on osx
          time.sleep(1)
        with open(s_path, "r") as f:
          d_size=int(f.read())
        try:
          subprocess.run("parted -m {} u s resizepart 2 {}".format(self.dev,str(d_size-1)), shell=True, check=True)
        except subprocess.CalledProcessError as e:
          logger.warning("Failed to resize drive!")
    else:
        logger.error("Resize and futher operation not possible on OSX and Windows.")
        return 1
    return 0
  
  def write_img(self, img=base_img):
    """
    Block level write of img to self.dev. Needs to be rescanned and resized prior to rom addition.
    Works on windows and linux, needs osx testing but should work.
    
    :param img: Path to image for writing to sdcard.
    """
    logger.info("Writing image")
    with open(self.tmp_dir+img, "rb") as in_file, open(self.dev, "w+b") as out_file:
        out_file.write(in_file.read())
  
  def _mk_dir(self, path):
    """
    Internal general creation of directory function.
    Works on linux, should be agnostic. TEST
    
    :param path: Path to temporary directory for extraction and storage.
    """
    logger.info("Making {} dir".format(path))
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
    logger.info("Removing temp dir")
    for path in self.tmp_dir:
      try:
        os.rmdir(path)
      except OSError as e:	# Python >2.5
        logger.error("Failed to remove temp dir {}.".format(path))
        pass
