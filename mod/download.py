#!/usr/bin/env python3

import logging
from enum import Enum
import sys, os, re, time, shlex
import urllib.request, hashlib
import magic, subprocess, ctypes
import tarfile, shutil, zipfile, lzma, gzip, rarfile

# regular expressions
RE_EXTRACTED = re.compile('(?P<file>.+)\.[^\.]{2,4}$') # Download::remove_ext()

class FileType(Enum):
  '''
  Internal class holding filetype of this Download object.
  '''
  gzip = 1
  xz = 2
  p7zip = 3
  tar = 4
  zip = 5
  rar = 6
  unknown = 99
  
  def get_filetype(path):
    '''
    Returns specific variant matching path's filetype.
    
    :param path: Full path of file to identify.
    '''
    logging.info("Finding filetype of {}".format(path))
    base = 'application/'
    ty = ""
    with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
      ty = m.id_filename(path)
    logging.debug("Found {}".format(ty))
    sw = {
      base+'x-gzip': FileType.gzip,
      base+'x-xz': FileType.xz,
      base+'x-7z-compressed': FileType.p7zip,
      base+'x-tar': FileType.tar,
      base+'zip': FileType.zip,
      base+'x-rar': FileType.rar,
    }
    return sw.get(ty, FileType.unknown)

