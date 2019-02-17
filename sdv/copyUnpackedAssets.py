import sys
import os
from shutil import copy
from config import config

config_name = os.environ.get('SDV_APP_SETTINGS', None)
current_config = config.get(config_name)
farm_asset_dir = os.path.join(current_config.ASSET_PATH, 'farm')

def copyUnpackedAsset(src_path, dest_dir):
    file_name = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, file_name)
    if os.path.exists(dest_path):
        print('Skipping ' + dest_path + ', already exists')
        return

    try:
        copy(src_path, dest_path)
        print('Copied ' + file_name + ' to ' + dest_path)
    except Exception as e:
        print(e)

def copyUnpackedAssets():
    if len(sys.argv) < 2:
        print(sys.argv[0] + ' <path to unpacked assets>')
        exit()

    unpacked_asset_dir = sys.argv[1]
    if not os.path.exists(unpacked_asset_dir):
        print('Error: given unpacked asset directory does not exist: ' + unpacked_asset_dir)
        exit()

    print('Copying assets from ' + unpacked_asset_dir)

    farm_files = [
        'winter_outdoorsTileSheet.png',
        os.path.join('Maps', 'summer_outdoorsTileSheet.png'),
        'spring_outdoorsTileSheet.png',
        'fall_outdoorsTileSheet.png'
    ]
    for file_name in farm_files:
        copyUnpackedAsset(os.path.join(unpacked_asset_dir, file_name), farm_asset_dir)

    # TODO: copy remaining asset files to the correct places for SDV-Summary

if __name__ == '__main__':
    copyUnpackedAssets()
