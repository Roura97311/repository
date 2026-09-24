#!/usr/bin/env python

__author__ = "Chad Parry"
__contact__ = "github@chad.parry.org"
__copyright__ = "Copyright 2016 Chad Parry"
__license__ = "GNU GENERAL PUBLIC LICENSE. Version 2, June 1991"
__version__ = "1.2.3"

import argparse
import collections
import gzip
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile
import threading
import xml.etree.ElementTree
import zipfile
import time
from traceback import format_exc
import subprocess

AddonMetadata = collections.namedtuple('AddonMetadata', ('id', 'version', 'root'))
WorkerResult = collections.namedtuple('WorkerResult', ('addon_metadata', 'exc_info'))
AddonWorker = collections.namedtuple('AddonWorker', ('thread', 'result_slot'))

INFO_BASENAME = 'addon.xml'
METADATA_BASENAMES = (INFO_BASENAME, 'icon.png', 'fanart.jpg')

ALLOWED_ADDONS = {
    'repository.aeon.miro.nox',
    'resource.images.miro.nox',
    'script.aeon.miro.nox',
    'script.skin.helper.colorpicker',
    'skin.aeon.miro.nox.matrix',
    'skin.aeon.miro.nox.nexus',
    'skin.aeon.miro.nox.omega',
}

def get_archive_basename(addon_metadata):
    return '{}-{}.zip'.format(addon_metadata.id, addon_metadata.version)

def get_metadata_basenames(addon_metadata):
    return ([(basename, basename) for basename in METADATA_BASENAMES] + [('changelog.txt', 'changelog-{}.txt'.format(addon_metadata.version))])

def is_url(addon_location):
    return bool(re.match(r'[A-Za-z0-9+.-]+://.', addon_location))

def parse_metadata(metadata_file):
    tree = xml.etree.ElementTree.parse(metadata_file)
    root = tree.getroot()
    addon_metadata = AddonMetadata(root.get('id'), root.get('version'), root)
    if addon_metadata.id is None or re.search('[^a-z0-9._-]', addon_metadata.id):
        raise RuntimeError('Invalid addon ID: ' + str(addon_metadata.id))
    if addon_metadata.version is None or not re.match(r'\d+\.\d+\.\d+$', addon_metadata.version):
        raise RuntimeError('Invalid addon version: ' + str(addon_metadata.version))
    return addon_metadata

def copy_metadata_files(source_folder, addon_target_folder, addon_metadata):
    for source_basename, target_basename in get_metadata_basenames(addon_metadata):
        source_path = os.path.join(source_folder, source_basename)
        if os.path.isfile(source_path):
            shutil.copyfile(source_path, os.path.join(addon_target_folder, target_basename))

def fetch_addon_from_git(addon_location, target_folder, temp_folder):
    alt_addonid = ""
    alt_addonname = ""
    git_branch = "master"
    addon_vars = addon_location.split("#")
    git_location = addon_vars[0]
    if len(addon_vars) > 1: git_branch = addon_vars[1]
    if len(addon_vars) > 2: alt_addonid = addon_vars[2]
    if len(addon_vars) > 3: alt_addonname = addon_vars[3]
    download_url = git_location + "/archive/%s.zip" % git_branch
    addon_id = git_location.split("/")[-1]
    zip_file = os.path.abspath(os.path.join(temp_folder, "%s%s.zip" % (addon_id, alt_addonid)))
    import requests
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    with open(zip_file, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)
    del response
    addon_temp = os.path.abspath(os.path.join(temp_folder, addon_id + alt_addonid))
    os.makedirs(addon_temp)
    do_unzip(zip_file, addon_temp)
    addon_temp = os.path.join(addon_temp, "%s-%s" % (addon_id, git_branch))
    if alt_addonid and alt_addonname:
        addon_file = os.path.join(addon_temp, "addon.xml")
        with open(addon_file, 'r', encoding='utf-8') as f:
            filedata = f.read()
        newdata = filedata.replace(addon_id, alt_addonid)
        body = newdata.replace('\r', '').replace('\n', '').replace('\t', '')
        addon_name = re.compile('name="(.*?)"').findall(body)[0]
        newdata = newdata.replace(addon_name, alt_addonname)
        with open(addon_file, 'w', encoding='utf-8') as f:
            f.write(newdata)
    return fetch_addon_from_folder(addon_temp, target_folder)

