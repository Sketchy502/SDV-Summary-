import os
from config import config

config_name = os.environ.get('SDV_APP_SETTINGS', None)
current_config = config.get(config_name)

def makeAssetDirectory(name):
  asset_dir = os.path.join(current_config.ASSET_PATH, name)
  if os.path.exists(asset_dir):
    print('Skipping ' + asset_dir + ', already exists')
  else:
    print('Creating ' + asset_dir)
    os.makedirs(asset_dir)

def makeAssetDirectories():
  makeAssetDirectory('farm')
  makeAssetDirectory(os.path.join('farm', 'trees'))
  makeAssetDirectory(os.path.join('farm', 'buildings'))
  makeAssetDirectory(os.path.join('farm', 'grass'))

if __name__ == '__main__':
    makeAssetDirectories()
