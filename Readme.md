# RetroPie Builder
## Author: Spenser Reinhardt <@c0mmiebstrd>
## Version: v0.0.1

### Intro

The Raspberrypi and RetroPie are a fantastic collection of emulators and tools
for building the ultimate retro game emulation system. Unfortunately investing
a fair amount of time and effort into collecting and curating the roms or
images for each system, configuring and managing special case games and
controllers, and finally handling metadata.

RetroPie Builder aims to merge these tasks into a single easy to configure
script. A single configuration file can handle taking a raw sd card, putting the
retropie image onto it, expanding partitions, mounting filesystems, downloading,
extracting multiple levels, and copying roms to the appropriate locations.

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
* Logging
* RetroPie controller, configuration, and theme management
* Backup and restore retropie

### DMCA Concerns

According to Archive.org, regulations have been altered to enable archiving of
retro gaming consoles and other out of production hardware and software. Any
links within this repository are intended to follow the same guidelines as
such other sites have found to be acceptable. Additionally, all defaults are set
to NOT download. If you or your organization have issues with the included
material, please contact me directly.
