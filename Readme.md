# RetroPie Builder
## Author: Spenser Reinhardt <@c0mmiebstrd>
## Version: v0.0.1

### Table of Contents

* [Introduction](Readme.md#introduction)
* [Using Retropie-Builder](Readme.md#using-retropie-builder)
  * [Windows](Readme.md#windows)
  * [OSX](Readme.md#osx)
  * [Linux](Readme.md#linux)
  * [Retropie](Readme.md#retropie)
* [Current State](Readme.md#current-state)
* [Remaining Work](Readme.md#todo)

### Introduction

The Raspberrypi and RetroPie are a fantastic collection of emulators and tools
for building the ultimate retro game emulation system. Unfortunately investing
a fair amount of time and effort into collecting and curating the roms or
images for each system, configuring and managing special case games and
controllers, and finally handling metadata.

RetroPie Builder aims to merge these tasks into a single easy to configure
script. A single configuration file can handle taking a raw sd card, putting the
retropie image onto it, expanding partitions, mounting filesystems, downloading,
extracting multiple levels, and copying roms to the appropriate locations.

### Using Retropie-Builder

Retropie-Builder is intened for use on all operating systems supporting python,
however Mac OSX and Microsoft Windows do not natively support ext4, the filesystem
used by the retropie image. Because of this, only downloading the retropie image
and copying to an sd card is supported on those operating systems. Future plans
incude modifications to an images /boot partition for adding builder to an image
for further processing on that device.

#### Windows

UNTESTED, I don't use Windows, although as suggested above some support is
expected. This is likely very broken as I'll need to address the underlying
windows differences to raw disk access. Feel free to send pull requests!

#### OSX

OSX works great for burning the retropie image, however it does not have ext4
support, so we can only burn an image to sdcards. You should expect to see an
exit message indicating that no further processing can be done on osx once this
is completed.

* Config:
  * dev_path = /dev/disk2 - this should be the base device not a partition

#### Linux

Linux is the main operating system intended to build a retropie. It's scary,
but use sudo unless you run as root. If you have an sdcard with existing image
various flags can be used to avoid mounting and reimaging.

* Config:
  * dev_path = /dev/sdc - this should be the base device not a partition
  * filesystem - leave unless building your own image
  * expand - resize resulting second partition?

#### Retropie

When run directly on a raspberrypi, it is suggested to attach external storage
for downloading and extraction. To maximize space available to extracted roms,
the external would store all downloaded and extracted files prior to copying.
This will result in a slower process though.

* Flags:
  * --ignore_mounts, do not allow builder to mount sdcard partitions.
  * --install_roms, only download, filter, extract, and copy roms.
* Config:
  * mount_path = /
  * temp_path = /path/to/external
  * filters = enable as needed

### Current State

* Image SD card
  * Given a path to online or offline retropie images and an sd card,
  rpi_builder will attempt to download, extract, and place the retropie image
  onto the sd card.
* Expand Partitions
  * After imaging the secondary or root partition as set by the retropie image
  will be expanded to fill remaining space on the drive.
* Downloading Files and Folders
  * Builder will look for several endings to paths and files within an emulators
  rom_uris variable in an attempt to smartly determine how best to retrieve
  files.
  * rar, tar, zip, r\d+, z\d+, gz, etc
    * Files will be downloaded directly, use of dl_all_b4_extract is needed for
    multipart compressed files.
  * trailing /
    * Attempts capture as a file will be attempted and if found to be a folder,
    files contained within of supported extension will be downloaded. Use of
    dl_all_b4_extract is suggested for folders containing multipart compressed
    files.
  * torrent
    * Torrents can be listed and printed back to the user. Torrenting is the
    suggested download method, as it helps support the emulation community and
    keeps projects such as these alive. It would however be far beyond the scope
    of this project to include torrent downloads.
* Recursive File Extraction
  * Once downloaded builder understands that many rom packs are a single or
  multipart compressed files, containing one or more further layers of
  compression. Such examples are rar->rom individual zips->raw rom files. Level
  of decompression is controlled by the extensions config option. In cases such
  as FBA and mame, an end result of zips containing a set of files for an
  individual rom may be desired. Simply put the zip file extension or whichever
  extensions you wish to stop attempting extraction against. Builder will always
  expect to extract the directly listed files in the configuration. Downloading
  without extraction is not presently supported or any sources known.
* Copying to sd card
  * Post extraction, roms are copied to the appropriate directory for
  emulation. No fancy magic here.
* Filtering of extracted roms
  * Prior to extraction retropie-builder lists the inner files of a download, we
  we can then avoid extracting unwanted files, both wasting space and time.

* Systems without active download links
  * daphne
  * game and watch
  * advancemames
  * mame2003 (login)
  * mame4all
  * psp (torrents)
  * playstation 2 (torrents)
  * wii (copyright)
  
### To Do

* Complete tying together for v0.1
* Remaining free space checks
* RetroPie controller, configuration, and theme management
* Backup and restore retropie

### DMCA Concerns

According to Archive.org, regulations have been altered to enable archiving of
retro gaming consoles and other out of production hardware and software. Any
links within this repository are intended to follow the same guidelines as
such other sites have found to be acceptable. Additionally, all defaults are set
to NOT download. If you or your organization have issues with the included
material, please contact me directly.
