#!/usr/bin/env python3

import sys, os, re, time
import argparse, json, logging

from mod.sdcard import *
from mod.download import *
from mod.emulator import *
from mod.config import *

VERSION = "0.0.1"

# bitflags for command line opts
EF_NO_FLAGS = 0
EF_IMAGE_SDCARD = 1
EF_INSTALL_ROMS = 2
EF_IGNORE_MOUNTS = 4
EF_MAX_FLAGS = 255

# MAIN
def parse_args(args=None, logger=None):
  '''
  Parse commandline arguments. Natively handles help. Commandline arguments superscede config options.
  
  :param args: Argv
  '''
  parser = argparse.ArgumentParser(description="RetroPie Image Builder {}"+VERSION)
  parser.add_argument("-c", "--config", type=str, required=True, help="Path to configuration file.")
  parser.add_argument("-s", "--sdcard", type=str, required=False, help="Path to sdcard device.")
  parser.add_argument("-m", "--mount", type=str, required=False, help="Mountpoint for sdcard.")
  parser.add_argument("-t", "--temp", type=str, required=False,
    help="Path to temporary directory for downloads and extraction")
  parser.add_argument("-v", "--verbose", action="count", required=False, help="Verbose output.")
  parser.add_argument("--image_sdcard", action="store_const", const=True, required=False, help="total_options+=download, extract, and image retropie onto sdcard")
  parser.add_argument("--install_roms", action="store_const", const=True, required=False, help="total_options+=download, extract and cp roms, mount and unmount sdcard")
  parser.add_argument("--ignore_mounts", action="store_const", const=True, required=False, help="total_options+=download, extract and cp roms, mount and unmount sdcard")
  args = parser.parse_args(args)
  
  logging.debug(args)
  
  if not args.config:
    print("Please specify a configuration file")
    print_help(1)
  
  if args.verbose:
    sw = {
      0: logging.NOTSET,
      1: logging.INFO,
      2: logging.DEBUG,
    }
    args.verbose = args.verbose if args.verbose <= 2 else 2
    logger.setLevel(level=sw.get(args.verbose, logging.NOTSET))
  
  execute_flag = EF_NO_FLAGS
  if args.image_sdcard:
    logging.debug("Setting image_sdcard")
    execute_flag |= EF_IMAGE_SDCARD
  if args.install_roms:
    logging.debug("Setting install_roms")
    execute_flag |= EF_INSTALL_ROMS
  if args.ignore_mounts:
    logging.debug("Setting ignore_mounts")
    execute_flag |= EF_IGNORE_MOUNTS
  if execute_flag == EF_NO_FLAGS:
    logging.debug("Setting max_flags")
    execute_flag = EF_MAX_FLAGS # way more than any unique flags we would need... hopefully
  logging.debug("Generated execute flag: {}".format(execute_flag))
  args.e_flag = execute_flag
  
  return args

def main(argv):
  '''
  Execute as arguments indicated by cli.
  
  :param argv: sys.argv array for parsing.
  '''
  logging.basicConfig(format='%(levelname)s|%(module)s::%(funcName)s|%(lineno)s| %(message)s', datefmt='%m-%d %H:%M')
  rootLogger = logging.getLogger()
  rootLogger.setLevel(logging.DEBUG)
  
  args = parse_args(argv, rootLogger)
  config = Config(args.config)
  sdcard = config.get_sdcard(args)
  retropie = config.get_retropie()
  emulators = config.get_emulators()
	
  sdcard.mk_dirs() # almost always need them, just create and remove when done
	
  if (args.e_flag & EF_IMAGE_SDCARD) == EF_IMAGE_SDCARD:
    
    retropie.download(sdcard.tmp_dir)
    retropie.decompress(retropie.extracted, sdcard.tmp_dir)
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
    
  if (args.e_flag & EF_IGNORE_MOUNTS) != EF_IGNORE_MOUNTS:
    try:
        sdcard.mount()
    except RuntimeError as e:
        print(e)
        return 1
  
  if (args.e_flag & EF_INSTALL_ROMS) == EF_INSTALL_ROMS:
    if emulators is None:
      logging.warning("Attempted to install roms with no roms in config.")
    else:
      for emulator in emulators:
        emulator.download(sdcard.tmp_dir)
        emulator.decompress_all(sdcard.tmp_dir)
        emulator.cp_to_sd(sdcard.tmp_dir, sdcard.mount_root)
  
  if (args.e_flag & EF_IGNORE_MOUNTS) != EF_IGNORE_MOUNTS:
    sdcard.umount()
  
    #sdcard.rm_dirs() # always remove temp dirs... however what about when we dont want to rm roms? TODO
''' TODO
    handle more errors
    backup/restore of controllers and saves
'''

'''
Are we actually in main? If so, someone called us directly and we should process as such...
'''
if __name__ == "__main__":
  exit_code = main(sys.argv[1:])
  sys.exit(exit_code)