def fetch_addon_from_folder(raw_addon_location, target_folder):
    try:
        addon_location = os.path.abspath(raw_addon_location)
        metadata_path = os.path.join(addon_location, INFO_BASENAME)
        addon_metadata = parse_metadata(metadata_path)
        if addon_metadata.id not in ALLOWED_ADDONS:
            print("Ignoring addon %s" % addon_metadata.id)
            return addon_metadata
        addon_target_folder = os.path.join(target_folder, addon_metadata.id)
        cur_metadata_path = os.path.join(addon_target_folder, INFO_BASENAME)
        if os.path.exists(cur_metadata_path):
            cur_metadata = parse_metadata(cur_metadata_path)
            if cur_metadata.version == addon_metadata.version:
                archive_path = os.path.join(addon_target_folder, get_archive_basename(addon_metadata))
                if os.path.isfile(archive_path):
                    print("Addon %s already has version %s on the repo, skipping..." % (addon_metadata.id, addon_metadata.version))
                    return cur_metadata
        if not os.path.isdir(addon_target_folder):
            os.makedirs(addon_target_folder)
        archive_path = os.path.join(addon_target_folder, get_archive_basename(addon_metadata))
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for root, dirs, files in os.walk(addon_location):
                relative_root = os.path.join(addon_metadata.id, os.path.relpath(root, addon_location))
                for relative_path in files:
                    sourcefile = os.path.join(root, relative_path)
                    destfile = os.path.join(relative_root, relative_path)
                    archive.write(sourcefile, destfile)
        copy_metadata_files(addon_location, addon_target_folder, addon_metadata)
    except Exception as exc:
        print(format_exc(sys.exc_info()))
        raise exc
    return addon_metadata

def buildskintextures(addon_folder):
    themes_dir = os.path.join(addon_folder, "themes")
    media_dir = os.path.join(addon_folder, "media")
    if os.path.isdir(media_dir):
        if not os.path.isdir(themes_dir): os.mkdir(themes_dir)
        shutil.move(media_dir, os.path.join(themes_dir, "Textures"))
        os.makedirs(media_dir)
        for item in os.listdir(themes_dir):
            themedir = os.path.join(themes_dir, item)
            if os.path.isdir(themedir):
                theme_file = os.path.join(media_dir, "%s.xbt" % item)
                tpargs = '-dupecheck -input %s -output %s' % (themedir, theme_file)
                subprocess.Popen(('TexturePacker.exe', tpargs)).wait()
        shutil.rmtree(themes_dir, ignore_errors=False)

def samefile(file1, file2):
    return os.stat(file1) == os.stat(file2)

def fetch_addon_from_zip(raw_addon_location, target_folder):
    addon_location = os.path.abspath(raw_addon_location)
    with zipfile.ZipFile(addon_location, compression=zipfile.ZIP_DEFLATED) as archive:
        roots = frozenset(next(iter(path.split(os.path.sep)), '') for path in archive.namelist())
        if len(roots) != 1: raise RuntimeError('Archive should contain one directory')
        root = next(iter(roots))
        if not root: raise RuntimeError('Archive should contain a directory')
        metadata_file = archive.open(os.path.join(root, INFO_BASENAME))
        addon_metadata = parse_metadata(metadata_file)
        addon_target_folder = os.path.join(target_folder, addon_metadata.id)
        if not os.path.isdir(addon_target_folder): os.makedirs(addon_target_folder)
        for source_basename, target_basename in get_metadata_basenames(addon_metadata):
            try: source_file = archive.open(os.path.join(root, source_basename))
            except KeyError: continue
            with open(os.path.join(addon_target_folder, target_basename), 'wb') as target_file:
                shutil.copyfileobj(source_file, target_file)
    archive_basename = get_archive_basename(addon_metadata)
    archive_path = os.path.join(addon_target_folder, archive_basename)
    if (not samefile(os.path.dirname(addon_location), addon_target_folder) or os.path.basename(addon_location) != archive_basename):
        shutil.copyfile(addon_location, archive_path)
    return addon_metadata

def do_unzip(zip_path, targetdir):
    zip_file = zipfile.ZipFile(zip_path, 'r', allowZip64=True)
    for fileinfo in zip_file.infolist():
        filename = fileinfo.filename
        if not filename.endswith("/"):
            cur_path = os.path.join(targetdir, filename)
            basedir = os.path.dirname(cur_path)
            if not os.path.isdir(basedir): os.makedirs(basedir)
            outputfile = open(cur_path, "wb")
            shutil.copyfileobj(zip_file.open(fileinfo.filename), outputfile)
            outputfile.close()
    zip_file.close()
    print("UNZIP DONE of file %s" % zip_path)

def fetch_addon(addon_location, target_folder, result_slot, temp_folder):
    try:
        print("Processing %s" % addon_location)
        if is_url(addon_location): addon_metadata = fetch_addon_from_git(addon_location, target_folder, temp_folder)
        elif os.path.isdir(addon_location): addon_metadata = fetch_addon_from_folder(addon_location, target_folder)
        elif os.path.isfile(addon_location): addon_metadata = fetch_addon_from_zip(addon_location, target_folder)
        else: raise RuntimeError('Path not found: ' + addon_location)
        result_slot.append(WorkerResult(addon_metadata, None))
    except:
        result_slot.append(WorkerResult(None, sys.exc_info()))

