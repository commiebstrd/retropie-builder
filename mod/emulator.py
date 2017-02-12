#!/usr/bin/env python3

import logging
import shutil, re
from progress.bar import Bar
from .download import *

ROOT_TO_ROMS="/home/pi/RetroPie/roms/"
logger = logging.getLogger(__name__)

class Emulator():
    def __init__(self, name, path, downloads=[], dl_all=False, rm=False):
        self.name = name # key in config
        self.rpi_path = path # rom dir on rpi
        self.downloads = downloads # array of download objects
        self.dl_all = dl_all # grab all before extract?
        self.rm_extracted = rm
    
    def download(self, dlpath):
        logger.info("Downloading for emulator {}".format(self.name))
        for download in self.downloads:
            download.download(dlpath)
    
    def cp_to_sd(self, dlpath, sdpath):
      print("Document cp_to_sd()!")
      logger.info("Copy from {} to {} for {}".format(dlpath, sdpath, self.name))
      bar = Bar("Copyying {} to sdcard:".format(self.name), max=len(self.downloads))
      for download in self.downloads:
          bar.next()
          download.cp_to_sd(self.rpi_path, dlpath, sdpath)
      bar.finish()
    
    def decompress_all(self, dlpath):
        logging.info("Decompress_all for emulator {}".format(self.name))
        if self.dl_all:
            base_rar_re = re.compile(r"([\w\-_\.]0+\.rar|.r00+)$")
            bar = Bar("Decompressing roms for {}:".format(self.name), max=1)
            for download in self.downloads:
                if base_rar_re.match(download.compressed):
                    bar.next()
                    download.decompress_all(dlpath)
        else:
            bar = Bar("Decompressing roms for {}:".format(self.name), max=len(self.downloads))
            for download in self.downloads:
                bar.next()
                download.decompress_all(dlpath)
        bar.finish()
