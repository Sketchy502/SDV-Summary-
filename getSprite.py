from PIL import Image
from PIL.ImageChops import offset

# Takes Spritesheet and returns 16x32 image of required part
def cropImage(fileName, index, count, dim, loc = (0,0)):
    with Image.open(fileName) as img:
        x = (index % count) * dim[0]
        y = (index // count) * dim[1]
        part = offset(img, -x, -y).crop((0,0,dim[0],dim[1]))
    whole_img = Image.new("RGBA", (16,32), (0,0,0,0))
    whole_img.paste(part, loc, part)
    return whole_img