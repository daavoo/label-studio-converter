"""
Original RLE JS code from https://github.com/thi-ng/umbrella/blob/develop/packages/rle-pack/src/index.ts

export const decode = (src: Uint8Array) => {
    const input = new BitInputStream(src);
    const num = input.read(32);
    const wordSize = input.read(5) + 1;
    const rleSizes = [0, 0, 0, 0].map(() => input.read(4) + 1);
    const out = arrayForWordSize(wordSize, num);
    let x, j;
    for (let i = 0; i < num; ) {
        x = input.readBit();
        j = i + 1 + input.read(rleSizes[input.read(2)]);
        if (x) {
            out.fill(input.read(wordSize), i, j);
            i = j;
        } else {
            for (; i < j; i++) {
                out[i] = input.read(wordSize);
            }
        }
    }
    return out;
};

const arrayForWordSize = (ws: number, n: number) => {
    return new (ws < 9 ? Uint8Array : ws < 17 ? Uint16Array : Uint32Array)(n);
};
"""
import os
import json
import numpy as np
import logging

from PIL import Image
from collections import defaultdict

logger = logging.getLogger(__name__)


class InputStream:
    def __init__(self, data):
        self.data = data
        self.i = 0

    def read(self, size):
        out = self.data[self.i:self.i+size]
        self.i += size
        return int(out, 2)


def access_bit(data, num):
    """ from bytes array to bits by num position
    """
    base = int(num // 8)
    shift = 7 - int(num % 8)
    return (data[base] & (1 << shift)) >> shift


def bytes2bit(data):
    """ get bit string from bytes data
    """
    return ''.join([str(access_bit(data, i)) for i in range(len(data) * 8)])


def decode_rle(rle):
    """ from LS RLE to numpy uint8 3d image [width, height, channel]
    """
    input = InputStream(bytes2bit(rle))
    num = input.read(32)
    word_size = input.read(5) + 1
    rle_sizes = [input.read(4)+1 for _ in range(4)]
    print('RLE params:', num, 'values', word_size, 'word_size', rle_sizes, 'rle_sizes')
    i = 0
    out = np.zeros(num, dtype=np.uint8)
    while i < num:
        x = input.read(1)
        j = i + 1 + input.read(rle_sizes[input.read(2)])
        if x:
            val = input.read(word_size)
            out[i:j] = val
            i = j
        else:
            while i < j:
                val = input.read(word_size)
                out[i] = val
                i += 1
    return out


def decode_from_annotation(from_name, results):
    """ from LS annotation to {"tag_name + label_name": [numpy uint8 image (width x height)]}
    """
    layers = {}
    counters = defaultdict(int)
    for result in results:
        if result['type'].lower() != 'brushlabels':
            continue

        rle = result['rle']
        width = result['original_width']
        height = result['original_height']
        labels = result['brushlabels']
        name = from_name + '-' + '-'.join(labels)

        # result count
        i = str(counters[name])
        counters[name] += 1
        name += '-' + i

        image = decode_rle(rle)
        layers[name] = np.reshape(image, [height, width, 4])[:, :, 3]
    return layers


def save_brush_images_from_annotation(task_id, from_name, results, out_dir, out_format='numpy'):
    layers = decode_from_annotation(from_name, results)
    for name in layers:
        filename = os.path.join(out_dir, 'task-' + str(task_id) + '-' + name)
        image = layers[name]
        logger.debug(f'Save image to {filename}')
        if out_format == 'numpy':
            np.save(filename, image)
        elif out_format == 'png':
            im = Image.fromarray(image)
            im.save(filename + '.png')
        else:
            raise Exception('Unknown output format for brush converter')


def convert_task(item, out_dir, out_format='numpy'):
    """ Task with multiple annotations to brush images, out_format = numpy | png
    """
    task_id = item['id']
    for from_name, results in item['output'].items():
        save_brush_images_from_annotation(task_id, from_name, results, out_dir, out_format)


def convert_task_dir(items, out_dir, out_format='numpy'):
    """ Directory with tasks and annotation to brush images, out_format = numpy | png
    """
    for item in items:
        convert_task(item, out_dir, out_format)


# convert_task_dir('/ls/test/annotations', '/ls/test/annotations/output', 'numpy')
