#!/usr/bin/env python3

import json, logging
import sys, os, re, time
from .download import Download
from .emulator import Emulator
from .sdcard import SdCard

logger = logging.getLogger(__name__)

RE_COMPRESSED = re.compile('\/(?P<cmp>[^\/]+)$') # Download::get_emulators()

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
      dir=self.sdcard.get("temp_path"))
    if isinstance(args.sdcard,str) and 0 < len(args.sdcard) and len(args.sdcard) <= 255:
      sdcard.dev = args.sdcard
      sdcard.dev_boot = args.sdcard+"1"
      sdcard.dev_root = args.sdcard+"2"
    if isinstance(args.mount,str) and 0 < len(args.mount) and len(args.mount) <= 255:
      sdcard.mount_root = args.mount
      sdcard.mount_boot = args.mount+"/boot"
    if isinstance(args.temp,str) and 0 < len(args.temp) and len(args.temp) <= 255:
      sdcard.tmp_dir = args.temp
    return sdcard
  
  def get_retropie(self):
    '''
    Generates a Download object with for retropie image use. Specifically it sets extracted and compressed so we know it's a single extraction and the wanted output file.
    '''
    return Download(
      uri=self.retropie.get("uri"),
      compressed=self.retropie.get("compressed_path"),
      extract=True,
      md5=self.retropie.get("md5") )
  
  def get_emulators(self):
    '''
    Generates a list of Download objects, set such that they will search internally and build the inner_files tree as needed.
    '''
    logger.debug("Entered get_emulators()")
    emulators = []
    for name, settings in self.emulators.items():
      if name is not None and settings is not None and settings.get("cp_to_sd") == True:
        logger.debug("rom_uris: {} sub_cmp: ".format(settings.get("rom_uris")))
        cmp = []
        emulator = Emulator(
            name,
            settings.get('rpi_path'),
            [],
            settings.get("dl_all_b4_extract"),
            settings.get("rm_extracted"))
        f_o = [ re.compile('.+\.'+ext+'$') for ext in settings.get("extensions") ]
        for uri in settings.get("rom_uris"):
          # allow each uri as a dl obj by falling through building uri, cmp, and adding
          if uri:
            uri_re = RE_COMPRESSED.search(uri)
          if uri_re:
            cmp = uri_re.group("cmp")
          if uri and cmp:
            # add individual download obj to encompasing emulator obj
            emulator.downloads.append(Download(
                      uri=uri,
                      compressed=cmp,
                      file_order=f_o ))
          else:
            logger.error("invalid uri found: {} - {}".format(cmp,uri))
        if 1 <= len(emulator.downloads):
            emulators.append(emulator)
    return emulators
