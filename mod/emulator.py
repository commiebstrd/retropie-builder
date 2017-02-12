#!/usr/bin/env python3

import logging
import shutil, re
from .download import *

ROOT_TO_ROMS="/home/pi/RetroPie/roms/"

class Emulator():
    def __init__(self, name, path, downloads=[], dl_all=False, rm=False):
        self.name = name # key in config
        self.rpi_path = path # rom dir on rpi
        self.downloads = downloads # array of download objects
        self.dl_all = dl_all # grab all before extract?
        self.rm_extracted = rm
    
    def download(self, dlpath):
        logging.info("Downloading for emulator {}".format(self.name))
        for download in self.downloads:
            download.download(dlpath)
    
    def cp_to_sd(self, dlpath, sdpath):
      print("Document cp_to_sd()!")
      logging.info("Copy from {} to {} for {}".format(dlpath, sdpath, self.name))
      for download in self.downloads:
          download.cp_to_sd(self.rpi_path, dlpath, sdpath)
    
    def decompress_all(self, dlpath):
        logging.info("Decompress_all for emulator {}".format(self.name))
        if self.dl_all:
            base_rar_re = re.compile(r"([\w\-_\.]0+\.rar|.r00+)$")
            for download in self.downloads:
                if base_rar_re.match(download.compressed):
                    download.decompress_all(dlpath)
        else:
            for download in self.downloads:
                download.decompress_all(dlpath)
