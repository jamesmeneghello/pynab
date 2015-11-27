#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A pure-Python module for identifying and examining RAR files developed without
any exposure to the original unrar code. (Just format docs from wotsit.org)

It was, however, influenced by the zipfile module in the Python standard
library as, having already decided to match the zipfile.ZipFile API as closely
as feasibly possible, I didn't see a point to doing extra work to come up with
new ways of laying out my code for no good reason.

@todo: Determine how rarfile (http://rarfile.berlios.de/) compares to this in
various target metrics. If it is superior or close enough on all fronts,
patch it as necessary and plan a migration path. Otherwise, do the following:
 - Complete the parsing of the RAR metadata.
   (eg. Get data from archive header, check CRCs, read cleartext comments, etc.)
 - Optimize further and write a test suite.
 - Double-check that ZipFile/ZipInfo API compatibility has been maintained
   wherever feasible.
 - Support extraction of files stored with no compression.
 - Look into supporting split and password-protected RARs.
 - Some password-protected RAR files use blocks with types 0x30, 0x60, and 0xAD
   according to this code. Figure out whether it's a bug or whether they're really
   completely new kinds of blocks. (Encrypted headers for filename-hiding?)
 - When the appropriate code is available, use the following message for failure
   to extract compressed files::
    For reasions of patent, performance, and a general lack of motivation on the
    author's part, this module does not extract compressed files.
"""

__appname__ = "rar.py"
__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.2.99.0"
__license__ = "PSF License 2.4 or higher (The Python License)"

#{ Settings for findRarHeader()
CHUNK_SIZE = 4096
MARKER_BLOCK = b"\x52\x61\x72\x21\x1a\x07\x00"
FIND_LIMIT = 1024 ** 2 #: 1MiB
# A Compromise. Override FIND_LIMIT with 0 to be sure but potentially very slow.

#{ Packing method values
RAR_STORED = 0x30
RAR_FASTEST = 0x31
RAR_FAST = 0x32
RAR_NORMAL = 0x33
RAR_GOOD = 0x34
RAR_BEST = 0x35
#}

import math
import struct
import sys
import time
import zlib

_struct_blockHeader = struct.Struct("<HBHH")
_struct_addSize = struct.Struct('<L')
_struct_fileHead_add1 = struct.Struct("<LBLLBBHL") # Plus FILE_NAME and everything after it
_struct_bigFileHead_add1 = struct.Struct("<LBLLBBHLLL") # Plus FILE_NAME and everything after it


class BadRarFile(Exception):
    """Raised when no valid RAR header is found in a given file."""


class RarInfo(object):
    """The metadata for a file stored in a RAR archive.

    @attention: API compatibility with ZipInfo could not be maintained in the
    following fields:
     - C{create_version} (Not stored in RAR files)
     - C{flag_bits} (Zip and RAR use different file header flags)
     - C{volume} (Zip files specify volume number. RAR files just have
       "File is continued from previous" and "File continues in next" flags and
       an archive-level "is volume" flag)
     - C{comment} (RAR files may have multiple comments per file and they may be
       stored using compression... which rar.py doesn't support)

    @todo: How do I interpret the raw file timestamp?
    @todo: Is the file's CRC of the compressed or uncompressed data?
    @todo: Does RAR perform any kind of path separator normalization?
    """

    os_map = ['MS DOS', 'OS/2', 'Win32', 'Unix'] #: Interpretations for possible L{create_system} values.

    compress_size = None    #: File's compressed size
    compress_type = None    #: Packing method (C{0x30} indicates no compression)
    create_system = None    #: Type of system on which the file originated (See L{os_map})
    date_time = None        #: File's timestamp
    external_attr = None    #: File's attributes
    extract_version = None  #: Minimum RAR version needed to extract (major * 10 + minor)
    filename = None         #: Filename relative to the archive root
    file_size = None        #: File's uncompressed size
    flag_bits = 0           #: Raw flag bits from the RAR header
    header_offset = None    #: Offset of the compressed data within the file
    is_directory = False    #: The entry describes a folder/directory
    is_encrypted = False    #: The file has been encrypted with a password
    is_solid = False        #: Information from previous files has been used
    not_first_piece = False #: File is continued from previous volume
    not_last_piece = False  #: File continues in next volume
    CRC = None              #: File's CRC
    _raw_time = None        #: Raw integer time value extracted from the header

    #TODO: comment, extra, reserved, internal_attr

    def __init__(self, filename, ftime=0):
        """
        @param filename: The file's name and path relative to the archive root.

        @note: Since I know of no filesystem which allows null bytes in paths,
        this borrows a trick from C{ZipInfo} and truncates L{filename} at the
        first null byte to protect against certain kinds of virus tricks.

        @todo: Implement support for taking ints OR tuples for L{ftime}.
        """
        filename = filename.decode('ISO-8859-1')
        null_byte = filename.find(chr(0))
        if null_byte >= 0:
            filename = filename[0:null_byte]

        self.filename = filename
        self.orig_filename = filename # Match ZipInfo for better compatibility
        self._raw_time = ftime
        self.date_time = time.gmtime(self._raw_time) #TODO: Verify this is correct.


class RarFile(object):
    """A simple parser for RAR archives capable of retrieving content metadata
    and, possibly in the future, of extracting entries stored without
    compression.

    @note: Whenever feasible, this class replicates the API of
        C{zipfile.ZipFile}. As a side-effect, design decisions the author
        has no strong feelings about (eg. naming of private methods)
        will generally closely follow those made C{in zipfile.ZipFile}.
    """

    _block_types = {
        0x72: 'Marker Block ( MARK_HEAD )',
        0x73: 'Archive Heaver ( MAIN_HEAD )',
        0x74: 'File Header',
        0x75: 'Comment Header',
        0x76: 'Extra Info',
        0x77: 'Subblock',
        0x78: 'Recovery Record',
        0x7b: 'Terminator?'
    } #: Raw HEAD_TYPE values used in block headers.

    # According to the comment in zipfile.ZipFile, __del__ needs fp here.
    fp = None          #: The file handle used to read the metadata.
    _filePassed = None #: Whether an already-open file handle was passed in.

    # I just put all public members here as a matter of course.
    filelist = None #: A C{list} of L{RarInfo} objects corresponding to the contents.
    debug = 0       #: Debugging verbosity. Effective range is currently 0 to 1.

    def __init__(self, handle):
        # If we've been given a path, get our desired file-like object.
        if isinstance(handle, str):
            self_filePassed = False
            self.filename = handle
            self.fp = open(handle, 'rb')
        else:
            self._filePassed = True
            self.fp = handle
            self.filename = getattr(handle, 'name', None)

        # Find the header, skipping the SFX module if present.
        start_offset = findRarHeader(self.fp)
        if start_offset:
            self.fp.seek(start_offset)
        else:
            if not self._filePassed:
                self.fp.close()
                self.fp = None
            raise BadRarFile("Not a valid RAR file")

        self.filelist = []

        # Actually read the file metadata.
        try:
            self._getContents()
        except:
            if not self._filePassed:
                self.fp.close()
                self.fp = None
            raise BadRarFile("Problem reading file")

    def __del__(self):
        """Close the file handle if we opened it... just in case the underlying
        Python implementation doesn't do refcount closing."""
        if self.fp and not self._filePassed:
            self.fp.close()

    def _getContents(self):
        """Content-reading code is here separated from L{__init__} so that, if
        the author so chooses, writing of uncompressed RAR files may be
        implemented in a later version more easily.
        """
        while True:
            offset = self.fp.tell()

            # Read the fields present in every type of block header
            try:
                head_crc, head_type, head_flags, head_size = self._read_struct(_struct_blockHeader)
            except struct.error:
                # If it fails here, we've reached the end of the file.
                return

            # Read the optional field ADD_SIZE if present.
            if head_flags & 0x8000:
                add_size = self._read_struct(_struct_addSize)[0]
            else:
                add_size = 0

            # TODO: Rework handling of archive headers.
            if head_type == 0x73:
                #TODO: Try to factor this out to reduce time spent in syscalls.
                self.fp.seek(offset + 2) # Seek to just after HEAD_CRC

            # TODO: Rework handling of file headers.
            elif head_type == 0x74:
                high_unp_size = 0
                try:
                    if head_flags & 0x0100:
                        unp_size, host_os, file_crc, ftime, unp_ver, method, name_size, attr, high_p_size, high_unp_size = self._read_struct(
                            _struct_bigFileHead_add1)
                    else:
                        unp_size, host_os, file_crc, ftime, unp_ver, method, name_size, attr = self._read_struct(
                            _struct_fileHead_add1)

                except:
                    raise BadRarFile("Problem reading file")

                # FIXME: What encoding does WinRAR use for filenames?
                # TODO: Verify that ftime is seconds since the epoch as it seems
                fileinfo = RarInfo(self.fp.read(name_size), ftime)
                fileinfo.compress_size = add_size
                fileinfo.header_offset = offset
                fileinfo.file_size = unp_size + (high_unp_size << 32)
                fileinfo.CRC = file_crc         #TODO: Verify the format matches that ZipInfo uses.
                fileinfo.compress_type = method

                # Note: RAR seems to have copied the encoding methods used by
                # Zip for these values.
                fileinfo.create_system = host_os
                fileinfo.extract_version = unp_ver
                fileinfo.external_attr = attr  #TODO: Verify that this is correct.

                # Handle flags
                fileinfo.flag_bits = head_flags
                fileinfo.not_first_piece = head_flags & 0x01
                fileinfo.not_last_piece = head_flags & 0x02
                fileinfo.is_encrypted = head_flags & 0x04
                #TODO: Handle comments
                fileinfo.is_solid = head_flags & 0x10

                # TODO: Verify this is correct handling of bits 7,6,5 == 111
                fileinfo.is_directory = head_flags & 0xe0

                self.filelist.append(fileinfo)
            elif self.debug > 0:
                sys.stderr.write(
                    "Unhandled block: %s\n" % self._block_types.get(head_type, 'Unknown (0x%x)' % head_type))

            # Line up for the next block
            #TODO: Try to factor this out to reduce time spent in syscalls.
            if head_size == 0 and add_size == 0:
                return

            self.fp.seek(offset + head_size + add_size)

    def _read_struct(self, fmt):
        """Simplifies the process of extracting a struct from the open file."""
        return fmt.unpack(self.fp.read(fmt.size))

    def _check_crc(self, data, crc):
        """Check some data against a stored CRC.

        Note: For header CRCs, RAR calculates a CRC32 and then throws out the high-order bytes.

        @bug: This method of parsing is deprecated.
        @todo: I've only tested this out on 2-byte CRCs, not 4-byte file data CRCs.
        @todo: Isn't there some better way to do the check for CRC bitwidth?
        @bug: Figure out why I can't get a match on valid File Header CRCs.
        """
        if isinstance(crc, int):
            if crc < 65536:
                crc = struct.pack('>H', crc)
            else:
                crc = struct.pack('>L', crc)
        return struct.pack('>L', zlib.crc32(data)).endswith(crc)

    def infolist(self):
        """Return a list of L{RarInfo} instances for the files in the archive."""
        return self.filelist

    def namelist(self):
        """Return a list of filenames for the files in the archive."""
        return [x.filename for x in self.filelist]


def findRarHeader(handle, limit=FIND_LIMIT):
    """Searches a file-like object for a RAR header.

    @returns: The in-file offset of the first byte after the header block or
    C{None} if no RAR header was found.

    @warning: The given file-like object must support C{seek()} up to the size
    of C{limit}.

    @note: C{limit} is rounded up to the nearest multiple of L{CHUNK_SIZE}.

    @todo: Audit this to ensure it can't raise an exception L{is_rarfile()}
    won't catch.
    """
    startPos, chunk = handle.tell(), b""
    limit = math.ceil(limit / float(CHUNK_SIZE)) * CHUNK_SIZE

    # Find the RAR header and line up for further reads. (Support SFX bundles)
    while True:
        temp = handle.read(CHUNK_SIZE)
        curr_pos = handle.tell()

        # If we hit the end of the file without finding a RAR marker block...
        if not temp or (0 < limit < curr_pos):
            handle.seek(startPos)
            return None

        chunk += temp
        marker_offset = chunk.find(MARKER_BLOCK)
        if marker_offset > -1:
            handle.seek(startPos)
            return curr_pos - len(chunk) + marker_offset + len(MARKER_BLOCK)

        # Obviously we haven't found the marker yet...
        chunk = chunk[len(temp):] # Use a rolling window to minimize memory consumption.


def is_rarfile(filename, limit=FIND_LIMIT):
    """Convenience wrapper for L{findRarHeader} equivalent to C{is_zipfile}.

    Returns C{True} if C{filename} is a valid RAR file based on its magic
    number, otherwise returns C{False}.

    Optionally takes a limiting value for the maximum amount of data to sift
    through. Defaults to L{FIND_LIMIT} to set a sane bound on performance. Set
    it to 0 to perform an exhaustive search for a RAR header.

    @note: findRarHeader rounds this limit up to the nearest multiple of
    L{CHUNK_SIZE}.
    """
    try:
        handle = open(filename, 'rb')
        return findRarHeader(handle, limit) is not None
    except IOError:
        pass
    return False


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(description=__doc__.split('\n\n')[0],
                          version="%%prog v%s" % __version__, usage="%prog <path> ...")

    opts, args = parser.parse_args()

    if args:
        RarFile.debug = 1
        for fpath in args:
            print("File: %s" % fpath)
            if is_rarfile(fpath):
                for line in RarFile(fpath).namelist():
                    print("\t%s" % line)
            else:
                print("Not a RAR file")