def get_addon_worker(addon_location, target_folder, temp_folder):
    result_slot = []
    thread = threading.Thread(target=lambda: fetch_addon(addon_location, target_folder, result_slot, temp_folder))
    return AddonWorker(thread, result_slot)

def cleanup_dir(dirname):
    if not os.path.isdir(dirname): return
    shutil.rmtree(dirname, ignore_errors=False)
    while os.path.isdir(dirname):
        print("wait for folder deletion")
        time.sleep(1)

def create_repository(addon_locations, target_folder, info_path, checksum_path, is_compressed):
    if any(is_url(addon_location) for addon_location in addon_locations):
        try:
            global git
            import git
        except ImportError:
            raise RuntimeError('Please install GitPython: pip install gitpython')
    if not os.path.isdir(target_folder): os.makedirs(target_folder)
    temp_folder = os.path.abspath(os.path.join(target_folder, "temp"))
    cleanup_dir(temp_folder)
    if not os.path.isdir(temp_folder): os.makedirs(temp_folder)
    workers = [get_addon_worker(addon_location, target_folder, temp_folder) for addon_location in addon_locations]
    for worker in workers: worker.thread.start()
    for worker in workers: worker.thread.join()
    metadata = []
    for worker in workers:
        try: result = next(iter(worker.result_slot))
        except StopIteration: raise RuntimeError('Addon worker did not report result')
        if result.exc_info is not None: raise result.exc_info[1]
        if result.addon_metadata.id in ALLOWED_ADDONS: metadata.append(result.addon_metadata)
    unique_metadata = {}
    for addon_metadata in metadata: unique_metadata[addon_metadata.id] = addon_metadata
    metadata = list(unique_metadata.values())
    metadata.sort(key=lambda item: item.id)
    root = xml.etree.ElementTree.Element('addons')
    for addon_metadata in metadata: root.append(addon_metadata.root)
    tree = xml.etree.ElementTree.ElementTree(root)
    with io.BytesIO() as info_file:
        tree.write(info_file, encoding='UTF-8', xml_declaration=True)
        info_contents = info_file.getvalue()
    if is_compressed: info_file = gzip.open(info_path, 'wb')
    else: info_file = open(info_path, 'wb')
    with info_file: info_file.write(info_contents)
    digest = hashlib.md5(info_contents).hexdigest()
    with open(checksum_path, 'w', encoding='ascii') as sig: sig.write(digest)
    print(); print("Repository generated:"); print("  addons.xml : %s" % info_path); print("  addons.xml.md5 : %s" % checksum_path); print("  addons : %d" % len(metadata))
    for addon_metadata in metadata: print("    %-40s %s" % (addon_metadata.id, addon_metadata.version))
    cleanup_dir(temp_folder)

def main():
    parser = argparse.ArgumentParser(description=('Create a Kodi add-on repository from add-on sources'))
    parser.add_argument('--datadir', '-d', default='.', help=('Path to place the add-ons [current directory]'))
    parser.add_argument('--info', '-i', help=('Path for the addons.xml file [DATADIR/addons.xml or DATADIR/addons.xml.gz if compressed]'))
    parser.add_argument('--checksum', '-c', help=('Path for the addons.xml.md5 file [DATADIR/addons.xml.md5]'))
    parser.add_argument('--compressed', '-z', action='store_true', help=('Compress addons.xml with gzip'))
    parser.add_argument('addon', nargs='*', metavar='ADDON', help=('Location of the add-on: either a path to a local folder or to a zip archive or a URL for a Git repository'))
    args = parser.parse_args()
    addonslist_path = os.path.join(os.getcwd(), "addonslist.txt")
    if os.path.exists(addonslist_path):
        with open(addonslist_path, encoding='utf-8') as f:
            for line in f.readlines():
                line = line.strip()
                if not line: continue
                if line.startswith("#"): continue
                args.addon.append(line)
    data_path = os.path.abspath(args.datadir)
    if args.info is None:
        info_basename = 'addons.xml.gz' if args.compressed else 'addons.xml'
        info_path = os.path.join(data_path, info_basename)
    else: info_path = os.path.abspath(args.info)
    checksum_path = os.path.abspath(args.checksum) if args.checksum is not None else os.path.join(data_path, 'addons.xml.md5')
    create_repository(args.addon, data_path, info_path, checksum_path, args.compressed)

if __name__ == "__main__":
    main()
