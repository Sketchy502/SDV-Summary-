#!/bin/bash

sourcedir=$1
assetsdir=$2


mkdir -p $assetsdir/farm/trees
mkdir -p $assetsdir/bases/spring
mkdir -p $assetsdir/bases/summer
mkdir -p $assetsdir/bases/fall
mkdir -p $assetsdir/bases/winter
mkdir -p $assetsdir/farm/buildings
mkdir -p $assetsdir/farm/grass

python3 imagegeneration/renderTiles.py --output $assetsdir/bases/spring --tile /media/storage/storage/outdir/Maps/Farm.tbin
python3 imagegeneration/renderTiles.py --output $assetsdir/bases/summer --season summer --tile /media/storage/storage/outdir/Maps/Farm.tbin
python3 imagegeneration/renderTiles.py --output $assetsdir/bases/fall --season fall --tile /media/storage/storage/outdir/Maps/Farm.tbin
python3 imagegeneration/renderTiles.py --output $assetsdir/bases/winter --season winter --tile /media/storage/storage/outdir/Maps/Farm.tbin

cd $assetsdir


cp $sourcedir/Maps/springobjects.png farm/objects.png
cp $sourcedir/TileSheets/Craftables.png farm/craftables.png

cp $sourcedir/TerrainFeatures/Flooring.png farm/flooring.png

cp $sourcedir/TerrainFeatures/hoeDirt.png farm/
cp $sourcedir/TerrainFeatures/hoeDirtSnow.png farm/hoeDirtsnow.png
cp $sourcedir/TileSheets/crops.png farm/
cp $sourcedir/LooseSprites/Fence*.png farm/

cp $sourcedir/TerrainFeatures/tree* farm/trees/
cp farm/trees/tree3_spring.png farm/trees/tree3_summer.png
cp $sourcedir/TerrainFeatures/mushroom_tree.png farm/trees/
cp $sourcedir/TileSheets/fruitTrees.png farm/
cp $sourcedir/TerrainFeatures/grass.png farm/grass/

cp $sourcedir/Buildings/* farm/buildings/