class Download():
  '''
  Download objects are used to track a single file from download through multiple levels of extraction. Depending on options set, they may leverage previously downloaded or extracted files. While not explicitly necessary, Download objects are expected to be extracted at least once prior to checking for rom extensions and copying to the sdcard.
  
  Once recursively extracted a tree of Download objects should exist within self.inner_files. Leaves should have self.extracted set to a single file or directory. They are files which either match the self.file_order expressions, or are unable to be decompressed further. Branches will have further Download objects listed within inner_Files, although they may only have been extracted and not downloaded directly. Branches are either the top level compressed file or each compressed file extracted from a previous layer of compressed Download objects.
  '''
  
  def __init__(self, uri=None, compressed=None, extract=False, dl_all=True, md5=None, file_order=[]):
    '''
    Initializes a Download object
    
    :param uri: List of uris, presently only https(s), from which to download the file.
    :param compressed: List of filenames of compressed file, used when downloading and extracting files from this archive, and while being extracted from parent archives.
    :param extracted: Boolean to determine if this should be extracted further.
    :param rm_extraced: Inidicator if self.compressed should be removed once all files are extracted.
    :param md5: String used to ensure file integrity. Should be used with downloaded files and can be used with extracted files to avoid extracting them a second time.
    :param file_order: Array of compiled regular expressions used to check if files extracted from this object are leaf(rom) or branch(rar/zip/tar) types.
    '''
    self.uri = uri
    self.compressed = compressed
    self.extract = extract
    self.inner_files = []
    self.file_order = file_order
    self.is_extracted = False
    self.dl_all = dl_all
    self.md5 = md5
    self.type = []
  
  def set_filetype(self, path):
    '''
    Checks self.compressed for filetype.
    '''
    logging.debug("Setting filetype")
    self.type = FileType.get_filetype(path+self.compressed)
  
  def download(self, path):
    '''
    Downloads self.uri into path+self.compressed, or path+basename(self.uri)
    
    :param path: Path to temporary directory for extraction and storage.
    '''
    # Download the file from `url` and save it locally under `file_name`:
    logging.info("Downloading file: {} from: {}".format(self.compressed, self.uri))
    if os.access(path+self.compressed, mode=4) and self.md5 is not None:
        md5 = hashlib.md5(open(path+self.compressed, "rb").read()).hexdigest()
        if md5 == self.md5:
            self.set_filetype(path)
            return
    # no existing file, or not matching sum
    try:
        with urllib.request.urlopen(self.uri, timeout=300) as response, open(path+self.compressed, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    #self.set_filetype(path)
    except urllib.error.NameError:
        logging.error("Uri appears invalid: {}".format(uri)); return
    except urllib.error.HTTPError:
        logging.error("Failed to download file: {}".format(uri)); return
    self.set_filetype(path)
  
  def is_rom(self, f_name=""):
    '''
    Checks f_name for matches of self.extensions
    
    :param f_name: Filename string to be matched against
    :returns bool: Result of matching
    '''
    for ext in self.file_order:
      if ext.match(f_name, re.I) is not None: # TODO should this be search not match?
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
  
  def lsrar(self, path):
    print("Document lsrar()!")
    logging.info("Entered lsrar for {}".format(path+self.compressed))
    ls = list()
    with rarfile.RarFile(path+self.compressed) as rf:
        ls = rf.namelist()
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
    logging.info("Entering get_inner_files for type {} at file {}".format(str(self.type), self.compressed))
    sw = {
      FileType.tar: self.lstar,
      FileType.gzip: self.remove_ext,
      FileType.xz: self.remove_ext,
      FileType.p7zip: None,
      FileType.zip: self.lszip,
      FileType.rar: self.lsrar,
      # FileType.unknown: should be rom
    }
    if self.type in sw.keys():
      fn = sw.get(self.type)
      ret = fn(path)
    else:
      logging.info("found unknown type: {} for file: {}".format(str(self.type), self.compressed))
      ret = None
    return ret
  
  def untar(self, member, path):
    '''
    Untars member from self.compressed, outputs to path+member.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    '''
    logging.info("Untar file: {} to: {}".format(self.compessed, member))
    infile = shlex.quote("{}{}".format(path,self.compressed))
    outfile = shlex.quote("{}{}".format(path,member))
    with tarfile.TarFile(infile) as tar:
      with tar.extractfile(member) as xtar, open(outfile, 'w+') as fout:
        fout.write(xtar.read())
  
  def unzip(self, member, path):
    '''
    Opens self.compressed for extraction of member to path+member.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Temporary directory for extraction.
    '''
    logging.info("Unzip file: {} to: {}".format(self.compessed, path+member))
    infile = shlex.quote("{}{}".format(path,self.compressed))
    outfile = shlex.quote("{}{}".format(path,member))
    with zipfile.ZipFile(infile, 'r') as zf:
      zf.extract(member, outfile)
  
  def unlzma(self, member, path):
    '''
    Extracts self.compressed into member+path. Xz compression has no idea of files, so hopefully one tars any sequential files first. This intends read from and to single but separate files.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    '''
    logging.info("Unlzma file: {} to: {}".format(self.compessed, member))
    infile = shlex.quote("{}{}".format(path,self.compressed))
    outfile = shlex.quote("{}{}".format(path,member))
    with lzma.open(infile) as fin, open(outfile, 'wb') as fout:
      fout.write(fin.read())
  
  def ungz(self, member, path):
    '''
    Gzip decompresses self.compressed writing to path+member. Gzip compression much like xz, has no real idea of files. This intends read from and to single but separate files.
    
    :param member: Name of object within self.compressed to be extracted and written to as path+this
    :param path: Path to temporary directory for extraction and storage.
    '''
    logging.info("Ungz file: {} to: {}".format(self.compressed, member))
    infile = shlex.quote("{}{}".format(path,self.compressed))
    outfile = shlex.quote("{}{}".format(path,member))
    with gzip.open(infile, 'rb') as fin, open(outfile, 'wb') as fout:
      fout.write(fin.read())
  
  def unrar(self, member, path):
    print("Document unrar()!")
    logging.info("Unrar file: {} to: {} path: {}".format(self.compressed, member, path))
    infile = shlex.quote("{}{}".format(path,self.compressed))
    outfile = shlex.quote(path)
    with rarfile.RarFile(infile) as rf:
        rf.extract(member, outfile)
  
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
      FileType.zip: self.unzip,
      FileType.rar: self.unrar,
      # FileType.unknown: should be rom
    }
    if self.type in sw.keys():
      fn = sw.get(self.type)
      fn(member, path)
    else:
      logging.info("found unknown type: {} for file: {}".format(str(self.type), member))
  
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
    logging.info("Starting decompress_all() on: {} in: {}".format(self.compressed, path))
    # get list of inner files for parsing
    list_t = self.get_inner_files(path)
    if not isinstance(list_t, list) or len(list_t) < 1:
        return # didn't return inner files, not supported or not an archive
    # parse list of files into roms and compressed files, after this extraction
    rom_list = [file_t for file_t in list_t if self.is_rom(file_t)]
    comp_list = [file_t for file_t in list_t if not self.is_rom(file_t)]
    # append roms list and rar list to inner_files. use self.extracted to determine extract method
    # picks up paths inside rom
    for cf in comp_list:
        self.inner_files.append(
          Download(
            compressed=cf,
            extract=True,
            file_order=self.file_order,
            dl_all=self.dl_all,
          ))
    for rom in rom_list:
        self.inner_files.append(
          Download(
            compressed=rom,
            extract=False,
            file_order=self.file_order,
            dl_all=self.dl_all,
          ))
    # cycle through list of files within this compressed file and extract and continue building tree if needed
    for i_f in self.inner_files:
        dirname = os.path.dirname(path+i_f.compressed)
        if not os.path.exists(dirname):
            logging.info("Creating dir {}".format(dirname))
            os.makedirs(dirname)
        self.decompress(i_f.compressed, path)
        i_f.set_filetype(path)
        if i_f.extract: # indicates compressed file and should be extracted further
            i_f.decompress_all(path)
    self.is_extracted=True
  
  def cp_to_sd(self, emulator, dlpath, sdpath):
    print("Document cp_to_sd()!")
    ROOT_TO_ROMS="/home/pi/RetroPie/roms/"
    logging.info("Copy from {} to {} for {}".format(dlpath, sdpath, self.compressed))
    if self.extract == False: # have rom, copy to sd
        src = dlpath+self.compressed # file
        dst = sdpath+ROOT_TO_ROMS+emulator+"/" # dir
        try:
            shutil.copy(src,dst)
        except OSError:
            logging.error("Dst {} is not writeable".format(dst))
            return
    if isinstance(self.inner_files,list) and 1 <= len(self.inner_files):
        # recurse through extracted files
        for i_f in self.inner_files:
            i_f.cp_to_sd(emulator, dlpath, sdpath)
